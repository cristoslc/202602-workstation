"""ImportSettingsScreen — re-import iTerm2 + Raycast settings on demand."""

from __future__ import annotations

import logging
import threading

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, Static

from ..lib.defaults import cleanup_raycast_import, run_all_imports

logger = logging.getLogger("setup")


class ImportSettingsScreen(Screen):
    """Import iTerm2 and Raycast settings outside of bootstrap/migration."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Import Settings[/bold]\n\n"
                "Re-import iTerm2 preferences and Raycast configuration\n"
                "from the repo into this machine.\n\n"
                "[dim]iTerm2: points preferences at the stow-managed plist[/dim]\n"
                "[dim]Raycast: decrypts the age-encrypted .rayconfig and "
                "opens the import dialog[/dim]",
                id="import-status",
            )
            yield RichLog(
                id="import-output", highlight=True, markup=True, wrap=True
            )
            with Horizontal(id="import-buttons"):
                yield Button(
                    "Import Settings", id="run-import", variant="primary"
                )
                yield Button("Back", id="back")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#import-output", RichLog).display = False

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "run-import":
            self._do_import()

    def _do_import(self) -> None:
        self.query_one("#run-import", Button).disabled = True
        output = self.query_one("#import-output", RichLog)
        output.clear()
        output.display = True
        self._log("[bold cyan]>>> Importing settings...[/bold cyan]\n")
        self._import_worker()

    @work(thread=True)
    def _import_worker(self) -> None:
        """Run all imports, suspending for Raycast dialog if needed."""
        try:
            messages, needs_raycast_confirm = run_all_imports(self.app.runner)
            for msg in messages:
                self.app.call_from_thread(self._log, f"  {msg}")

            if needs_raycast_confirm:
                done = threading.Event()

                def _do_confirm() -> None:
                    with self.app.suspend():
                        input(
                            "\n  Confirm the import in the Raycast dialog, "
                            "then press Enter to continue..."
                        )
                    done.set()

                self.app.call_from_thread(_do_confirm)
                done.wait()
                cleanup_raycast_import()
                self.app.call_from_thread(
                    self._log, "  Raycast import confirmed."
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
                self.query_one("#run-import", Button),
                "disabled", False,
            )

    def _log(self, text: str) -> None:
        self.query_one("#import-output", RichLog).write(text)
