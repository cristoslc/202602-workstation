"""BootstrapScreen — mode/phase selection, prereqs, and ansible execution."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    RadioButton,
    RadioSet,
    RichLog,
    Static,
)

from ..lib.runner import REPO_ROOT

logger = logging.getLogger("setup")

BOOTSTRAP_LOG = REPO_ROOT / "bootstrap.log"
ANSIBLE_LOG = Path.home() / ".local" / "log" / "ansible.log"

# Phase definitions — order matches site.yml playbook imports.
PHASES = [
    ("system", "System", "OS packages, fonts, system settings"),
    ("security", "Security", "SSH keys, GPG, firewall, disk encryption checks"),
    ("dev-tools", "Dev Tools", "Languages, editors, CLI tools, containers"),
    ("desktop", "Desktop", "Window manager, terminal, theme, apps"),
    ("dotfiles", "Dotfiles", "Shell config, git config, app settings via stow"),
]

# Phases selected by default for each mode.
DEFAULT_PHASES = {
    "fresh": ["system", "security", "dev-tools", "desktop", "dotfiles"],
    "new_account": ["security", "dev-tools", "desktop", "dotfiles"],
    "existing_account": ["security", "dev-tools", "desktop", "dotfiles"],
}


class BootstrapModeScreen(Screen):
    """Step 1: Select bootstrap mode."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap — Step 1 of 3[/bold]\n\n"
                "What kind of system is this?"
            )
            with RadioSet(id="mode-select"):
                yield RadioButton(
                    "Fresh install (new OS, clean slate)",
                    id="fresh",
                    value=True,
                )
                yield RadioButton(
                    "Existing system, new user account",
                    id="new_account",
                )
                yield RadioButton(
                    "Existing system, existing user account",
                    id="existing_account",
                )
            yield Button("Next", id="next", variant="primary")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            radio_set = self.query_one("#mode-select", RadioSet)
            pressed = radio_set.pressed_button
            if pressed is None:
                return
            mode = pressed.id
            self.app.push_screen(BootstrapPhaseScreen(mode))


class BootstrapPhaseScreen(Screen):
    """Step 2: Select which phases to run."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode

    def compose(self) -> ComposeResult:
        defaults = DEFAULT_PHASES.get(self.mode, [])
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap — Step 2 of 3[/bold]\n\n"
                "Which role groups should run?"
            )
            with Vertical(id="phase-checkboxes"):
                for phase_id, label, description in PHASES:
                    yield Checkbox(
                        f"{label}  [dim]{description}[/dim]",
                        id=f"phase-{phase_id}",
                        value=phase_id in defaults,
                    )
            yield Button("Next", id="next", variant="primary")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            selected = []
            for phase_id, _, _ in PHASES:
                cb = self.query_one(f"#phase-{phase_id}", Checkbox)
                if cb.value:
                    selected.append(phase_id)
            if not selected:
                return
            self.app.push_screen(
                BootstrapPasswordScreen(self.mode, selected)
            )


class BootstrapPasswordScreen(Screen):
    """Step 3: Collect sudo password for ansible-playbook --become."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, mode: str, phases: list[str]) -> None:
        super().__init__()
        self.mode = mode
        self.phases = phases

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            mode_labels = {
                "fresh": "Fresh install",
                "new_account": "New user account",
                "existing_account": "Existing user account",
            }
            phase_labels = {pid: label for pid, label, _ in PHASES}
            phase_names = ", ".join(
                phase_labels.get(p, p) for p in self.phases
            )
            yield Static(
                "[bold]Bootstrap — Step 3 of 3[/bold]\n\n"
                f"[dim]Mode:[/dim]   {mode_labels.get(self.mode, self.mode)}\n"
                f"[dim]Phases:[/dim] {phase_names}\n\n"
                "Enter your sudo password for Ansible privilege escalation.\n"
                "[dim]This is passed to ansible-playbook via environment variable "
                "and is never written to disk.[/dim]"
            )
            yield Input(
                placeholder="sudo password",
                password=True,
                id="sudo-password",
            )
            yield Button("Run Bootstrap", id="run", variant="primary")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_input_submitted(self, _event: Input.Submitted) -> None:
        self._start_run()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run":
            self._start_run()

    def _start_run(self) -> None:
        password = self.query_one("#sudo-password", Input).value
        if not password:
            return
        self.app.push_screen(
            BootstrapRunScreen(self.mode, self.phases, password)
        )


class BootstrapRunScreen(Screen):
    """Executes bootstrap: prereqs, galaxy, ansible-playbook with live output."""

    BINDINGS = [
        ("q", "confirm_quit", "Quit"),
    ]

    def __init__(
        self, mode: str, phases: list[str], become_pass: str
    ) -> None:
        super().__init__()
        self.mode = mode
        self.phases = phases
        self.become_pass = become_pass
        self._finished = False
        self._log_file = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="run-layout"):
            with Vertical(id="step-sidebar"):
                yield Static("[bold]Steps[/bold]", id="sidebar-title")
                yield Static("", id="step-list")
            with Vertical(id="run-main"):
                yield RichLog(id="output", highlight=True, markup=True)
        with Horizontal(id="run-footer-buttons"):
            yield Button("Done", id="done", variant="primary", disabled=True)
            yield Button("Back to Menu", id="back", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self._run_bootstrap()

    @work(thread=True)
    def _run_bootstrap(self) -> None:
        """Run the full bootstrap pipeline in a background thread."""
        import re
        from datetime import datetime, timezone

        platform = self.app.platform
        platform_dir = "macos" if platform == "macos" else "linux"
        apply_system_roles = "system" in self.phases

        # Create fresh bootstrap.log for this run.
        self._log_file = open(BOOTSTRAP_LOG, "w")
        self._log_file.write(
            f"Bootstrap started: {datetime.now(timezone.utc).isoformat()}\n"
            f"Mode: {self.mode}  Platform: {platform}\n"
            f"Phases: {', '.join(self.phases)}\n"
            f"{'=' * 60}\n\n"
        )

        steps = [
            ("Install prerequisites", self._step_prereqs),
            ("Install Ansible Galaxy collections", self._step_galaxy),
            ("Resolve age key", self._step_age_key),
            ("Run Ansible playbook", self._step_ansible),
        ]

        self.app.call_from_thread(
            self._update_sidebar, steps, -1
        )

        success = True
        for i, (label, step_fn) in enumerate(steps):
            self.app.call_from_thread(
                self._update_sidebar, steps, i
            )
            self.app.call_from_thread(
                self._log, f"\n[bold cyan]>>> {label}[/bold cyan]\n"
            )
            try:
                step_fn(platform, platform_dir, apply_system_roles)
            except Exception as exc:
                self.app.call_from_thread(
                    self._log,
                    f"\n[bold red]ERROR:[/bold red] {exc}\n"
                )
                logger.exception("Bootstrap step failed: %s", label)
                success = False
                break

        log_path = str(BOOTSTRAP_LOG)
        if success:
            self.app.call_from_thread(
                self._update_sidebar, steps, len(steps)
            )
            self.app.call_from_thread(
                self._log,
                "\n[bold green]Bootstrap complete![/bold green]\n"
                "[dim]Some changes may require a shell restart "
                "or system reboot.[/dim]\n"
                f"[dim]Log: {log_path}[/dim]\n"
            )
        else:
            self.app.call_from_thread(
                self._log,
                "\n[bold red]Bootstrap failed.[/bold red] "
                "Fix the issue above and re-run.\n"
                f"[dim]Log: {log_path}[/dim]\n"
            )

        # Append ansible log if it exists.
        if ANSIBLE_LOG.exists():
            self._log_file.write(f"\n{'=' * 60}\n")
            self._log_file.write("Ansible log (from ~/.local/log/ansible.log):\n")
            self._log_file.write(f"{'=' * 60}\n\n")
            self._log_file.write(ANSIBLE_LOG.read_text())

        self._log_file.close()
        self._log_file = None
        self._finished = True
        self.app.call_from_thread(self._enable_done_buttons)

    def _step_prereqs(
        self, platform: str, _platform_dir: str, _apply_system: bool
    ) -> None:
        from ..lib.prereqs import install_bootstrap_prereqs

        install_bootstrap_prereqs(
            platform, on_message=lambda msg: self.app.call_from_thread(
                self._log, f"  {msg}"
            )
        )

    def _step_galaxy(
        self, _platform: str, _platform_dir: str, _apply_system: bool
    ) -> None:
        requirements = REPO_ROOT / "shared" / "requirements.yml"
        self._run_streaming(
            ["ansible-galaxy", "collection", "install",
             "-r", str(requirements)],
        )

    def _step_age_key(
        self, _platform: str, _platform_dir: str, _apply_system: bool
    ) -> None:
        from ..lib.age import generate_or_load_age_key

        status_msg, public_key = generate_or_load_age_key(self.app.runner)
        self.app.call_from_thread(self._log, f"  {status_msg}")
        self.app.call_from_thread(
            self._log,
            f"  [dim]Public key: {public_key}[/dim]"
        )

    def _step_ansible(
        self, platform: str, platform_dir: str, apply_system_roles: bool
    ) -> None:
        import tempfile

        ansible_cfg = REPO_ROOT / platform_dir / "ansible.cfg"
        playbook = REPO_ROOT / platform_dir / "site.yml"

        # Write become password to a temp file for ansible-playbook.
        # The ANSIBLE_BECOME_PASSWORD env var is unreliable across
        # ansible-core versions; --become-password-file is robust.
        pass_fd, pass_path = tempfile.mkstemp(prefix=".become-", dir=str(REPO_ROOT))
        try:
            os.write(pass_fd, self.become_pass.encode())
            os.close(pass_fd)
            os.chmod(pass_path, 0o600)

            cmd = [
                "ansible-playbook", str(playbook),
                "--become-password-file", pass_path,
                "-e", f"workstation_dir={REPO_ROOT}",
                "-e", f"bootstrap_mode={self.mode}",
                "-e", f"apply_system_roles={str(apply_system_roles).lower()}",
                "-e", f"platform={platform}",
                "-e", f"platform_dir={platform_dir}",
            ]

            if platform == "macos":
                apply_defaults = "true" if self.mode != "existing_account" else "false"
                cmd.extend(["-e", f"apply_macos_defaults={apply_defaults}"])

            env_extra = {"ANSIBLE_CONFIG": str(ansible_cfg)}
            self._run_streaming(cmd, env_extra=env_extra)
        finally:
            # Always remove the password file, even on failure.
            try:
                os.unlink(pass_path)
            except OSError:
                pass

    def _run_streaming(
        self,
        cmd: list[str],
        *,
        env_extra: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        """Run a command and stream stdout/stderr to the RichLog widget."""
        env = os.environ.copy()
        env["PATH"] = f"{Path.home()}/.local/bin:{env.get('PATH', '')}"
        if env_extra:
            env.update(env_extra)

        logger.debug("Streaming: %s", " ".join(cmd))

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            cwd=cwd,
        )

        for line in proc.stdout:
            stripped = line.rstrip("\n")
            self.app.call_from_thread(self._log_output, stripped)
            logger.debug(stripped)

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                f"Command failed (exit {proc.returncode}): {' '.join(cmd)}"
            )

    def _log(self, text: str) -> None:
        """Write a Rich-markup line to the RichLog widget and log file."""
        import re

        log_widget = self.query_one("#output", RichLog)
        log_widget.write(text)

        if self._log_file and not self._log_file.closed:
            # Strip Rich markup tags for the plain-text log file.
            plain = re.sub(r"\[/?[^\]]*\]", "", text)
            self._log_file.write(plain + "\n")
            self._log_file.flush()

    def _log_output(self, text: str) -> None:
        """Write subprocess output verbatim (no Rich markup parsing)."""
        from rich.text import Text

        log_widget = self.query_one("#output", RichLog)
        log_widget.write(Text(text))

        if self._log_file and not self._log_file.closed:
            self._log_file.write(text + "\n")
            self._log_file.flush()

    def _update_sidebar(
        self, steps: list[tuple[str, object]], current: int
    ) -> None:
        """Update the step sidebar with progress indicators."""
        lines = []
        for i, (label, _) in enumerate(steps):
            if i < current:
                lines.append(f"[green]  {label}[/green]")
            elif i == current:
                lines.append(f"[bold yellow]  {label}[/bold yellow]")
            else:
                lines.append(f"[dim]  {label}[/dim]")
        sidebar = self.query_one("#step-list", Static)
        sidebar.update("\n".join(lines))

    def _enable_done_buttons(self) -> None:
        self.query_one("#done", Button).disabled = False
        self.query_one("#back", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done":
            self.app.exit()
        elif event.button.id == "back":
            # Pop all bootstrap screens back to welcome.
            while not isinstance(self.app.screen, BootstrapModeScreen):
                self.app.pop_screen()
            self.app.pop_screen()

    def action_confirm_quit(self) -> None:
        if self._finished:
            self.app.exit()
