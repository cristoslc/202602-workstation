"""BootstrapScreen — mode/phase selection, prereqs, and ansible execution."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    RadioButton,
    RadioSet,
    RichLog,
    SelectionList,
    Static,
    TabbedContent,
    TabPane,
)

from ..lib.ansible_summary import AnsibleOutputParser, AnsibleSummary
from ..lib.defaults import run_all_imports
from ..lib.discovery import PlaybookManifest, discover_playbook, validate_config
from ..lib.proc_cleanup import terminate_procs
from ..lib.runner import REPO_ROOT

logger = logging.getLogger("setup")

BOOTSTRAP_LOG = REPO_ROOT / "bootstrap.log"
ANSIBLE_LOG = Path.home() / ".local" / "log" / "ansible.log"

# Phases selected by default for each mode.
DEFAULT_PHASES = {
    "fresh": ["system", "security", "dev-tools", "desktop", "dotfiles"],
    "new_account": ["security", "dev-tools", "desktop", "dotfiles"],
    "existing_account": ["security", "dev-tools", "desktop", "dotfiles"],
}

# Phase dependencies — values are auto-included when the key is selected.
# security decrypts secret dotfiles that the stow role needs.
PHASE_DEPS: dict[str, list[str]] = {
    "dotfiles": ["security"],
}


def _resolve_phase_deps(
    selected: list[str], manifest: PlaybookManifest
) -> list[str]:
    """Add missing dependencies and return phases in manifest order."""
    phase_order = manifest.phase_ids()
    full = set(selected)
    for phase in selected:
        for dep in PHASE_DEPS.get(phase, []):
            full.add(dep)
    return [p for p in phase_order if p in full]


class BootstrapModeScreen(Screen):
    """Step 1: Select bootstrap mode."""

    BINDINGS = [("escape", "go_back", "Back")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap — Step 1 of 3[/bold]\n\n"
                "What kind of system is this?\n"
                "[dim]Arrow keys to choose, Tab to reach Next, Enter to press[/dim]"
            )
            with RadioSet(id="mode-select"):
                yield RadioButton(
                    "Existing system, existing user account",
                    id="existing_account",
                    value=True,
                )
                yield RadioButton(
                    "Existing system, new user account",
                    id="new_account",
                )
                yield RadioButton(
                    "Fresh install (new OS, clean slate)",
                    id="fresh",
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
            manifest = discover_playbook(self.app.platform)
            warnings = validate_config(manifest, DEFAULT_PHASES, PHASE_DEPS)
            for w in warnings:
                logger.warning("Config validation: %s", w)
            self.app.push_screen(BootstrapPhaseScreen(mode, manifest))


class BootstrapPhaseScreen(Screen):
    """Step 2: Select which phases to run."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(self, mode: str, manifest: PlaybookManifest) -> None:
        super().__init__()
        self.mode = mode
        self.manifest = manifest

    def compose(self) -> ComposeResult:
        defaults = DEFAULT_PHASES.get(self.mode, [])
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap — Step 2[/bold]\n\n"
                "Which role groups should run?\n"
                "[dim]Arrow keys to move, Space to toggle, Tab to jump to Next[/dim]"
            )
            yield SelectionList[str](
                *[
                    (
                        f"{phase.display_name}  "
                        f"[dim]{', '.join(r.name for r in phase.roles)}[/dim]",
                        phase.phase_id,
                        phase.phase_id in defaults,
                    )
                    for phase in self.manifest.phases
                ],
                id="phase-list",
            )
            yield Button("Next", id="next", variant="primary")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            phase_list = self.query_one("#phase-list", SelectionList)
            selected = list(phase_list.selected)
            if not selected:
                return
            selected = _resolve_phase_deps(selected, self.manifest)
            # Show role screen if any selected phase has >1 role.
            roles = self.manifest.roles_for_phases(selected)
            if len(roles) > 1:
                self.app.push_screen(
                    BootstrapRoleScreen(
                        self.mode, selected, self.manifest
                    )
                )
            else:
                self.app.push_screen(
                    BootstrapPasswordScreen(
                        self.mode, selected, self.manifest
                    )
                )


class BootstrapRoleScreen(Screen):
    """Optional step: Select individual roles to include/skip."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(
        self,
        mode: str,
        phases: list[str],
        manifest: PlaybookManifest,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.phases = phases
        self.manifest = manifest

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            yield Static(
                "[bold]Bootstrap — Role Selection[/bold]\n\n"
                "Deselect any roles you want to skip.\n"
                "[dim]Arrow keys to move, Space to toggle, Tab to jump to Next[/dim]"
            )
            with TabbedContent(id="role-tabs"):
                for phase in self.manifest.phases:
                    if phase.phase_id not in self.phases:
                        continue
                    items = []
                    for role in phase.roles:
                        desc = f"  [dim]{role.description}[/dim]" if role.description else ""
                        label = f"{role.name}{desc}"
                        items.append((label, role.name, True))
                    with TabPane(phase.display_name, id=f"tab-{phase.phase_id}"):
                        yield SelectionList[str](
                            *items, id=f"roles-{phase.phase_id}"
                        )
            yield Button("Next", id="next", variant="primary")
        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "next":
            selected_roles: set[str] = set()
            for sel_list in self.query(SelectionList):
                selected_roles.update(sel_list.selected)
            all_roles = {
                r.name
                for p in self.manifest.phases
                if p.phase_id in self.phases
                for r in p.roles
            }
            skip_tags = sorted(all_roles - selected_roles)
            self.app.push_screen(
                BootstrapPasswordScreen(
                    self.mode, self.phases, self.manifest,
                    skip_tags=skip_tags,
                )
            )


class BootstrapPasswordScreen(Screen):
    """Collect sudo password for ansible-playbook --become."""

    BINDINGS = [("escape", "go_back", "Back")]

    def __init__(
        self,
        mode: str,
        phases: list[str],
        manifest: PlaybookManifest,
        *,
        skip_tags: list[str] | None = None,
        role_apply: str | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.phases = phases
        self.manifest = manifest
        self.skip_tags = skip_tags or []
        self.role_apply = role_apply

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-content"):
            if self.role_apply:
                # Single-role apply mode.
                summary = (
                    f"[bold]Apply Role — Password[/bold]\n\n"
                    f"[dim]Role:[/dim] {self.role_apply}"
                )
                button_label = "Apply"
            else:
                mode_labels = {
                    "fresh": "Fresh install",
                    "new_account": "New user account",
                    "existing_account": "Existing user account",
                }
                phase_names = ", ".join(
                    phase.display_name if (phase := self.manifest.phase_by_id(p)) else p
                    for p in self.phases
                )
                skip_text = ""
                if self.skip_tags:
                    skip_text = (
                        f"\n[dim]Skipping:[/dim] {', '.join(self.skip_tags)}"
                    )
                summary = (
                    f"[bold]Bootstrap — Password[/bold]\n\n"
                    f"[dim]Mode:[/dim]   {mode_labels.get(self.mode, self.mode)}\n"
                    f"[dim]Phases:[/dim] {phase_names}"
                    f"{skip_text}"
                )
                button_label = "Run Bootstrap"
            yield Static(
                f"{summary}\n\n"
                "Enter your sudo password for Ansible privilege escalation.\n"
                "[dim]This is passed to ansible-playbook via environment variable "
                "and is never written to disk.[/dim]\n"
                f"[dim]Enter to submit, or Tab to reach {button_label}[/dim]"
            )
            yield Input(
                placeholder="sudo password",
                password=True,
                id="sudo-password",
            )
            yield Static("", id="password-error")
            yield Button(button_label, id="run", variant="primary")
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
        # Disable controls while validating.
        self.query_one("#run", Button).disabled = True
        self.query_one("#sudo-password", Input).disabled = True
        self.query_one("#password-error", Static).update(
            "[dim]Verifying sudo password… "
            "(may take ~15 s if fingerprint auth is active)[/dim]"
        )
        self._validate_sudo(password)

    @work(thread=True)
    def _validate_sudo(self, password: str) -> None:
        """Test the sudo password before starting the bootstrap run.

        pam_fprintd (if present) blocks for up to 15 s waiting for a
        fingerprint before falling through to pam_unix.  We use a 20 s
        timeout so the password is still validated correctly.
        """
        try:
            proc = subprocess.run(
                ["sudo", "-kS", "true"],
                input=password + "\n",
                capture_output=True,
                text=True,
                timeout=20,
            )
            if proc.returncode == 0:
                logger.debug("Sudo password validated successfully")
                self.app.call_from_thread(
                    self._push_run_screen, password,
                )
            else:
                logger.warning("Sudo password validation failed (exit %d)", proc.returncode)
                self.app.call_from_thread(self._show_password_error)
        except subprocess.TimeoutExpired:
            # Even 20 s wasn't enough — proceed anyway and let
            # ansible-playbook validate the password at runtime.
            logger.warning(
                "Sudo validation timed out after 20 s; skipping validation"
            )
            self.app.call_from_thread(self._show_timeout_warning, password)

    def _show_password_error(self) -> None:
        """Reset the form and show an error message for wrong password."""
        self.query_one("#password-error", Static).update(
            "[bold red]Wrong password.[/bold red] Please try again."
        )
        password_input = self.query_one("#sudo-password", Input)
        password_input.value = ""
        password_input.disabled = False
        password_input.focus()
        self.query_one("#run", Button).disabled = False

    def _push_run_screen(self, password: str) -> None:
        """Instantiate and push the run screen on the main thread."""
        self.app.push_screen(
            BootstrapRunScreen(
                self.mode, self.phases, password,
                skip_tags=self.skip_tags,
                role_apply=self.role_apply,
                manifest=self.manifest,
            ),
        )

    def _show_timeout_warning(self, password: str) -> None:
        """Sudo timed out (likely fingerprint auth). Proceed with a warning."""
        self.query_one("#password-error", Static).update(
            "[bold yellow]Sudo timed out[/bold yellow] — fingerprint auth may "
            "be interfering.\nProceeding; Ansible will verify the password."
        )
        self._push_run_screen(password)


class BootstrapRunScreen(Screen):
    """Executes bootstrap: prereqs, galaxy, ansible-playbook with live output."""

    BINDINGS = [
        ("q", "confirm_quit", "Quit"),
    ]

    def __init__(
        self,
        mode: str,
        phases: list[str],
        become_pass: str,
        *,
        skip_tags: list[str] | None = None,
        role_apply: str | None = None,
        manifest: PlaybookManifest | None = None,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.phases = phases
        self.become_pass = become_pass
        self.skip_tags = skip_tags or []
        self.role_apply = role_apply
        self.manifest = manifest
        self._procs: list[subprocess.Popen] = []
        self._finished = False
        self._success = False
        self._log_file = None
        self._start_time: float = 0.0
        self._timer = None
        self._spinner_frames = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._spinner_idx = 0
        self._ansible_parser: AnsibleOutputParser | None = None
        self._ansible_summary: AnsibleSummary | None = None
        self._failed_phases: set[str] = set()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="run-layout"):
            with Vertical(id="step-sidebar"):
                yield Static("[bold]Steps[/bold]", id="sidebar-title")
                yield Static("", id="step-list")
                yield Static("", id="elapsed-timer")
            with Vertical(id="run-main"):
                yield RichLog(id="output", highlight=True, markup=True, wrap=True)
        with Horizontal(id="run-footer-buttons"):
            yield Button("Done", id="done", variant="primary", disabled=True)
            yield Button(
                "Retry Failed", id="retry-failed",
                variant="warning", disabled=True,
            )
            yield Button("Migrate Data", id="migrate-data", disabled=True)
            yield Button("Import Settings", id="import-settings", disabled=True)
            yield Button("Back to Menu", id="back", disabled=True)
            yield Button("Send Log", id="send-log", disabled=True)
        yield Static(
            "[dim]Tab to move between buttons, Enter to press[/dim]",
            id="run-hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        if self.app.platform != "macos":
            self.query_one("#import-settings", Button).display = False
        self.query_one("#retry-failed", Button).display = False
        self._start_time = time.monotonic()
        self._timer = self.set_interval(1, self._tick_elapsed)
        self._run_bootstrap()

    def on_unmount(self) -> None:
        terminate_procs(self._procs)
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._log_file and not self._log_file.closed:
            self._log_file.close()

    @work(thread=True)
    def _run_bootstrap(self) -> None:
        """Run the full bootstrap pipeline in a background thread."""
        from datetime import datetime, timezone

        platform = self.app.platform
        platform_dir = "macos" if platform == "macos" else "linux"
        apply_system_roles = "system" in self.phases

        # Create fresh bootstrap.log for this run.
        self._log_file = open(BOOTSTRAP_LOG, "w")

        # Truncate ansible.log so it only contains output from this run.
        ANSIBLE_LOG.parent.mkdir(parents=True, exist_ok=True)
        ANSIBLE_LOG.write_text("")
        skip_info = f"\nSkipping: {', '.join(self.skip_tags)}" if self.skip_tags else ""
        self._log_file.write(
            f"Bootstrap started: {datetime.now(timezone.utc).isoformat()}\n"
            f"Mode: {self.mode}  Platform: {platform}\n"
            f"Phases: {', '.join(self.phases)}{skip_info}\n"
            f"{'=' * 60}\n\n"
        )

        steps = [
            ("Install prerequisites", self._step_prereqs),
            ("Install Ansible Galaxy collections", self._step_galaxy),
            ("Resolve age key", self._step_age_key),
            ("Run Ansible playbook", self._step_ansible),
            ("Verify installations", self._step_verify),
        ]

        self.app.call_from_thread(
            self._update_sidebar, steps, -1
        )

        # Grant temporary NOPASSWD sudo for the entire bootstrap run.
        # Broken PAM modules (e.g. pam_fprintd on Mint) hang for ~10s on
        # every sudo invocation, which causes captured subprocess calls to
        # fail.  A NOPASSWD sudoers entry lets sudo skip PAM authentication
        # entirely.  The initial `sudo -S` to create the entry goes through
        # PAM once (~10s) but completes within the 30-second timeout.
        self._grant_nopasswd_sudo()

        success = True
        ansible_failed = False
        try:
            for i, (label, step_fn) in enumerate(steps):
                # Skip verify if ansible failed — results would be meaningless.
                if ansible_failed and step_fn == self._step_verify:
                    self.app.call_from_thread(
                        self._log,
                        f"\n[dim]>>> {label} (skipped — ansible failed)[/dim]\n"
                    )
                    continue

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

                    if step_fn == self._step_ansible:
                        # Don't break — render the summary, then skip verify.
                        ansible_failed = True
                        success = False
                        self._render_ansible_summary()
                    else:
                        success = False
                        break

                # Render summary after successful ansible too.
                if step_fn == self._step_ansible and not ansible_failed:
                    self._render_ansible_summary()
        finally:
            self._revoke_nopasswd_sudo()

        log_path = str(BOOTSTRAP_LOG)
        if success:
            self.app.call_from_thread(
                self._update_sidebar, steps, len(steps)
            )
            self.app.call_from_thread(
                self._log,
                "\n[bold green]Bootstrap complete![/bold green]\n"
                "[dim]Shell configs will reload automatically "
                "when you press Done.[/dim]\n"
                "[dim]If this is a new machine, use "
                "[bold]Migrate Data[/bold] to copy user folders "
                "from an existing machine.[/dim]\n"
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
        self._success = success
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
        from ..lib.age import (
            TRANSFER_KEY_SCRIPT,
            AgeKeyError,
            generate_age_key,
            load_age_key,
        )
        from ..lib.state import AGE_KEY_PATH

        # Fast path: key already exists.
        try:
            status_msg, public_key = load_age_key(self.app.runner)
            self.app.call_from_thread(self._log, f"  {status_msg}")
            self.app.call_from_thread(
                self._log, f"  [dim]Public key: {public_key}[/dim]"
            )
            return
        except FileNotFoundError:
            pass

        # No key — ask the user how to proceed.
        from .key_resolve import KeyResolveScreen

        choice_event = threading.Event()
        choice_result: list[str] = []  # mutable container for closure

        def on_dismiss(result: str) -> None:
            choice_result.append(result or "skip")
            choice_event.set()

        self.app.call_from_thread(
            self.app.push_screen, KeyResolveScreen(), on_dismiss
        )
        choice_event.wait()
        choice = choice_result[0]

        if choice in ("receive", "import"):
            self._run_interactive_transfer(choice, TRANSFER_KEY_SCRIPT)
        elif choice == "1password":
            self._step_retrieve_age_from_1password(AGE_KEY_PATH)
        elif choice == "generate":
            status_msg, public_key = generate_age_key(self.app.runner)
            self.app.call_from_thread(self._log, f"  {status_msg}")
            self.app.call_from_thread(
                self._log, f"  [dim]Public key: {public_key}[/dim]"
            )
            return
        elif choice == "skip":
            self.app.call_from_thread(
                self._log,
                "  [bold yellow]Skipped[/bold yellow] — no age key. "
                "Secret decryption will fail until a key is provided."
            )
            logger.warning("User skipped age key resolution")
            return

        # After transfer, verify the key was installed.
        if not AGE_KEY_PATH.exists():
            self.app.call_from_thread(
                self._log,
                "  [bold yellow]Warning:[/bold yellow] key file not found "
                "after transfer. Secret decryption may fail."
            )
            logger.warning("Age key not found after transfer attempt")
            return

        try:
            status_msg, public_key = load_age_key(self.app.runner)
            self.app.call_from_thread(self._log, f"  {status_msg}")
            self.app.call_from_thread(
                self._log, f"  [dim]Public key: {public_key}[/dim]"
            )
        except (FileNotFoundError, AgeKeyError) as exc:
            self.app.call_from_thread(
                self._log,
                f"  [bold yellow]Warning:[/bold yellow] {exc}"
            )

    def _step_retrieve_age_from_1password(self, key_path: Path) -> None:
        """Retrieve the age key from 1Password CLI."""
        self.app.call_from_thread(
            self._log, "  Retrieving age key from 1Password..."
        )
        try:
            result = subprocess.run(
                ["op", "--version"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                self.app.call_from_thread(
                    self._log,
                    "  [bold yellow]Error:[/bold yellow] 1Password CLI "
                    "(op) not found. Install the 1Password desktop app first."
                )
                return

            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.parent.chmod(0o700)

            result = subprocess.run(
                ["op", "read", "op://Private/age-key/private-key"],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0 or not result.stdout.strip():
                self.app.call_from_thread(
                    self._log,
                    "  [bold yellow]Error:[/bold yellow] Could not retrieve "
                    "key from 1Password. Ensure the desktop app is running "
                    "and unlocked."
                )
                return

            key_path.write_text(result.stdout)
            key_path.chmod(0o600)
            self.app.call_from_thread(
                self._log, "  Age key retrieved from 1Password."
            )
        except subprocess.TimeoutExpired:
            self.app.call_from_thread(
                self._log,
                "  [bold yellow]Error:[/bold yellow] 1Password CLI timed out."
            )
        except Exception as exc:
            self.app.call_from_thread(
                self._log,
                f"  [bold yellow]Error:[/bold yellow] {exc}"
            )

    def _run_interactive_transfer(
        self, method: str, script: Path
    ) -> None:
        """Suspend the TUI and run transfer-key.sh interactively."""
        done_event = threading.Event()

        def _do_transfer() -> None:
            with self.app.suspend():
                if method == "receive":
                    print("\n  On the source machine, run:  make key-send\n")
                else:
                    print(
                        "\n  On the source machine, run:  make key-export\n"
                        "  Then paste the blob below.\n"
                    )
                subprocess.run(
                    ["bash", str(script), method],
                    stdin=sys.stdin,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                )
            done_event.set()

        self.app.call_from_thread(_do_transfer)
        done_event.wait()

    _SUDOERS_TEMP = "/etc/sudoers.d/99-bootstrap-temp"

    def _step_ansible(
        self, platform: str, platform_dir: str, apply_system_roles: bool,
        *, tags_override: list[str] | None = None,
    ) -> None:
        ansible_cfg = REPO_ROOT / platform_dir / "ansible.cfg"
        playbook = REPO_ROOT / platform_dir / "site.yml"

        cmd = [
            "ansible-playbook", str(playbook),
            "-e", f"workstation_dir={REPO_ROOT}",
            "-e", f"bootstrap_mode={self.mode}",
            "-e", f"apply_system_roles={str(apply_system_roles).lower()}",
            "-e", f"platform={platform}",
            "-e", f"platform_dir={platform_dir}",
            "-e", "interactive_imports=false",
        ]

        if platform == "macos":
            apply_defaults = "true" if self.mode != "existing_account" else "false"
            cmd.extend(["-e", f"apply_macos_defaults={apply_defaults}"])

        # Filter playbook to only the selected phases.
        tags = tags_override or self.phases
        if tags:
            cmd.extend(["--tags", ",".join(tags)])

        # Skip deselected roles.
        if self.skip_tags:
            cmd.extend(["--skip-tags", ",".join(self.skip_tags)])

        self._ansible_parser = AnsibleOutputParser()
        env_extra = {"ANSIBLE_CONFIG": str(ansible_cfg)}
        self._run_streaming(
            cmd, env_extra=env_extra,
            line_callback=self._ansible_parser.feed_line,
        )

    def _step_verify(
        self, platform: str, _platform_dir: str, _apply_system: bool
    ) -> None:
        """Run post-install verification for the selected phases (informational only)."""
        from ..lib.verify import filter_entries, load_registry, run_all_checks

        try:
            entries = load_registry()
        except Exception as exc:
            self.app.call_from_thread(
                self._log,
                f"  [yellow]Could not load verify registry: {exc}[/yellow]"
            )
            return

        if self.role_apply:
            # Single-role apply: filter by role name, not phase.
            entries = filter_entries(
                entries, platform=platform, roles=[self.role_apply]
            )
        else:
            entries = filter_entries(
                entries, platform=platform, phases=self.phases
            )
        if not entries:
            self.app.call_from_thread(
                self._log, "  [dim]No entries to verify for selected phases.[/dim]"
            )
            return

        results = run_all_checks(entries, parallel=True)

        pass_count = sum(1 for r in results if r.passed)
        fail_count = sum(1 for r in results if not r.passed and not r.entry.optional)
        warn_count = sum(1 for r in results if not r.passed and r.entry.optional)

        # Log failures and warnings.
        for r in results:
            if not r.passed:
                if r.entry.optional:
                    note = f" — {r.entry.note}" if r.entry.note else ""
                    self.app.call_from_thread(
                        self._log,
                        f"  [yellow]WARN[/yellow]  {r.entry.name}: {r.detail}{note}"
                    )
                else:
                    self.app.call_from_thread(
                        self._log,
                        f"  [red]FAIL[/red]  {r.entry.name}: {r.detail}"
                    )

        summary = f"  {pass_count} passed, {fail_count} failed, {warn_count} warnings"
        self.app.call_from_thread(self._log, summary)

    def _render_ansible_summary(self) -> None:
        """Extract and render a structured summary from the Ansible parser."""
        if self._ansible_parser is None:
            return

        summary = self._ansible_parser.summary()
        self._ansible_summary = summary
        if summary is None:
            self.app.call_from_thread(
                self._log,
                "\n[dim]  (No Ansible recap captured)[/dim]\n"
            )
            return

        # Counts line.
        counts = (
            f"  [green]OK: {summary.ok}[/green]  "
            f"[yellow]Changed: {summary.changed}[/yellow]  "
            f"[red]Failed: {summary.failed}[/red]  "
            f"[dim]Skipped: {summary.skipped}[/dim]"
        )
        if summary.unreachable:
            counts += f"  [red]Unreachable: {summary.unreachable}[/red]"
        if summary.rescued:
            counts += f"  [cyan]Rescued: {summary.rescued}[/cyan]"
        if summary.ignored:
            counts += f"  [dim]Ignored: {summary.ignored}[/dim]"

        self.app.call_from_thread(
            self._log,
            "\n[bold]Ansible Run Summary[/bold]\n"
            f"{'─' * 50}"
        )
        self.app.call_from_thread(self._log, counts)

        # Failed tasks table.
        if summary.failures:
            self.app.call_from_thread(
                self._log,
                f"\n  [bold red]Failed Tasks ({len(summary.failures)}):[/bold red]"
            )
            for i, ft in enumerate(summary.failures, 1):
                role_label = f"[cyan]{ft.role}[/cyan] : " if ft.role else ""
                # Truncate long messages to first line for scannability.
                msg_first_line = ft.message.split("\n")[0][:200]
                self.app.call_from_thread(
                    self._log,
                    f"  {i}. {role_label}[bold]{ft.task}[/bold]\n"
                    f"     [dim]{ft.play}[/dim]\n"
                    f"     [red]{msg_first_line}[/red]"
                )

            # Populate _failed_phases for retry button.
            self._failed_phases = self._resolve_failed_phases(summary)
            if self._failed_phases:
                self.app.call_from_thread(self._show_retry_button)

        self.app.call_from_thread(
            self._log, f"{'─' * 50}\n"
        )

    def _resolve_failed_phases(self, summary: AnsibleSummary) -> set[str]:
        """Map failed task play names back to phase IDs via the manifest."""
        if self.manifest is None:
            return set()

        failed = set()
        for ft in summary.failures:
            # Play name looks like "Phase 2: Development tools".
            # The manifest display_name is "Development tools" or similar.
            for phase in self.manifest.phases:
                if phase.display_name in ft.play:
                    failed.add(phase.phase_id)
                    break
        return failed

    def _show_retry_button(self) -> None:
        """Show and enable the retry-failed button."""
        btn = self.query_one("#retry-failed", Button)
        btn.display = True
        btn.disabled = False

    def _retry_failed(self) -> None:
        """Re-run ansible-playbook with --tags limited to failed phases."""
        if not self._failed_phases:
            return
        self.query_one("#retry-failed", Button).disabled = True
        self.query_one("#done", Button).disabled = True
        self._finished = False
        if self._timer is None:
            self._start_time = time.monotonic()
            self._timer = self.set_interval(1, self._tick_elapsed)
        self._retry_failed_worker()

    @work(thread=True)
    def _retry_failed_worker(self) -> None:
        """Background worker for retrying failed phases."""
        platform = self.app.platform
        platform_dir = "macos" if platform == "macos" else "linux"
        apply_system_roles = "system" in self._failed_phases
        tags = sorted(self._failed_phases)

        self.app.call_from_thread(
            self._log,
            f"\n[bold cyan]>>> Retrying failed phases: "
            f"{', '.join(tags)}[/bold cyan]\n"
        )

        self._grant_nopasswd_sudo()
        try:
            self._step_ansible(
                platform, platform_dir, apply_system_roles,
                tags_override=tags,
            )
            self._render_ansible_summary()
            self.app.call_from_thread(
                self._log,
                "\n[bold green]Retry complete![/bold green]\n"
            )
            self._success = True
        except Exception as exc:
            self.app.call_from_thread(
                self._log,
                f"\n[bold red]Retry failed:[/bold red] {exc}\n"
            )
            self._render_ansible_summary()
            self._success = False
        finally:
            self._revoke_nopasswd_sudo()

        self._finished = True
        self.app.call_from_thread(self._enable_done_buttons)

    def _grant_nopasswd_sudo(self) -> None:
        """Create a temporary NOPASSWD sudoers entry for the current user."""
        import getpass

        user = getpass.getuser()
        sudoers_line = f"{user} ALL=(ALL) NOPASSWD: ALL"
        result = subprocess.run(
            [
                "sudo", "-S", "sh", "-c",
                f'echo "{sudoers_line}" > {self._SUDOERS_TEMP}'
                f" && chmod 0440 {self._SUDOERS_TEMP}",
            ],
            input=self.become_pass + "\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("Could not create temp sudoers: %s", result.stderr)

    def _revoke_nopasswd_sudo(self) -> None:
        """Remove the temporary NOPASSWD sudoers entry."""
        subprocess.run(
            ["sudo", "-n", "rm", "-f", self._SUDOERS_TEMP],
            capture_output=True,
            timeout=15,
            check=False,
        )

    def _run_streaming(
        self,
        cmd: list[str],
        *,
        env_extra: dict[str, str] | None = None,
        cwd: Path | None = None,
        line_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Run a command and stream stdout/stderr to the RichLog widget."""
        env = os.environ.copy()
        # Strip virtualenv variables so they don't leak through sudo into
        # PAM modules (pam_fingwit.so does execvp("python3") using PATH,
        # and the venv python lacks system packages like gi).
        env.pop("VIRTUAL_ENV", None)
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        venv = os.environ.get("VIRTUAL_ENV")
        clean_path = os.environ.get("PATH", "")
        if venv:
            clean_path = os.pathsep.join(
                p for p in clean_path.split(os.pathsep)
                if not p.startswith(venv)
            )
        env["PATH"] = f"{Path.home()}/.local/bin:{clean_path}"
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
        self._procs.append(proc)
        try:
            for line in proc.stdout:
                stripped = line.rstrip("\n")
                if line_callback is not None:
                    line_callback(stripped)
                self.app.call_from_thread(self._log_output, stripped)
                logger.debug(stripped)

            proc.wait()
        finally:
            if proc in self._procs:
                self._procs.remove(proc)
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

    def _tick_elapsed(self) -> None:
        """Tick the elapsed-time display in the sidebar."""
        elapsed = int(time.monotonic() - self._start_time)
        minutes, seconds = divmod(elapsed, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            time_str = f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            time_str = f"{minutes}:{seconds:02d}"

        if self._finished:
            label = f"[dim]Elapsed: {time_str}[/dim]"
            if self._timer is not None:
                self._timer.stop()
                self._timer = None
        else:
            spinner = self._spinner_frames[self._spinner_idx]
            self._spinner_idx = (self._spinner_idx + 1) % len(
                self._spinner_frames
            )
            label = f"[bold yellow]{spinner}[/bold yellow] [dim]Elapsed: {time_str}[/dim]"

        self.query_one("#elapsed-timer", Static).update(label)

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
        self.query_one("#migrate-data", Button).disabled = False
        self.query_one("#import-settings", Button).disabled = False
        self.query_one("#back", Button).disabled = False
        self.query_one("#send-log", Button).disabled = False

    def _generate_post_install_doc(self) -> None:
        """Write a post-install checklist HTML file and stash the path on the app."""
        try:
            from ..lib.post_install import generate_and_open

            doc_path = generate_and_open(
                plat=self.app.platform,
                phases=self.phases,
                skip_tags=self.skip_tags,
                log_path=str(BOOTSTRAP_LOG),
            )
            self.app.post_install_doc = doc_path  # type: ignore[attr-defined]
        except Exception:
            logger.exception("Failed to generate post-install checklist")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "done":
            if self._success:
                self._generate_post_install_doc()
            self.app.exit(result="reload_shell" if self._success else None)
        elif event.button.id == "retry-failed":
            self._retry_failed()
        elif event.button.id == "migrate-data":
            from .migration import DataMigrationScreen
            self.app.push_screen(DataMigrationScreen())
        elif event.button.id == "import-settings":
            self._do_import_settings()
        elif event.button.id == "back":
            # Pop all bootstrap screens back to welcome.
            from .welcome import WelcomeScreen

            while not isinstance(
                self.app.screen, (BootstrapModeScreen, WelcomeScreen)
            ):
                self.app.pop_screen()
            if isinstance(self.app.screen, BootstrapModeScreen):
                self.app.pop_screen()
            # If no WelcomeScreen in the stack (e.g. --start-screen bootstrap),
            # push a fresh one so the user doesn't land on a blank screen.
            if not isinstance(self.app.screen, WelcomeScreen):
                self.app.push_screen(WelcomeScreen())
        elif event.button.id == "send-log":
            self._send_log()

    def _do_import_settings(self) -> None:
        """Import iTerm2 + Raycast settings (macOS only)."""
        self.query_one("#import-settings", Button).disabled = True
        self._log("[bold cyan]>>> Importing settings...[/bold cyan]\n")
        self._import_settings_worker()

    @work(thread=True)
    def _import_settings_worker(self) -> None:
        """Run all imports, suspending for interactive confirm dialogs."""
        try:
            messages, confirmations = run_all_imports(self.app.runner)
            for msg in messages:
                self.app.call_from_thread(self._log, f"  {msg}")

            for prompt, cleanup_fn in confirmations:
                done = threading.Event()

                def _do_confirm(p: str = prompt) -> None:
                    with self.app.suspend():
                        input(f"\n  {p}, then press Enter to continue...")
                    done.set()

                self.app.call_from_thread(_do_confirm)
                done.wait()
                cleanup_fn()
                self.app.call_from_thread(
                    self._log, f"  {prompt.split(' in ')[0]} confirmed."
                )

            self.app.call_from_thread(
                self._log,
                "\n[bold green]Settings import complete.[/bold green]\n",
            )
        except Exception as exc:
            logger.exception("Settings import failed")
            self.app.call_from_thread(
                self._log, f"\n[bold red]Import failed:[/bold red] {exc}\n"
            )
        finally:
            self.app.call_from_thread(
                setattr,
                self.query_one("#import-settings", Button),
                "disabled", False,
            )

    @work(thread=True)
    def _send_log(self) -> None:
        """Send bootstrap.log via Magic Wormhole."""
        if not BOOTSTRAP_LOG.exists():
            self.app.call_from_thread(
                self._log,
                "[bold red]No bootstrap.log found.[/bold red]"
            )
            return

        send_btn = self.query_one("#send-log", Button)
        self.app.call_from_thread(setattr, send_btn, "disabled", True)
        self.app.call_from_thread(
            self._log,
            "\n[bold cyan]>>> Sending bootstrap.log via Magic Wormhole...[/bold cyan]\n"
        )

        try:
            self._run_streaming(
                ["uv", "run", "--with", "magic-wormhole",
                 "wormhole", "send", str(BOOTSTRAP_LOG)],
            )
            self.app.call_from_thread(
                self._log,
                "\n[bold green]Log sent successfully.[/bold green]\n"
            )
        except RuntimeError:
            self.app.call_from_thread(
                self._log,
                "\n[bold red]Failed to send log.[/bold red]\n"
            )
        finally:
            self.app.call_from_thread(setattr, send_btn, "disabled", False)

    def action_confirm_quit(self) -> None:
        if self._finished:
            self.app.exit()
