"""KeyResolveScreen — modal for choosing how to resolve a missing age key."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option


class KeyResolveScreen(Screen[str]):
    """Modal screen that asks the user how to obtain their age key.

    Dismisses with one of: "receive", "import", "generate", "skip".
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Resolve Age Key[/bold]\n\n"
                "An age private key is required to decrypt secrets.\n\n"
                "[dim]If you already have a key on another machine, "
                "transfer it.\n"
                "Otherwise, generate a new one (you will need to "
                "re-encrypt secrets).[/dim]"
            )
            yield OptionList(
                Option("Receive via Magic Wormhole", id="receive"),
                Option("Import encrypted blob", id="import"),
                Option("Generate new key", id="generate"),
                Option("Skip (no key)", id="skip"),
                id="key-menu",
            )
        yield Footer()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        self.dismiss(event.option.id)

    def action_cancel(self) -> None:
        self.dismiss("skip")
