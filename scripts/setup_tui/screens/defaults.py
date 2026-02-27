"""EditDefaultsScreen — edit action registry keybindings."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    SelectionList,
    Static,
)

from ..lib.defaults import (
    EXPORT_ITEMS,
    display_to_keybinding,
    get_export_fn,
    keybinding_to_display,
    load_action_registry,
    save_action_registry,
)
from ..lib.runner import REPO_ROOT

logger = logging.getLogger("setup")


class EditDefaultsScreen(Screen):
    """Edit keybindings from the action registry."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Edit Defaults[/bold]\n\n"
                "[dim]Loading action registry...[/dim]",
                id="defaults-status",
            )
            yield VerticalScroll(id="defaults-form")
            yield Static("", id="defaults-result")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#defaults-form").display = False
        self._actions: list[dict] = []
        self._load_actions()

    @work(thread=True)
    def _load_actions(self) -> None:
        """Load action registry in a background thread."""
        try:
            actions = load_action_registry()
        except Exception as exc:
            logger.warning("Failed to load action registry: %s", exc)
            self.app.call_from_thread(self._show_load_error, str(exc))
            return
        self.app.call_from_thread(self._populate, actions)

    def _populate(self, actions: list[dict]) -> None:
        """Build the keybinding form from loaded actions."""
        self._actions = actions
        form = self.query_one("#defaults-form", VerticalScroll)

        form.mount(
            Static(
                "[bold underline]Key Mappings[/bold underline]\n"
                "[dim]Meta = Cmd (macOS) / Super (Linux) — same physical key.[/dim]",
                classes="section-header",
            )
        )

        for action in actions:
            display = keybinding_to_display(action["keybinding"]["linux"])
            form.mount(
                Static(
                    f"[bold]{action['description']}[/bold]  "
                    f"[dim]{action['action']}[/dim]"
                )
            )
            form.mount(
                Input(
                    value=display,
                    placeholder="Meta+Shift+V",
                    id=f"bind-{action['action']}",
                )
            )

        # --- Export checklist (macOS only, hidden until toggled) ---
        if self.app.platform == "macos":
            form.mount(
                Static(
                    "\n[bold underline]Export Settings[/bold underline]",
                    id="export-header",
                )
            )
            form.mount(
                SelectionList[str](
                    *[
                        (item["label"], item["id"], True)
                        for item in EXPORT_ITEMS
                    ],
                    id="export-checklist",
                )
            )
            form.mount(
                Button(
                    "Export Selected", id="run-export", variant="warning"
                )
            )
            self.query_one("#export-header").display = False
            self.query_one("#export-checklist").display = False
            self.query_one("#run-export").display = False

        buttons = [
            Button("Save", id="save", variant="primary"),
        ]
        if self.app.platform == "macos":
            buttons.append(Button("Export Settings", id="export-settings"))
        buttons.append(Button("Back", id="back"))

        form.mount(Horizontal(*buttons, id="defaults-buttons"))

        macos_hint = ""
        if self.app.platform == "macos":
            macos_hint = (
                "[dim]macOS: use Export Settings to capture iTerm2 prefs, "
                "Raycast config, and Stream Deck profiles into the repo.[/dim]\n"
            )
        self.query_one("#defaults-status", Static).update(
            "[bold]Edit Defaults[/bold]\n\n"
            "Change keybindings below, then press Save.\n"
            "[dim]Format: Meta+Key or Meta+Shift+Key  "
            "(Meta = Cmd on macOS, Super on Linux)[/dim]\n"
            f"{macos_hint}"
            "[dim]Tab between fields, Enter to save, Escape to go back[/dim]"
        )
        form.display = True

    def _show_load_error(self, error: str) -> None:
        self.query_one("#defaults-status", Static).update(
            "[bold]Edit Defaults[/bold]\n\n"
            f"[red]Could not load action registry:[/red]\n"
            f"[dim]{error}[/dim]"
        )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._do_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "save":
            self._do_save()
        elif event.button.id == "export-settings":
            self._do_export_settings()
        elif event.button.id == "run-export":
            self._do_run_export()

    def _do_save(self) -> None:
        """Collect edited bindings and save the action registry."""
        errors: list[str] = []
        for action in self._actions:
            widget_id = f"bind-{action['action']}"
            val = self.query_one(f"#{widget_id}", Input).value.strip()
            if not val:
                errors.append(f"{action['action']}: empty binding")
                continue
            parts = [p.strip() for p in val.split("+")]
            if len(parts) < 2:
                errors.append(
                    f"{action['action']}: need at least Meta+Key"
                )
                continue
            try:
                new_binding = display_to_keybinding(val)
                action["keybinding"] = new_binding
            except Exception as exc:
                errors.append(f"{action['action']}: {exc}")

        if errors:
            self.query_one("#defaults-result", Static).update(
                "[bold red]Validation errors:[/bold red]\n"
                + "\n".join(f"  {e}" for e in errors)
            )
            return

        self.query_one("#save", Button).disabled = True
        self.query_one("#defaults-result", Static).update(
            "[dim]Saving...[/dim]"
        )
        self._save_worker()

    @work(thread=True)
    def _save_worker(self) -> None:
        """Write action registry in a background thread."""
        try:
            save_action_registry(self._actions)
            self.app.call_from_thread(self._show_save_success)
        except Exception as exc:
            logger.exception("Failed to save action registry")
            self.app.call_from_thread(self._show_save_error, str(exc))

    def _show_save_success(self) -> None:
        self.query_one("#save", Button).disabled = False
        self.query_one("#defaults-result", Static).update(
            "[bold green]Action registry saved.[/bold green]"
        )

    def _show_save_error(self, error: str) -> None:
        self.query_one("#save", Button).disabled = False
        self.query_one("#defaults-result", Static).update(
            f"[bold red]Save failed:[/bold red] {error}"
        )

    def _do_export_settings(self) -> None:
        """Toggle the export checklist visibility (macOS only)."""
        if self.app.platform != "macos":
            self.query_one("#defaults-result", Static).update(
                "[bold yellow]Settings export is macOS-only.[/bold yellow]"
            )
            return
        # Toggle checklist section visibility.
        header = self.query_one("#export-header")
        checklist = self.query_one("#export-checklist")
        run_btn = self.query_one("#run-export")
        visible = not header.display
        header.display = visible
        checklist.display = visible
        run_btn.display = visible

    def _do_run_export(self) -> None:
        """Run exports for the items checked in the SelectionList."""
        checklist = self.query_one("#export-checklist", SelectionList)
        selected_ids = list(checklist.selected)
        if not selected_ids:
            self.query_one("#defaults-result", Static).update(
                "[bold yellow]No items selected.[/bold yellow]"
            )
            return
        self.query_one("#run-export", Button).disabled = True
        self.query_one("#export-settings", Button).disabled = True
        self.query_one("#defaults-result", Static).update(
            "[dim]Exporting settings...[/dim]"
        )
        self._export_settings_worker(selected_ids)

    @work(thread=True)
    def _export_settings_worker(self, selected_ids: list[str]) -> None:
        """Run selected exports: non-interactive first, then interactive."""
        selected = [i for i in EXPORT_ITEMS if i["id"] in selected_ids]

        # --- Non-interactive exports (call Python functions directly) ---
        for item in selected:
            if item["interactive"]:
                continue
            try:
                fn = get_export_fn(item)
                msg = fn(self.app.runner)
                self.app.call_from_thread(
                    self._show_export_result,
                    f"[bold green]{msg}[/bold green]",
                )
            except Exception as exc:
                logger.exception("Failed to export %s", item["label"])
                self.app.call_from_thread(
                    self._show_export_result,
                    f"[bold red]{item['label']} export failed:[/bold red] {exc}",
                )

        # --- Interactive exports (suspend TUI, run make target) ---
        for item in selected:
            if not item["interactive"]:
                continue
            done = threading.Event()
            ok = [False]

            def _run_interactive(make_target: str = item["make_target"]) -> None:
                with self.app.suspend():
                    result = subprocess.run(
                        ["make", make_target],
                        cwd=REPO_ROOT,
                        stdin=sys.stdin,
                        stdout=sys.stdout,
                        stderr=sys.stderr,
                    )
                    ok[0] = result.returncode == 0
                done.set()

            self.app.call_from_thread(_run_interactive)
            done.wait()

            if ok[0]:
                self.app.call_from_thread(
                    self._show_export_result,
                    f"[bold green]{item['label']} exported.[/bold green]",
                )
            else:
                self.app.call_from_thread(
                    self._show_export_result,
                    f"[bold red]{item['label']} export failed.[/bold red]",
                )

        self.app.call_from_thread(self._enable_export_button)

    def _show_export_result(self, message: str) -> None:
        self.query_one("#defaults-result", Static).update(message)

    def _enable_export_button(self) -> None:
        self.query_one("#export-settings", Button).disabled = False
        self.query_one("#run-export", Button).disabled = False
