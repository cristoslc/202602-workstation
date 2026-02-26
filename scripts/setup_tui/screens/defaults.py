"""EditDefaultsScreen — edit action registry keybindings."""

from __future__ import annotations

import logging

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from ..lib.defaults import (
    display_to_keybinding,
    export_iterm2_plist,
    keybinding_to_display,
    load_action_registry,
    save_action_registry,
)

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

        buttons = [
            Button("Save", id="save", variant="primary"),
        ]
        if self.app.platform == "macos":
            buttons.append(Button("Export iTerm2", id="export-iterm2"))
        buttons.append(Button("Back", id="back"))

        form.mount(Horizontal(*buttons, id="defaults-buttons"))

        macos_hint = ""
        if self.app.platform == "macos":
            macos_hint = (
                "[dim]macOS: use Export iTerm2 to capture current iTerm2 "
                "prefs into the repo.[/dim]\n"
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
        elif event.button.id == "export-iterm2":
            self._do_export_iterm2()

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

    def _do_export_iterm2(self) -> None:
        """Export iTerm2 preferences (macOS only)."""
        if self.app.platform != "macos":
            self.query_one("#defaults-result", Static).update(
                "[bold yellow]iTerm2 export is macOS-only.[/bold yellow]"
            )
            return
        self.query_one("#export-iterm2", Button).disabled = True
        self.query_one("#defaults-result", Static).update(
            "[dim]Exporting iTerm2 preferences...[/dim]"
        )
        self._export_iterm2_worker()

    @work(thread=True)
    def _export_iterm2_worker(self) -> None:
        """Run iTerm2 export in a background thread."""
        try:
            message = export_iterm2_plist(self.app.runner)
            self.app.call_from_thread(self._show_export_success, message)
        except Exception as exc:
            logger.exception("Failed to export iTerm2 preferences")
            self.app.call_from_thread(self._show_export_error, str(exc))

    def _show_export_success(self, message: str) -> None:
        self.query_one("#export-iterm2", Button).disabled = False
        self.query_one("#defaults-result", Static).update(
            f"[bold green]{message}[/bold green]"
        )

    def _show_export_error(self, error: str) -> None:
        self.query_one("#export-iterm2", Button).disabled = False
        self.query_one("#defaults-result", Static).update(
            f"[bold red]iTerm2 export failed:[/bold red] {error}"
        )
