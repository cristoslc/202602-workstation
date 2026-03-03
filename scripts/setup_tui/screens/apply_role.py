"""ApplyRoleScreen — quick single-role apply without full bootstrap."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, OptionList, Static
from textual.widgets.option_list import Option

from ..lib.discovery import PlaybookManifest, discover_playbook

logger = logging.getLogger("setup")


class ApplyRoleScreen(Screen):
    """Select a single role to apply (equivalent to ``make apply ROLE=x``)."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Apply Role[/bold]\n\n"
                "Select a role to apply.\n"
                "[dim]Arrow keys to browse, Enter to select[/dim]"
            )
            yield OptionList(id="role-list")
        yield Footer()

    def on_mount(self) -> None:
        manifest = discover_playbook(self.app.platform)
        self._manifest = manifest
        role_list = self.query_one("#role-list", OptionList)

        for i, phase in enumerate(manifest.phases):
            # Phase header (disabled — arrow keys skip over it).
            role_list.add_option(
                Option(
                    f"[bold dim]{phase.display_name}[/bold dim]",
                    disabled=True,
                )
            )
            for role in phase.roles:
                desc = (
                    f"  [dim]{role.description}[/dim]"
                    if role.description
                    else ""
                )
                role_list.add_option(
                    Option(f"{role.name}{desc}", id=f"role-{role.name}")
                )

        role_list.focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        option_id = event.option.id
        if not option_id or not option_id.startswith("role-"):
            return
        role_name = option_id.removeprefix("role-")

        # Find the parent phase so verification works correctly.
        phase_id = None
        for phase in self._manifest.phases:
            for role in phase.roles:
                if role.name == role_name:
                    phase_id = phase.phase_id
                    break
            if phase_id:
                break

        from .bootstrap import BootstrapPasswordScreen

        self.app.push_screen(
            BootstrapPasswordScreen(
                mode="existing_account",
                phases=[role_name],
                manifest=self._manifest,
                role_apply=role_name,
            )
        )
