"""DataMigrationScreen — bulk-copy user data folders from another machine."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
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
                "[dim]Folders: Documents, Pictures, Music, Videos, "
                "Downloads[/dim]\n\n"
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
            yield RichLog(
                id="migration-output", highlight=True, markup=True, wrap=True
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#migration-output", RichLog).display = False

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

        # Step 3: Check rsync on remote
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

        # All green
        self.app.call_from_thread(
            self._log,
            "\n[bold green]Connection ready![/bold green]",
        )
        self.app.call_from_thread(self._enable_pull)

    # ------------------------------------------------------------------
    # Copy SSH key (suspend Textual → real terminal)
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
                        "Review above, then press "
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
                self._log, f"\n[bold red]Error:[/bold red] {exc}"
            )

        self.app.call_from_thread(self._enable_pull)

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
        self.query_one("#migration-output", RichLog).write(text)

    def _log_output(self, text: str) -> None:
        from rich.text import Text
        self.query_one("#migration-output", RichLog).write(Text(text))

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


# ------------------------------------------------------------------
# Helpers (no UI dependency)
# ------------------------------------------------------------------


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
