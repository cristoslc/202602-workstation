"""WelcomeScreen — state detection and main menu."""

from __future__ import annotations

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ..lib.state import detect_resume_state


class WelcomeScreen(Screen):
    """Detects repo state and presents appropriate menu options."""

    BINDINGS = [
        ("q", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Workstation Setup[/bold]\n\n"
                "Detecting current state...",
                id="status",
            )
            yield OptionList(id="menu")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#menu", OptionList).display = False
        self._detect_state()

    @work(thread=True)
    def _detect_state(self) -> None:
        """Detect repo state in a background thread."""
        state = detect_resume_state(self.app.runner)
        self.app.call_from_thread(self._show_menu, state)

    def _show_menu(self, state) -> None:
        """Update the screen with detected state and menu options."""
        status = self.query_one("#status", Static)
        menu = self.query_one("#menu", OptionList)
        menu.clear_options()

        if not state.is_personalized:
            # Fresh template — needs first-run.
            status.update(
                "[bold]Workstation Setup[/bold]\n\n"
                "[yellow]This repo has not been personalized yet.[/yellow]\n"
                "The first-run wizard will generate an age key, "
                "collect your GitHub info,\n"
                "and encrypt your secrets."
            )
            menu.add_options([
                Option("Start First-Run Setup", id="first-run"),
                Option("Quit", id="quit"),
            ])
        elif state.pending:
            # Partially completed first-run.
            pending_text = "\n".join(f"  - {p}" for p in state.pending)
            status.update(
                "[bold]Workstation Setup[/bold]\n\n"
                "[yellow]First-run was started but not finished.[/yellow]\n"
                f"Remaining steps:\n{pending_text}"
            )
            menu.add_options([
                Option("Resume First-Run", id="resume"),
                Option("Start Over", id="first-run"),
                Option("Quit", id="quit"),
            ])
        else:
            # Personalized — show full menu.
            origin_info = ""
            result = self.app.runner.git(
                "remote", "get-url", "origin", check=False
            )
            if result.returncode == 0:
                origin_info = f"\n[dim]Origin: {result.stdout.strip()}[/dim]"

            placeholder_note = ""
            if state.has_placeholder_secrets:
                placeholder_note = (
                    "\n[yellow]Secrets contain placeholders — "
                    "use Edit Secrets to fill them in.[/yellow]"
                )

            status.update(
                "[bold]Workstation Setup[/bold]\n\n"
                f"[green]Repo is personalized.[/green]{origin_info}"
                f"{placeholder_note}"
            )
            menu.add_options([
                Option("Bootstrap This Machine", id="bootstrap"),
                Option("Edit Secrets", id="edit-secrets"),
                Option("Re-Run First-Time Setup", id="first-run"),
                Option("Quit", id="quit"),
            ])

        menu.highlighted = 0
        menu.display = True
        menu.focus()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle menu option selection."""
        option_id = event.option.id
        if option_id == "quit":
            self.app.exit()
        elif option_id == "bootstrap":
            self.app.push_screen(BootstrapPlaceholderScreen())
        elif option_id in ("first-run", "resume"):
            self.app.push_screen(FirstRunPlaceholderScreen())
        elif option_id == "edit-secrets":
            self.app.push_screen(SecretsPlaceholderScreen())


# Placeholder screens for Phase 1 — will be replaced in Phases 2-3.


class BootstrapPlaceholderScreen(Screen):
    """Temporary placeholder until Phase 2 implements the full bootstrap flow."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap[/bold]\n\n"
                "The full bootstrap TUI is coming in Phase 2.\n"
                "For now, exit and run the platform bootstrap script directly:\n\n"
                "  [cyan]make bootstrap[/cyan]"
            )
            yield Button("Back", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()


class FirstRunPlaceholderScreen(Screen):
    """Temporary placeholder until Phase 3 implements the full first-run flow."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]First-Run Setup[/bold]\n\n"
                "The full first-run TUI is coming in Phase 3.\n"
                "For now, exit and run:\n\n"
                "  [cyan]./first-run.sh[/cyan]"
            )
            yield Button("Back", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()


class SecretsPlaceholderScreen(Screen):
    """Temporary placeholder until Phase 3 implements secrets editing."""

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Edit Secrets[/bold]\n\n"
                "The secrets TUI is coming in Phase 3.\n"
                "For now, exit and run:\n\n"
                "  [cyan]make edit-secrets-shared[/cyan]"
            )
            yield Button("Back", id="back")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
