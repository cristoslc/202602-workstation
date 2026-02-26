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

USER_FOLDERS = ["Documents", "Pictures", "Music", "Videos", "Downloads"]


class DataMigrationScreen(Screen):
    """Collect a source hostname and run data-pull.sh to migrate user folders."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Data Migration[/bold]\n\n"
                "Copy user data folders from another machine via rsync/SSH.\n"
                "[dim]Folders: Documents, Pictures, Music, Videos, Downloads[/dim]\n\n"
                "Enter the hostname or IP of the source machine.\n"
                "SSH key auth must already be configured.\n"
                "[dim]Enter to submit, or Tab to reach buttons[/dim]",
                id="migration-status",
            )
            yield Input(
                placeholder="hostname or IP (e.g. desktop, 192.168.1.50)",
                id="source-host",
            )
            yield Static("", id="migration-error")
            with Horizontal(id="migration-buttons"):
                yield Button(
                    "Preview (Dry Run)", id="dry-run", variant="default"
                )
                yield Button(
                    "Start Migration", id="start", variant="primary"
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
        """Enter key in the input field starts a dry run by default."""
        self._start_migration(dry_run=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "dry-run":
            self._start_migration(dry_run=True)
        elif event.button.id == "start":
            self._start_migration(dry_run=False)

    def _start_migration(self, *, dry_run: bool) -> None:
        host = self.query_one("#source-host", Input).value.strip()
        if not host:
            self.query_one("#migration-error", Static).update(
                "[red]Please enter a hostname or IP address.[/red]"
            )
            return

        self.query_one("#migration-error", Static).update("")
        self.query_one("#source-host", Input).disabled = True
        self.query_one("#dry-run", Button).disabled = True
        self.query_one("#start", Button).disabled = True

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
                stripped = line.rstrip("\n")
                self.app.call_from_thread(self._log_output, stripped)

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

        self.app.call_from_thread(self._re_enable_controls)

    def _log(self, text: str) -> None:
        """Write a Rich-markup line to the output widget."""
        self.query_one("#migration-output", RichLog).write(text)

    def _log_output(self, text: str) -> None:
        """Write subprocess output verbatim (no markup parsing)."""
        from rich.text import Text

        self.query_one("#migration-output", RichLog).write(Text(text))

    def _re_enable_controls(self) -> None:
        """Re-enable input and buttons after migration finishes."""
        self.query_one("#source-host", Input).disabled = False
        self.query_one("#dry-run", Button).disabled = False
        self.query_one("#start", Button).disabled = False
