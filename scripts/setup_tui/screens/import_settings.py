"""ImportSettingsScreen — re-import iTerm2 + OpenIn + Raycast + Stream Deck settings."""

from __future__ import annotations

import logging
import threading

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, RichLog, SelectionList, Static

from ..lib.defaults import IMPORT_ITEMS, get_cleanup_fn, get_import_fn

logger = logging.getLogger("setup")


class ImportSettingsScreen(Screen):
    """Import app settings with a selectable checklist."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Import Settings[/bold]\n\n"
                "Select which app settings to re-import from the repo.\n",
                id="import-status",
            )
            yield SelectionList[str](
                *[
                    (item["label"], item["id"], True)
                    for item in IMPORT_ITEMS
                ],
                id="import-checklist",
            )
            yield RichLog(
                id="import-output", highlight=True, markup=True, wrap=True
            )
            with Horizontal(id="import-buttons"):
                yield Button(
                    "Import Selected", id="run-import", variant="primary"
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
        checklist = self.query_one("#import-checklist", SelectionList)
        selected_ids = list(checklist.selected)
        if not selected_ids:
            output = self.query_one("#import-output", RichLog)
            output.clear()
            output.display = True
            self._log("[bold yellow]No items selected.[/bold yellow]")
            return
        self.query_one("#run-import", Button).disabled = True
        output = self.query_one("#import-output", RichLog)
        output.clear()
        output.display = True
        self._log("[bold cyan]>>> Importing settings...[/bold cyan]\n")
        self._import_worker(selected_ids)

    @work(thread=True)
    def _import_worker(self, selected_ids: list[str]) -> None:
        """Run selected imports, suspending for interactive confirm dialogs."""
        selected = [i for i in IMPORT_ITEMS if i["id"] in selected_ids]
        try:
            # --- Non-interactive imports first ---
            for item in selected:
                if item["interactive"]:
                    continue
                try:
                    fn = get_import_fn(item)
                    msg = fn(self.app.runner)
                    self.app.call_from_thread(self._log, f"  {msg}")
                except Exception as exc:
                    self.app.call_from_thread(
                        self._log,
                        f"  [red]{item['label']} import failed:[/red] {exc}",
                    )

            # --- Interactive imports (need user confirmation) ---
            for item in selected:
                if not item["interactive"]:
                    continue
                try:
                    fn = get_import_fn(item)
                    msg, needs_confirm = fn(self.app.runner)
                    self.app.call_from_thread(self._log, f"  {msg}")

                    if needs_confirm:
                        done = threading.Event()
                        prompt = item["confirm_prompt"]

                        def _do_confirm(p: str = prompt) -> None:
                            with self.app.suspend():
                                input(f"\n  {p}, then press Enter to continue...")
                            done.set()

                        self.app.call_from_thread(_do_confirm)
                        done.wait()
                        get_cleanup_fn(item)()
                        self.app.call_from_thread(
                            self._log,
                            f"  {item['label']} import confirmed.",
                        )
                except Exception as exc:
                    self.app.call_from_thread(
                        self._log,
                        f"  [red]{item['label']} import failed:[/red] {exc}",
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
