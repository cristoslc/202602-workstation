"""SecretsScreen — edit Ansible vars and shell secrets."""

from __future__ import annotations

import logging

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from ..lib.secrets import (
    SHARED_ANSIBLE_VARS,
    SHELL_SECRETS,
    load_existing_ansible_vars,
    load_existing_shell_exports,
    save_ansible_vars,
    save_shell_exports,
)

logger = logging.getLogger("setup")


class SecretsScreen(Screen):
    """Edit encrypted Ansible variables and shell secrets."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Edit Secrets[/bold]\n\n"
                "[dim]Loading existing values...[/dim]",
                id="secrets-status",
            )
            with VerticalScroll(id="secrets-form"):
                yield Static(
                    "[bold underline]Ansible Variables[/bold underline]",
                    classes="section-header",
                )
                for field in SHARED_ANSIBLE_VARS:
                    yield Static(f"[bold]{field.label}[/bold]  [dim]{field.description}[/dim]")
                    yield Input(
                        placeholder=field.placeholder,
                        password=field.password,
                        id=f"field-{field.key}",
                    )
                yield Static(
                    "\n[bold underline]Shell Secrets[/bold underline]",
                    classes="section-header",
                )
                for field in SHELL_SECRETS:
                    doc = f"  [dim]{field.doc_url}[/dim]" if field.doc_url else ""
                    yield Static(
                        f"[bold]{field.label}[/bold]  [dim]{field.description}[/dim]{doc}"
                    )
                    yield Input(
                        placeholder=field.placeholder,
                        password=field.password,
                        id=f"field-{field.key}",
                    )
                with Horizontal(id="secrets-buttons"):
                    yield Button("Save", id="save", variant="primary")
                    yield Button("Back", id="back")
            yield Static("", id="secrets-result")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#secrets-form").display = False
        self._load_existing()

    @work(thread=True)
    def _load_existing(self) -> None:
        """Load existing encrypted values in a background thread."""
        try:
            ansible_vals = load_existing_ansible_vars(self.app.runner)
            shell_vals = load_existing_shell_exports(self.app.runner)
        except Exception as exc:
            logger.warning("Failed to decrypt existing secrets: %s", exc)
            self.app.call_from_thread(self._show_load_error, str(exc))
            return

        self.app.call_from_thread(self._populate_fields, ansible_vals, shell_vals)

    def _populate_fields(
        self, ansible_vals: dict[str, str], shell_vals: dict[str, str]
    ) -> None:
        """Fill inputs with decrypted values and reveal the form."""
        for field in SHARED_ANSIBLE_VARS:
            if field.key in ansible_vals:
                self.query_one(f"#field-{field.key}", Input).value = ansible_vals[field.key]
        for field in SHELL_SECRETS:
            if field.key in shell_vals:
                self.query_one(f"#field-{field.key}", Input).value = shell_vals[field.key]

        self.query_one("#secrets-status", Static).update(
            "[bold]Edit Secrets[/bold]\n\n"
            "Fill in or update the values below, then press Save.\n"
            "[dim]Tab to move between fields, Enter to save, "
            "Escape to go back[/dim]\n"
            "[dim]Empty Ansible fields default to PLACEHOLDER. "
            "Empty shell secrets are omitted.[/dim]"
        )
        self.query_one("#secrets-form").display = True

    def _show_load_error(self, error: str) -> None:
        """Show decryption error but still reveal the form for fresh entry."""
        self.query_one("#secrets-status", Static).update(
            "[bold]Edit Secrets[/bold]\n\n"
            f"[yellow]Could not decrypt existing secrets:[/yellow]\n"
            f"[dim]{error}[/dim]\n\n"
            "You can enter fresh values below.\n"
            "[dim]Tab to move between fields, Enter to save, "
            "Escape to go back[/dim]"
        )
        self.query_one("#secrets-form").display = True

    def action_go_back(self) -> None:
        self.dismiss("back")

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._do_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.dismiss("back")
        elif event.button.id == "save":
            self._do_save()

    def _do_save(self) -> None:
        """Collect values from inputs and save."""
        ansible_collected: dict[str, str] = {}
        for field in SHARED_ANSIBLE_VARS:
            val = self.query_one(f"#field-{field.key}", Input).value.strip()
            ansible_collected[field.key] = val if val else "PLACEHOLDER"

        shell_collected: dict[str, str] = {}
        for field in SHELL_SECRETS:
            val = self.query_one(f"#field-{field.key}", Input).value.strip()
            if val:
                shell_collected[field.key] = val

        self.query_one("#save", Button).disabled = True
        self.query_one("#secrets-result", Static).update(
            "[dim]Saving and encrypting...[/dim]"
        )
        self._save_worker(ansible_collected, shell_collected)

    @work(thread=True)
    def _save_worker(
        self,
        ansible_collected: dict[str, str],
        shell_collected: dict[str, str],
    ) -> None:
        """Write and encrypt secrets in a background thread."""
        try:
            save_ansible_vars(self.app.runner, ansible_collected)
            save_shell_exports(self.app.runner, shell_collected)
            self.app.call_from_thread(self._show_save_success)
        except Exception as exc:
            logger.exception("Failed to save secrets")
            self.app.call_from_thread(self._show_save_error, str(exc))

    def _show_save_success(self) -> None:
        self.query_one("#save", Button).disabled = False
        self.query_one("#secrets-result", Static).update(
            "[bold green]Secrets saved and encrypted.[/bold green]"
        )

    def _show_save_error(self, error: str) -> None:
        self.query_one("#save", Button).disabled = False
        self.query_one("#secrets-result", Static).update(
            f"[bold red]Save failed:[/bold red] {error}"
        )
