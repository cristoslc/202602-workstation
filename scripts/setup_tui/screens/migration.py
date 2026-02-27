"""DataMigrationScreen — bulk-copy user data folders from another machine."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    ProgressBar,
    RichLog,
    Static,
)

from ..lib.defaults import run_all_imports
from ..lib.proc_cleanup import terminate_procs
from ..lib.runner import REPO_ROOT

logger = logging.getLogger("setup")

DATA_PULL_SCRIPT = REPO_ROOT / "scripts" / "data-pull.sh"
SSH_KEY_PATH = Path.home() / ".ssh" / "id_ed25519"
MIGRATION_LOG = Path.home() / ".local" / "log" / "migration.log"
_SAVED_HOST_FILE = Path("/tmp/.workstation-migration-host")

# Regex for rsync --info=progress2 output lines, e.g.:
#   1,234,567,890  45%  12.34MB/s    0:01:23 (xfr#1, ir-chk=100/200)
# The bytes field may use commas. Percentage is integer. Speed has units.
# Time is H:MM:SS or M:SS.
_PROGRESS2_RE = re.compile(
    r"^\s*"
    r"(?P<bytes>[\d,]+)\s+"
    r"(?P<pct>\d+)%\s+"
    r"(?P<speed>\S+)\s+"
    r"(?P<eta>\d[\d:]+)"
)

# Structured markers emitted by data-pull.sh
_SCAN_RE = re.compile(r"^@@SCAN:(\w+):(\d+)@@$")
_TOTAL_RE = re.compile(r"^@@TOTAL:(\d+)@@$")
_FOLDER_START_RE = re.compile(r"^@@FOLDER_START:(\w+)@@$")
_FOLDER_DONE_RE = re.compile(r"^@@FOLDER_DONE:(\w+)@@$")
_VERIFY_RE = re.compile(r"^@@VERIFY:(\w+):(\d+):(\d+)@@$")
_VERIFY_START_RE = re.compile(r"^@@VERIFY_START@@$")
_VERIFY_DONE_RE = re.compile(r"^@@VERIFY_DONE@@$")


def _format_bytes(n: int | float) -> str:
    """Human-friendly byte size (e.g. 1.23 GB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


class MigrationProgress:
    """Track transfer progress across multiple folders."""

    def __init__(self) -> None:
        self.folder_sizes: dict[str, int] = {}
        self.total_bytes: int = 0
        self.completed_folders: list[str] = []
        self.current_folder: str | None = None
        self.current_pct: int = 0
        self.current_speed: str = ""
        self.current_eta: str = ""
        self._start_time: float | None = None

    @property
    def bytes_completed(self) -> int:
        """Estimated bytes transferred so far."""
        done = sum(self.folder_sizes.get(f, 0) for f in self.completed_folders)
        if self.current_folder and self.current_folder in self.folder_sizes:
            cur_size = self.folder_sizes[self.current_folder]
            done += int(cur_size * self.current_pct / 100)
        return done

    @property
    def overall_pct(self) -> float:
        if self.total_bytes <= 0:
            return 0.0
        return min(100.0, self.bytes_completed / self.total_bytes * 100)

    @property
    def elapsed_seconds(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def eta_display(self) -> str:
        """Rough wall-clock ETA based on overall progress."""
        pct = self.overall_pct
        elapsed = self.elapsed_seconds
        if pct <= 0 or elapsed <= 0:
            return "estimating..."
        remaining = elapsed / pct * (100 - pct)
        return _format_duration(remaining)

    def start(self) -> None:
        self._start_time = time.monotonic()

    def summary_line(self) -> str:
        """One-line progress summary for the UI."""
        done = _format_bytes(self.bytes_completed)
        total = _format_bytes(self.total_bytes)
        pct = self.overall_pct
        eta = self.eta_display
        folder = self.current_folder or "—"
        parts = [
            f"{done} / {total}",
            f"{pct:.1f}%",
        ]
        if self.current_speed:
            parts.append(self.current_speed)
        parts.append(f"~{eta} remaining")
        parts.append(f"[dim]{folder}[/dim]")
        return "  ".join(parts)


def _format_duration(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    s = int(seconds)
    if s < 0:
        return "0:00"
    h, remainder = divmod(s, 3600)
    m, sec = divmod(remainder, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


class DataMigrationScreen(Screen):
    """Set up SSH to source host, then pull user data folders via rsync."""

    BINDINGS = [
        ("escape", "go_back", "Back"),
        ("q", "app.quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._log_file = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Data Migration[/bold]\n\n"
                "Copy user data folders from another machine via rsync/SSH.\n"
                "[dim]Folders: Desktop, Documents, Downloads, Movies, "
                "Music, Pictures, Videos[/dim]\n\n"
                "Enter the hostname or IP of the source machine.",
                id="migration-status",
            )
            yield Input(
                placeholder="hostname or IP (e.g. desktop, 192.168.1.50)",
                id="source-host",
            )
            yield Static("", id="migration-error")
            with Horizontal(id="migration-buttons"):
                yield Button(
                    "Check Connection", id="check-conn", variant="warning"
                )
                yield Button(
                    "Copy SSH Key", id="copy-key", disabled=True
                )
                yield Button(
                    "Preview (Dry Run)",
                    id="dry-run",
                    variant="default",
                    disabled=True,
                )
                yield Button(
                    "Start Migration",
                    id="start",
                    variant="primary",
                    disabled=True,
                )
            yield Static("", id="progress-summary")
            yield ProgressBar(id="migration-progress", show_eta=False)
            yield RichLog(
                id="migration-output", highlight=True, markup=True, wrap=True
            )
            with Horizontal(id="migration-done-buttons"):
                yield Button(
                    "Done", id="done", variant="primary", disabled=True
                )
                yield Button(
                    "Import Settings", id="import-settings", disabled=True
                )
                yield Button(
                    "Send Log", id="send-log", disabled=True
                )
        yield Footer()

    def on_mount(self) -> None:
        self._procs: list[subprocess.Popen] = []
        self.query_one("#migration-output", RichLog).display = False
        self.query_one("#migration-progress", ProgressBar).display = False
        self.query_one("#progress-summary", Static).display = False
        self.query_one("#migration-done-buttons", Horizontal).display = False
        if self.app.platform != "macos":
            self.query_one("#import-settings", Button).display = False
        self._progress = MigrationProgress()
        # Restore previously-entered host.
        if _SAVED_HOST_FILE.exists():
            saved = _SAVED_HOST_FILE.read_text().strip()
            if saved:
                self.query_one("#source-host", Input).value = saved

    def on_unmount(self) -> None:
        terminate_procs(self._procs)
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Enter key checks connection."""
        self._run_check()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "check-conn":
            self._run_check()
        elif event.button.id == "copy-key":
            self._run_copy_key()
        elif event.button.id == "dry-run":
            self._start_migration(dry_run=True)
        elif event.button.id == "start":
            self._start_migration(dry_run=False)
        elif event.button.id == "done":
            self.app.pop_screen()
        elif event.button.id == "import-settings":
            self._do_import_settings()
        elif event.button.id == "send-log":
            self._send_log()

    # ------------------------------------------------------------------
    # Check connection
    # ------------------------------------------------------------------

    def _run_check(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._disable_all()
        output = self.query_one("#migration-output", RichLog)
        output.clear()
        output.display = True
        self._check_connection(host)

    @work(thread=True)
    def _check_connection(self, host: str) -> None:
        """Generate SSH key if needed, test connectivity, check rsync."""
        # Step 1: Local SSH key
        if SSH_KEY_PATH.exists():
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] SSH key exists: "
                f"[dim]{SSH_KEY_PATH}[/dim]",
            )
        else:
            self.app.call_from_thread(
                self._log,
                "[yellow]No SSH key found. "
                "Generating ed25519 key...[/yellow]",
            )
            result = subprocess.run(
                [
                    "ssh-keygen", "-t", "ed25519",
                    "-f", str(SSH_KEY_PATH),
                    "-N", "",
                    "-C", f"{os.environ.get('USER', 'user')}"
                           f"@{_local_hostname()}",
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                self.app.call_from_thread(
                    self._log,
                    f"[bold red]ssh-keygen failed:[/bold red]\n"
                    f"{result.stderr.strip()}",
                )
                self.app.call_from_thread(self._enable_check)
                return
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] Generated SSH key: "
                f"[dim]{SSH_KEY_PATH}[/dim]",
            )

        # Step 2: Test key auth
        self.app.call_from_thread(
            self._log,
            f"\nTesting SSH key auth to [bold]{host}[/bold]...",
        )
        if _ssh_key_auth_works(host):
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] SSH key auth works.",
            )
        else:
            self.app.call_from_thread(
                self._log,
                "[yellow]\u2717 Key auth not configured.[/yellow]\n"
                "Use [bold]Copy SSH Key[/bold] to send your public "
                "key to the source machine.\n"
                "[dim]This will drop to the terminal so you can "
                "type the remote password.[/dim]",
            )
            self.app.call_from_thread(self._enable_copy_key)
            return

        # Step 3: Check local rsync version (need 3.1+ for --info=progress2)
        self.app.call_from_thread(
            self._log,
            "Checking local rsync version...",
        )
        if not _local_rsync_ok():
            self.app.call_from_thread(
                self._log,
                "[bold red]rsync 3.1+ required[/bold red] "
                "(macOS ships an old 2.6.x build).\n"
                "Install a modern rsync:\n"
                "  [dim]brew install rsync[/dim]",
            )
            self.app.call_from_thread(self._enable_check)
            return
        self.app.call_from_thread(
            self._log,
            "[green]\u2713[/green] Local rsync is 3.1+.",
        )

        # Step 4: Check rsync on remote
        self.app.call_from_thread(
            self._log,
            f"Checking rsync on [bold]{host}[/bold]...",
        )
        if _remote_has_rsync(host):
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] rsync available on {host}.",
            )
        else:
            self.app.call_from_thread(
                self._log,
                f"[bold red]rsync not found on {host}.[/bold red]\n"
                "Install rsync on the source machine:\n"
                "  [dim]sudo apt install rsync[/dim]  (Debian/Ubuntu)\n"
                "  [dim]brew install rsync[/dim]       (macOS)",
            )
            self.app.call_from_thread(self._enable_check)
            return

        # Step 5: Scan remote folder sizes
        self.app.call_from_thread(
            self._log,
            f"\nScanning remote folder sizes on [bold]{host}[/bold]...",
        )
        scan = _scan_remote_sizes(host)
        if scan:
            total = 0
            for folder, size in scan.items():
                total += size
                self.app.call_from_thread(
                    self._log,
                    f"  {folder}: {_format_bytes(size)}",
                )
            self.app.call_from_thread(
                self._log,
                f"\n[bold]Total remote data: {_format_bytes(total)}[/bold]",
            )
            # Pre-fill progress state for migration.
            self._progress.folder_sizes = scan
            self._progress.total_bytes = total
        else:
            self.app.call_from_thread(
                self._log,
                "[yellow]Could not scan remote sizes "
                "(progress estimation will be limited).[/yellow]",
            )

        # All green
        self.app.call_from_thread(
            self._log,
            "\n[bold green]Connection ready![/bold green]",
        )
        self.app.call_from_thread(self._enable_pull)

    # ------------------------------------------------------------------
    # Copy SSH key (suspend Textual -> real terminal)
    # ------------------------------------------------------------------

    def _run_copy_key(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._disable_all()
        self._suspend_for_ssh_copy_id(host)

    @work(thread=True)
    def _suspend_for_ssh_copy_id(self, host: str) -> None:
        """Suspend Textual, run ssh-copy-id interactively, resume."""
        done = threading.Event()

        def _do_copy() -> None:
            with self.app.suspend():
                print(
                    "\n"
                    "  ┌─────────────────────────────────────────┐\n"
                    "  │  Copying SSH key to remote machine       │\n"
                    "  └─────────────────────────────────────────┘\n"
                    f"\n  Host: {host}\n"
                    f"  Key:  {SSH_KEY_PATH}.pub\n"
                )
                subprocess.run(
                    ["ssh-copy-id", "-i", str(SSH_KEY_PATH), host],
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
                input("\n  Press Enter to return to the setup wizard...")
            done.set()

        self.app.call_from_thread(_do_copy)
        done.wait()

        # Back in Textual — verify it worked
        self.app.call_from_thread(
            self._log,
            "\n[dim]Verifying key auth after copy...[/dim]",
        )
        if _ssh_key_auth_works(host):
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] SSH key auth to {host} works!",
            )
            # Still need to check rsync
            self.app.call_from_thread(
                self._log,
                f"Checking rsync on [bold]{host}[/bold]...",
            )
            if _remote_has_rsync(host):
                self.app.call_from_thread(
                    self._log,
                    f"[green]\u2713[/green] rsync available on {host}.",
                )
                self.app.call_from_thread(
                    self._log,
                    "\n[bold green]Connection ready![/bold green]",
                )
                self.app.call_from_thread(self._enable_pull)
            else:
                self.app.call_from_thread(
                    self._log,
                    f"[bold red]rsync not found on {host}.[/bold red]\n"
                    "Install rsync on the source, then re-check.",
                )
                self.app.call_from_thread(self._enable_check)
        else:
            self.app.call_from_thread(
                self._log,
                "[yellow]Key auth still not working.[/yellow]\n"
                "Try again, or manually run:\n"
                f"  [dim]ssh-copy-id {host}[/dim]",
            )
            self.app.call_from_thread(self._enable_copy_key)

    # ------------------------------------------------------------------
    # Data pull
    # ------------------------------------------------------------------

    def _start_migration(self, *, dry_run: bool) -> None:
        host = self._get_host()
        if not host:
            return

        self._disable_all()
        output = self.query_one("#migration-output", RichLog)
        output.clear()
        output.display = True

        # Open (or reopen) the migration log file.
        self._open_log_file()

        mode_label = "DRY RUN" if dry_run else "MIGRATION"
        self._log(
            f"[bold cyan]>>> {mode_label}: "
            f"Copying user folders from {host}[/bold cyan]\n"
        )

        # Reset progress state
        self._progress = MigrationProgress()
        bar = self.query_one("#migration-progress", ProgressBar)
        bar.update(total=100, progress=0)
        bar.display = not dry_run
        self.query_one("#progress-summary", Static).display = not dry_run

        self._run_data_pull(host, dry_run)

    @work(thread=True)
    def _run_data_pull(self, host: str, dry_run: bool) -> None:
        """Run data-pull.sh in a background thread with streaming output."""
        cmd = ["bash", str(DATA_PULL_SCRIPT), host]
        if dry_run:
            cmd.append("--dry-run")

        env = os.environ.copy()
        env["PATH"] = _brew_path()

        progress = self._progress

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
            )
            self._procs.append(proc)
            try:
                for raw_line in proc.stdout:
                    stripped = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    self._handle_output_line(stripped, progress, dry_run)
                proc.wait()
            finally:
                if proc in self._procs:
                    self._procs.remove(proc)

            if proc.returncode == 0:
                if dry_run:
                    self.app.call_from_thread(
                        self._log,
                        "\n[bold green]Dry run complete.[/bold green] "
                        "Review above, then press "
                        "[bold]Start Migration[/bold] to copy for real.",
                    )
                else:
                    # Set progress to 100%
                    self.app.call_from_thread(self._set_progress, 100.0)
                    self.app.call_from_thread(
                        self._update_summary,
                        f"{_format_bytes(progress.total_bytes)} / "
                        f"{_format_bytes(progress.total_bytes)}  "
                        f"100.0%  "
                        f"completed in {_format_duration(progress.elapsed_seconds)}",
                    )
                    self.app.call_from_thread(
                        self._log,
                        "\n[bold green]Migration complete![/bold green] "
                        "Your user folders have been copied.",
                    )
            else:
                self.app.call_from_thread(
                    self._log,
                    f"\n[bold red]Migration failed[/bold red] "
                    f"(exit code {proc.returncode}).\n"
                    "Check the output above for errors.",
                )
        except Exception as exc:
            logger.exception("Data migration failed")
            self.app.call_from_thread(
                self._log, f"\n[bold red]Error:[/bold red] {exc}"
            )

        self.app.call_from_thread(self._enable_pull)
        self.app.call_from_thread(self._show_done_buttons)

    def _handle_output_line(
        self, line: str, progress: MigrationProgress, dry_run: bool,
    ) -> None:
        """Parse a single output line for structured markers or progress."""
        # Scan markers
        m = _SCAN_RE.match(line)
        if m:
            folder, size_str = m.group(1), m.group(2)
            size = int(size_str)
            progress.folder_sizes[folder] = size
            human = _format_bytes(size)
            self.app.call_from_thread(
                self._log, f"  {folder}: {human}"
            )
            return

        m = _TOTAL_RE.match(line)
        if m:
            progress.total_bytes = int(m.group(1))
            human = _format_bytes(progress.total_bytes)
            self.app.call_from_thread(
                self._log,
                f"\n[bold]Total remote data: {human}[/bold]\n",
            )
            return

        m = _FOLDER_START_RE.match(line)
        if m:
            folder = m.group(1)
            progress.current_folder = folder
            progress.current_pct = 0
            progress.current_speed = ""
            progress.current_eta = ""
            if progress._start_time is None:
                progress.start()
            return

        m = _FOLDER_DONE_RE.match(line)
        if m:
            folder = m.group(1)
            if folder not in progress.completed_folders:
                progress.completed_folders.append(folder)
            progress.current_pct = 0
            if not dry_run:
                self.app.call_from_thread(
                    self._set_progress, progress.overall_pct
                )
                self.app.call_from_thread(
                    self._update_summary, progress.summary_line()
                )
            return

        # rsync --info=progress2 lines (only during real transfers)
        if not dry_run:
            m = _PROGRESS2_RE.match(line)
            if m:
                progress.current_pct = int(m.group("pct"))
                progress.current_speed = m.group("speed")
                progress.current_eta = m.group("eta")
                self.app.call_from_thread(
                    self._set_progress, progress.overall_pct
                )
                self.app.call_from_thread(
                    self._update_summary, progress.summary_line()
                )
                return

        # Verification markers
        if _VERIFY_START_RE.match(line):
            self.app.call_from_thread(
                self._log,
                "\n[bold cyan]Verifying migrated data...[/bold cyan]",
            )
            return

        m = _VERIFY_RE.match(line)
        if m:
            folder = m.group(1)
            local_bytes = int(m.group(2))
            remote_bytes = int(m.group(3))
            local_h = _format_bytes(local_bytes)
            remote_h = _format_bytes(remote_bytes)
            # Allow 5% tolerance (du rounding, excludes, etc.)
            if remote_bytes == 0:
                icon = "[dim]—[/dim]"
                note = "empty on remote"
            elif local_bytes >= remote_bytes * 0.95:
                icon = "[green]\u2713[/green]"
                note = ""
            elif local_bytes >= remote_bytes * 0.80:
                icon = "[yellow]~[/yellow]"
                note = " [yellow](partial)[/yellow]"
            else:
                icon = "[red]\u2717[/red]"
                note = " [red](incomplete)[/red]"
            self.app.call_from_thread(
                self._log,
                f"  {icon} {folder}: {local_h} local / "
                f"{remote_h} remote{note}",
            )
            return

        if _VERIFY_DONE_RE.match(line):
            return

        # Regular output — show in log
        self.app.call_from_thread(self._log_output, line)

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

    def _get_host(self) -> str | None:
        """Return validated hostname or show error and return None."""
        host = self.query_one("#source-host", Input).value.strip()
        if not host:
            self.query_one("#migration-error", Static).update(
                "[red]Please enter a hostname or IP address.[/red]"
            )
            return None
        self.query_one("#migration-error", Static).update("")
        _SAVED_HOST_FILE.write_text(host)
        return host

    def _open_log_file(self) -> None:
        """Open the migration log file, creating the directory if needed."""
        if self._log_file and not self._log_file.closed:
            self._log_file.close()
        MIGRATION_LOG.parent.mkdir(parents=True, exist_ok=True)
        self._log_file = open(MIGRATION_LOG, "w")

    def _log(self, text: str) -> None:
        """Write a Rich-markup line to the RichLog widget and log file."""
        import re

        self.query_one("#migration-output", RichLog).write(text)

        if self._log_file and not self._log_file.closed:
            plain = re.sub(r"\[/?[^\]]*\]", "", text)
            self._log_file.write(plain + "\n")
            self._log_file.flush()

    def _log_output(self, text: str) -> None:
        """Write subprocess output verbatim (no Rich markup parsing)."""
        from rich.text import Text

        self.query_one("#migration-output", RichLog).write(Text(text))

        if self._log_file and not self._log_file.closed:
            self._log_file.write(text + "\n")
            self._log_file.flush()

    def _set_progress(self, pct: float) -> None:
        bar = self.query_one("#migration-progress", ProgressBar)
        bar.update(total=100, progress=pct)

    def _update_summary(self, text: str) -> None:
        self.query_one("#progress-summary", Static).update(text)

    def _disable_all(self) -> None:
        self.query_one("#check-conn", Button).disabled = True
        self.query_one("#copy-key", Button).disabled = True
        self.query_one("#dry-run", Button).disabled = True
        self.query_one("#start", Button).disabled = True

    def _enable_check(self) -> None:
        """Only check-connection is available (setup not done)."""
        self.query_one("#check-conn", Button).disabled = False
        self.query_one("#source-host", Input).disabled = False

    def _enable_copy_key(self) -> None:
        """SSH key exists but not on remote — offer copy."""
        self.query_one("#check-conn", Button).disabled = False
        self.query_one("#copy-key", Button).disabled = False
        self.query_one("#source-host", Input).disabled = False

    def _enable_pull(self) -> None:
        """Connection verified — enable migration buttons."""
        self.query_one("#check-conn", Button).disabled = False
        self.query_one("#dry-run", Button).disabled = False
        self.query_one("#start", Button).disabled = False
        self.query_one("#source-host", Input).disabled = False

    def _show_done_buttons(self) -> None:
        """Show Done, Import Settings, and Send Log buttons after migration completes."""
        row = self.query_one("#migration-done-buttons", Horizontal)
        row.display = True
        self.query_one("#done", Button).disabled = False
        self.query_one("#import-settings", Button).disabled = False
        self.query_one("#send-log", Button).disabled = False

    def _do_import_settings(self) -> None:
        """Import iTerm2 + Raycast settings (macOS only)."""
        self.query_one("#import-settings", Button).disabled = True
        self._log("[bold cyan]>>> Importing settings...[/bold cyan]\n")
        self._import_settings_worker()

    @work(thread=True)
    def _import_settings_worker(self) -> None:
        """Run all imports, suspending for interactive confirm dialogs."""
        try:
            messages, confirmations = run_all_imports(self.app.runner)
            for msg in messages:
                self.app.call_from_thread(self._log, f"  {msg}")

            for prompt, cleanup_fn in confirmations:
                done = threading.Event()

                def _do_confirm(p: str = prompt) -> None:
                    with self.app.suspend():
                        input(f"\n  {p}, then press Enter to continue...")
                    done.set()

                self.app.call_from_thread(_do_confirm)
                done.wait()
                cleanup_fn()
                self.app.call_from_thread(
                    self._log, f"  {prompt.split(' in ')[0]} confirmed."
                )

            self.app.call_from_thread(
                self._log,
                "\n[bold green]Settings import complete.[/bold green]\n",
            )
        except Exception as exc:
            logger.exception("Settings import failed")
            self.app.call_from_thread(
                self._log,
                f"\n[bold red]Import failed:[/bold red] {exc}\n",
            )
        finally:
            self.app.call_from_thread(
                setattr,
                self.query_one("#import-settings", Button),
                "disabled", False,
            )

    @work(thread=True)
    def _send_log(self) -> None:
        """Send migration.log via Magic Wormhole."""
        if not MIGRATION_LOG.exists():
            self.app.call_from_thread(
                self._log,
                "[bold red]No migration.log found.[/bold red]",
            )
            return

        send_btn = self.query_one("#send-log", Button)
        self.app.call_from_thread(setattr, send_btn, "disabled", True)
        self.app.call_from_thread(
            self._log,
            "\n[bold cyan]>>> Sending migration.log via Magic Wormhole...[/bold cyan]\n",
        )

        try:
            proc = subprocess.Popen(
                [
                    "uv", "run", "--with", "magic-wormhole",
                    "wormhole", "send", str(MIGRATION_LOG),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env={**os.environ, "PATH": f"{Path.home() / '.local/bin'}:{os.environ.get('PATH', '')}"},
            )
            self._procs.append(proc)
            try:
                for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
                    self.app.call_from_thread(self._log_output, line)
                proc.wait()
            finally:
                if proc in self._procs:
                    self._procs.remove(proc)
            if proc.returncode == 0:
                self.app.call_from_thread(
                    self._log,
                    "\n[bold green]Log sent successfully.[/bold green]\n",
                )
            else:
                self.app.call_from_thread(
                    self._log,
                    "\n[bold red]Failed to send log.[/bold red]\n",
                )
        except Exception as exc:
            logger.exception("Failed to send migration log")
            self.app.call_from_thread(
                self._log,
                f"\n[bold red]Failed to send log:[/bold red] {exc}\n",
            )
        finally:
            self.app.call_from_thread(setattr, send_btn, "disabled", False)


# ------------------------------------------------------------------
# Helpers (no UI dependency)
# ------------------------------------------------------------------


def _brew_path() -> str:
    """Return PATH with Homebrew and ~/.local/bin prepended."""
    base = os.environ.get("PATH", "")
    extra = [str(Path.home() / ".local" / "bin"), "/opt/homebrew/bin"]
    return ":".join(extra + [base])


def _local_hostname() -> str:
    import socket
    return socket.gethostname()


def _ssh_key_auth_works(host: str) -> bool:
    result = subprocess.run(
        [
            "ssh", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5", host, "true",
        ],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _local_rsync_ok() -> bool:
    """Check that the local rsync supports --info=progress2 (requires 3.1+)."""
    result = subprocess.run(
        ["rsync", "--version"],
        capture_output=True, text=True,
        env={**os.environ, "PATH": _brew_path()},
    )
    if result.returncode != 0:
        return False
    # First line looks like: "rsync  version 3.2.7  protocol version 31"
    m = re.search(r"version\s+(\d+)\.(\d+)", result.stdout)
    if not m:
        return False
    major, minor = int(m.group(1)), int(m.group(2))
    return (major, minor) >= (3, 1)


def _remote_has_rsync(host: str) -> bool:
    result = subprocess.run(
        [
            "ssh", "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            host, "command -v rsync",
        ],
        capture_output=True, text=True,
    )
    return result.returncode == 0


def _scan_remote_sizes(host: str) -> dict[str, int] | None:
    """Run data-pull.sh --scan-only and parse the @@SCAN markers."""
    result = subprocess.run(
        ["bash", str(DATA_PULL_SCRIPT), host, "--scan-only"],
        capture_output=True, text=True,
        env={**os.environ, "PATH": _brew_path()},
    )
    if result.returncode != 0:
        return None
    sizes: dict[str, int] = {}
    for line in result.stdout.splitlines():
        m = _SCAN_RE.match(line)
        if m:
            sizes[m.group(1)] = int(m.group(2))
    return sizes if sizes else None
