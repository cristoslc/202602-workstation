"""DataMigrationScreen — bulk-copy user data folders from another machine."""

from __future__ import annotations

import logging
import os
import subprocess
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
    RichLog,
    Static,
)

from ..lib.runner import REPO_ROOT

logger = logging.getLogger("setup")

DATA_PULL_SCRIPT = REPO_ROOT / "scripts" / "data-pull.sh"
SSH_KEY_PATH = Path.home() / ".ssh" / "id_ed25519"


class DataMigrationScreen(Screen):
    """Set up SSH to source host, then pull user data folders via rsync."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Data Migration[/bold]\n\n"
                "Copy user data folders from another machine via rsync/SSH.\n"
                "[dim]Folders: Documents, Pictures, Music, Videos, Downloads"
                "[/dim]\n\n"
                "Enter the hostname or IP of the source machine, then set up\n"
                "the connection before pulling data.",
                id="migration-status",
            )
            yield Input(
                placeholder="hostname or IP (e.g. desktop, 192.168.1.50)",
                id="source-host",
            )
            yield Static("", id="migration-error")
            with Horizontal(id="migration-buttons"):
                yield Button(
                    "Setup Connection", id="setup-conn", variant="warning"
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
            yield RichLog(
                id="migration-output", highlight=True, markup=True, wrap=True
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#migration-output", RichLog).display = False
        self._host_verified = False

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        """Enter key triggers setup if not yet verified, dry-run otherwise."""
        if self._host_verified:
            self._start_migration(dry_run=True)
        else:
            self._run_setup()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "setup-conn":
            self._run_setup()
        elif event.button.id == "dry-run":
            self._start_migration(dry_run=True)
        elif event.button.id == "start":
            self._start_migration(dry_run=False)

    # ------------------------------------------------------------------
    # Connection setup
    # ------------------------------------------------------------------

    def _run_setup(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._disable_all_buttons()
        output = self.query_one("#migration-output", RichLog)
        output.clear()
        output.display = True
        output.write("[bold cyan]>>> Setting up connection...[/bold cyan]\n")
        self._setup_connection(host)

    @work(thread=True)
    def _setup_connection(self, host: str) -> None:
        """Check/generate SSH key, copy to remote, verify connectivity."""
        # Step 1: Local SSH key
        if SSH_KEY_PATH.exists():
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] SSH key exists: {SSH_KEY_PATH}",
            )
        else:
            self.app.call_from_thread(
                self._log,
                "[yellow]No SSH key found. Generating ed25519 key...[/yellow]",
            )
            result = subprocess.run(
                [
                    "ssh-keygen",
                    "-t", "ed25519",
                    "-f", str(SSH_KEY_PATH),
                    "-N", "",  # no passphrase
                    "-C", f"{os.environ.get('USER', 'user')}@{_local_hostname()}",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.app.call_from_thread(
                    self._log,
                    f"[bold red]ssh-keygen failed:[/bold red]\n"
                    f"{result.stderr.strip()}",
                )
                self.app.call_from_thread(self._re_enable_controls)
                return
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] Generated SSH key: {SSH_KEY_PATH}",
            )

        # Step 2: Test if key auth already works
        self.app.call_from_thread(
            self._log,
            f"\nTesting SSH key auth to [bold]{host}[/bold]...",
        )
        if _ssh_key_auth_works(host):
            self.app.call_from_thread(
                self._log,
                f"[green]\u2713[/green] SSH key auth to {host} works!",
            )
        else:
            # Key auth doesn't work — try ssh-copy-id
            self.app.call_from_thread(
                self._log,
                "[yellow]Key auth not configured. "
                "Running ssh-copy-id...[/yellow]\n"
                "[dim]You may be prompted for the remote password.[/dim]",
            )
            copy_ok = self._run_ssh_copy_id(host)
            if not copy_ok:
                self.app.call_from_thread(
                    self._log,
                    "\n[bold red]ssh-copy-id failed.[/bold red]\n"
                    "Manually copy your public key to the source:\n"
                    f"  [dim]ssh-copy-id {host}[/dim]",
                )
                self.app.call_from_thread(self._re_enable_controls)
                return
            # Verify it actually worked
            if _ssh_key_auth_works(host):
                self.app.call_from_thread(
                    self._log,
                    f"[green]\u2713[/green] SSH key auth to {host} "
                    "now works!",
                )
            else:
                self.app.call_from_thread(
                    self._log,
                    "\n[bold red]Key auth still failing after "
                    "ssh-copy-id.[/bold red]\n"
                    "Check that the source machine accepts key auth.",
                )
                self.app.call_from_thread(self._re_enable_controls)
                return

        # Step 3: Check rsync on remote
        self.app.call_from_thread(
            self._log, f"\nChecking rsync on [bold]{host}[/bold]..."
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
            self.app.call_from_thread(self._re_enable_controls)
            return

        # All checks passed
        self.app.call_from_thread(
            self._log,
            "\n[bold green]Connection ready![/bold green] "
            "Use [bold]Preview[/bold] to see what will transfer, "
            "then [bold]Start Migration[/bold] to copy.",
        )
        self.app.call_from_thread(self._mark_verified)

    def _run_ssh_copy_id(self, host: str) -> bool:
        """Run ssh-copy-id, streaming output so the user sees the prompt."""
        try:
            proc = subprocess.Popen(
                ["ssh-copy-id", "-i", str(SSH_KEY_PATH), host],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                # stdin is inherited so the user can type the password
            )
            for line in proc.stdout:
                self.app.call_from_thread(
                    self._log_output, line.rstrip("\n")
                )
            proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            self.app.call_from_thread(
                self._log,
                "[red]ssh-copy-id not found on this machine.[/red]",
            )
            return False

    def _mark_verified(self) -> None:
        """Enable pull buttons after successful connection setup."""
        self._host_verified = True
        self.query_one("#setup-conn", Button).disabled = True
        self.query_one("#setup-conn", Button).label = "Connected \u2713"
        self.query_one("#dry-run", Button).disabled = False
        self.query_one("#start", Button).disabled = False
        self.query_one("#source-host", Input).disabled = True

    # ------------------------------------------------------------------
    # Data pull
    # ------------------------------------------------------------------

    def _start_migration(self, *, dry_run: bool) -> None:
        host = self._get_host()
        if not host:
            return

        self._disable_all_buttons()
        output = self.query_one("#migration-output", RichLog)
        output.clear()
        output.display = True

        mode_label = "DRY RUN" if dry_run else "MIGRATION"
        output.write(
            f"[bold cyan]>>> {mode_label}: "
            f"Copying user folders from {host}[/bold cyan]\n"
        )

        self._run_data_pull(host, dry_run)

    @work(thread=True)
    def _run_data_pull(self, host: str, dry_run: bool) -> None:
        """Run data-pull.sh in a background thread with streaming output."""
        cmd = ["bash", str(DATA_PULL_SCRIPT), host]
        if dry_run:
            cmd.append("--dry-run")

        env = os.environ.copy()
        env["PATH"] = f"{Path.home()}/.local/bin:{env.get('PATH', '')}"

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )

            for line in proc.stdout:
                self.app.call_from_thread(
                    self._log_output, line.rstrip("\n")
                )

            proc.wait()

            if proc.returncode == 0:
                if dry_run:
                    self.app.call_from_thread(
                        self._log,
                        "\n[bold green]Dry run complete.[/bold green] "
                        "Review the output above, then press "
                        "[bold]Start Migration[/bold] to copy for real.",
                    )
                else:
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
                self._log,
                f"\n[bold red]Error:[/bold red] {exc}",
            )

        self.app.call_from_thread(self._re_enable_pull_buttons)

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
        return host

    def _log(self, text: str) -> None:
        """Write a Rich-markup line to the output widget."""
        self.query_one("#migration-output", RichLog).write(text)

    def _log_output(self, text: str) -> None:
        """Write subprocess output verbatim (no markup parsing)."""
        from rich.text import Text

        self.query_one("#migration-output", RichLog).write(Text(text))

    def _disable_all_buttons(self) -> None:
        self.query_one("#setup-conn", Button).disabled = True
        self.query_one("#dry-run", Button).disabled = True
        self.query_one("#start", Button).disabled = True

    def _re_enable_controls(self) -> None:
        """Re-enable setup button (connection not yet verified)."""
        self.query_one("#setup-conn", Button).disabled = False
        self.query_one("#source-host", Input).disabled = False

    def _re_enable_pull_buttons(self) -> None:
        """Re-enable pull buttons after a migration run."""
        self.query_one("#dry-run", Button).disabled = False
        self.query_one("#start", Button).disabled = False


# ------------------------------------------------------------------
# Helpers (no UI dependency)
# ------------------------------------------------------------------


def _local_hostname() -> str:
    """Best-effort local hostname for SSH key comment."""
    import socket

    return socket.gethostname()


def _ssh_key_auth_works(host: str) -> bool:
    """Test whether password-less SSH to *host* succeeds."""
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, "true"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _remote_has_rsync(host: str) -> bool:
    """Check if rsync is available on the remote host."""
    result = subprocess.run(
        [
            "ssh",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=5",
            host,
            "command -v rsync",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
