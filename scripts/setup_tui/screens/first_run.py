"""First-run setup screen for unpersonalized repos."""

from __future__ import annotations

import logging

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

from ..lib.age import generate_or_load_age_key
from ..lib.encryption import encrypt_secret_files
from ..lib.git_ops import (
    commit_and_push,
    create_github_repo,
    detach_from_template,
    remove_origin,
)
from ..lib.prereqs import install_precommit
from ..lib.state import RepoConfig
from ..lib.tokens import replace_tokens

logger = logging.getLogger("setup")


class FirstRunSetupScreen(Screen):
    """Run first-run personalization, then chain to secrets/defaults editing."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]First-Run Setup[/bold]\n\n"
                "This will personalize the template repo, encrypt placeholders,\n"
                "install pre-commit hooks, create your GitHub repo, and push.\n"
                "[dim]Then you'll be guided through Edit Secrets and Edit Defaults.[/dim]"
            )
            yield Static("GitHub username")
            yield Input(placeholder="your-username", id="fr-username")
            yield Static("Repository name")
            yield Input(value="my-workstation", id="fr-repo")
            with Horizontal(id="defaults-buttons"):
                yield Button("Run First-Run", id="run", variant="primary")
                yield Button("Back", id="back")
            yield Static("", id="first-run-result")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._start_run()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "run":
            self._start_run()

    def _start_run(self) -> None:
        username = self.query_one("#fr-username", Input).value.strip()
        repo_name = self.query_one("#fr-repo", Input).value.strip()
        if not username:
            self.query_one("#first-run-result", Static).update(
                "[bold red]GitHub username is required.[/bold red]"
            )
            return
        if not repo_name:
            self.query_one("#first-run-result", Static).update(
                "[bold red]Repository name is required.[/bold red]"
            )
            return

        self.query_one("#run", Button).disabled = True
        self.query_one("#back", Button).disabled = True
        self.query_one("#first-run-result", Static).update(
            "[dim]Running first-run setup...[/dim]"
        )
        self._run_worker(username, repo_name)

    @work(thread=True)
    def _run_worker(self, username: str, repo_name: str) -> None:
        messages: list[str] = []
        try:
            status_msg, public_key = generate_or_load_age_key(self.app.runner)
            messages.append(status_msg)

            config = RepoConfig(
                age_public_key=public_key,
                github_username=username,
                repo_name=repo_name,
            )

            messages.extend(replace_tokens(config))
            _count, enc_messages = encrypt_secret_files(self.app.runner)
            messages.extend(enc_messages)
            messages.extend(install_precommit(self.app.runner))

            mismatch = detach_from_template(self.app.runner, config)
            if mismatch:
                messages.append(mismatch)
                remove_origin(self.app.runner)
                messages.append("Removed existing origin remote.")

            auth_check = self.app.runner.gh("auth", "status", check=False)
            if auth_check.returncode != 0:
                raise RuntimeError(
                    "GitHub CLI is not authenticated. Run 'gh auth login' and retry."
                )

            messages.extend(create_github_repo(self.app.runner, config))
            messages.extend(commit_and_push(self.app.runner))

            self.app.call_from_thread(self._show_run_success, messages)
        except Exception as exc:
            logger.exception("First-run setup failed")
            self.app.call_from_thread(
                self._show_run_error, str(exc), messages
            )

    def _show_run_success(self, messages: list[str]) -> None:
        summary = "\n".join(f"  - {m}" for m in messages[-8:])
        self.query_one("#first-run-result", Static).update(
            "[bold green]First-run core setup complete.[/bold green]\n"
            f"{summary}\n\n"
            "[dim]Opening Edit Secrets...[/dim]"
        )
        from .secrets import SecretsScreen

        self.app.push_screen(SecretsScreen(), self._after_secrets)

    def _show_run_error(
        self, error: str, messages: list[str]
    ) -> None:
        self.query_one("#run", Button).disabled = False
        self.query_one("#back", Button).disabled = False
        prior = ""
        if messages:
            prior = "\n".join(f"  - {m}" for m in messages[-6:]) + "\n\n"
        self.query_one("#first-run-result", Static).update(
            "[bold red]First-run failed.[/bold red]\n"
            f"{prior}{error}"
        )

    def _after_secrets(self, _result: object | None = None) -> None:
        from .defaults import EditDefaultsScreen

        self.app.push_screen(EditDefaultsScreen(), self._after_defaults)

    def _after_defaults(self, _result: object | None = None) -> None:
        self.app.pop_screen()
