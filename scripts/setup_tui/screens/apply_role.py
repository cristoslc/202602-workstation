"""ApplyRoleScreen — quick single-role apply without full bootstrap."""

from __future__ import annotations

import logging

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, OptionList, Static
from textual.widgets.option_list import Option

from ..lib.discovery import discover_playbook

logger = logging.getLogger("setup")


class ApplyRoleScreen(Screen):
    """Select a single role to apply (equivalent to ``make apply ROLE=x``)."""

    BINDINGS = [("escape", "go_back", "Back"), ("slash", "focus_search", "Search")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Apply Role[/bold]\n\n"
                "Select a role to apply.\n"
                "[dim]/ to search, Arrow keys to browse, Enter to select[/dim]"
            )
            yield Input(placeholder="Filter roles...", id="role-search")
            yield OptionList(id="role-list")
        yield Footer()

    def on_mount(self) -> None:
        manifest = discover_playbook(self.app.platform)
        self._manifest = manifest
        self._rebuild_list("")
        self.query_one("#role-search", Input).focus()

    def _rebuild_list(self, filter_text: str) -> None:
        """Rebuild the option list, showing only roles matching the filter."""
        role_list = self.query_one("#role-list", OptionList)
        role_list.clear_options()
        needle = filter_text.strip().lower()

        for phase in self._manifest.phases:
            matching_roles = []
            for role in phase.roles:
                if needle and not self._role_matches(role, needle):
                    continue
                matching_roles.append(role)

            if not matching_roles:
                continue

            role_list.add_option(
                Option(
                    f"[bold dim]{phase.display_name}[/bold dim]",
                    disabled=True,
                )
            )
            for role in matching_roles:
                desc = (
                    f"  [dim]{role.description}[/dim]"
                    if role.description
                    else ""
                )
                role_list.add_option(
                    Option(f"{role.name}{desc}", id=f"role-{role.name}")
                )

    @staticmethod
    def _role_matches(role, needle: str) -> bool:
        """Check if a role matches the search needle by name, tags, or description."""
        if needle in role.name.lower():
            return True
        if any(needle in tag.lower() for tag in role.tags):
            return True
        if role.description and needle in role.description.lower():
            return True
        return False

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "role-search":
            self._rebuild_list(event.value)

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_focus_search(self) -> None:
        self.query_one("#role-search", Input).focus()

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
