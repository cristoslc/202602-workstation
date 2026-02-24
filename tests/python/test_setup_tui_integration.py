"""Integration tests for setup_tui — renders the actual Textual app headlessly.

These tests use Textual's built-in ``pilot`` test harness to catch runtime
errors that pure unit tests (with mocked imports) miss:

- Property collisions with Textual base classes  (e.g. ``App.debug``)
- Missing methods on ``Screen`` vs ``App``  (e.g. ``call_from_thread``)
- Compose / mount errors
- Widget query failures
- Navigation bugs (push/pop screen)

Every test actually instantiates ``SetupApp``, renders it headlessly, and
interacts via ``pilot.click`` / ``pilot.press``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from textual.widgets import Button

# Add scripts/ to path so setup_tui package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.app import SetupApp
from setup_tui.lib.discovery import (
    DiscoveredPhase,
    DiscoveredRole,
    PlaybookManifest,
)
from setup_tui.lib.state import ResumeState
from setup_tui.screens.bootstrap import (
    DEFAULT_PHASES,
    BootstrapModeScreen,
    BootstrapPasswordScreen,
    BootstrapPhaseScreen,
    BootstrapRoleScreen,
    BootstrapRunScreen,
)
from setup_tui.screens.secrets import SecretsScreen
from setup_tui.screens.welcome import (
    FirstRunPlaceholderScreen,
    WelcomeScreen,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_result(**overrides):
    """Shorthand for a successful CompletedProcess."""
    defaults = dict(args=[], returncode=0, stdout="", stderr="")
    defaults.update(overrides)
    return subprocess.CompletedProcess(**defaults)


def _fail_result(**overrides):
    """Shorthand for a failed CompletedProcess."""
    defaults = dict(args=[], returncode=1, stdout="", stderr="")
    defaults.update(overrides)
    return subprocess.CompletedProcess(**defaults)


def _menu_option_ids(app) -> list[str]:
    """Get all option IDs from the menu OptionList."""
    from textual.widgets import OptionList

    menu = app.screen.query_one("#menu", OptionList)
    return [
        menu.get_option_at_index(i).id for i in range(menu.option_count)
    ]


async def _select_option(ctx, option_id: str) -> None:
    """Select a menu option by its ID and wait for processing."""
    from textual.widgets import OptionList

    menu = ctx.app.screen.query_one("#menu", OptionList)
    for i in range(menu.option_count):
        if menu.get_option_at_index(i).id == option_id:
            menu.highlighted = i
            break
    else:
        raise ValueError(f"Option {option_id!r} not found in menu")
    menu.action_select()
    await ctx.pilot.pause()


# ---------------------------------------------------------------------------
# Mock manifest for tests
# ---------------------------------------------------------------------------

def _make_mock_manifest() -> PlaybookManifest:
    """Build a PlaybookManifest matching the old hardcoded PHASES shape."""
    return PlaybookManifest(
        platform="linux",
        phases=(
            DiscoveredPhase(
                phase_id="system",
                order=0,
                display_name="System foundation",
                roles=(
                    DiscoveredRole("base", ("base", "system"), "", True),
                    DiscoveredRole("system", ("system",), "", True),
                    DiscoveredRole("hardware", ("hardware", "thinkpad", "system"), "Thinkpad", True),
                ),
                has_pre_tasks=True,
            ),
            DiscoveredPhase(
                phase_id="security",
                order=1,
                display_name="Security and secrets",
                roles=(
                    DiscoveredRole("secrets-manager", ("secrets-manager", "onepassword", "sops", "security"), "Onepassword, Sops"),
                    DiscoveredRole("firewall", ("firewall", "security"), ""),
                ),
                has_pre_tasks=True,
            ),
            DiscoveredPhase(
                phase_id="dev-tools",
                order=2,
                display_name="Development tools",
                roles=(
                    DiscoveredRole("git", ("git", "gh", "lazygit", "delta", "dev-tools"), "Gh, Lazygit, Delta"),
                    DiscoveredRole("shell", ("shell", "zsh", "direnv", "dev-tools"), "Zsh, Direnv"),
                    DiscoveredRole("python", ("python", "dev-tools"), ""),
                    DiscoveredRole("node", ("node", "dev-tools"), ""),
                    DiscoveredRole("docker", ("docker", "dev-tools"), ""),
                    DiscoveredRole("editor", ("editor", "vscode", "dev-tools"), "Vscode"),
                    DiscoveredRole("claude-code", ("claude-code", "dev-tools"), ""),
                    DiscoveredRole("fonts", ("fonts", "dev-tools"), ""),
                    DiscoveredRole("terminal", ("terminal", "tmux", "dev-tools"), "Tmux"),
                ),
            ),
            DiscoveredPhase(
                phase_id="desktop",
                order=3,
                display_name="Desktop environment",
                roles=(
                    DiscoveredRole("browsers", ("browsers", "firefox", "brave", "chrome", "desktop"), "Firefox, Brave, Chrome"),
                ),
            ),
            DiscoveredPhase(
                phase_id="dotfiles",
                order=4,
                display_name="Dotfile management",
                roles=(
                    DiscoveredRole("stow", ("stow", "dotfiles"), ""),
                ),
            ),
            DiscoveredPhase(
                phase_id="gaming",
                order=5,
                display_name="Gaming",
                roles=(
                    DiscoveredRole("gaming", ("gaming", "steam"), "Steam"),
                ),
            ),
        ),
    )


MOCK_MANIFEST = _make_mock_manifest()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def unpersonalized_state():
    """State for a fresh template repo."""
    return ResumeState(is_personalized=False)


@pytest.fixture
def personalized_state():
    """State for a fully completed repo."""
    return ResumeState(
        is_personalized=True,
        has_origin=True,
        has_commit=True,
        is_pushed=True,
        has_precommit=True,
        has_placeholder_secrets=False,
    )


@pytest.fixture
def partial_state():
    """State for a partially completed first-run."""
    return ResumeState(
        is_personalized=True,
        has_origin=False,
        has_commit=False,
        is_pushed=False,
        has_precommit=False,
        pending=["set up GitHub remote", "install pre-commit hooks"],
    )


@pytest.fixture
def placeholder_secrets_state():
    """Personalized repo with placeholder secrets remaining."""
    return ResumeState(
        is_personalized=True,
        has_placeholder_secrets=True,
    )


# ---------------------------------------------------------------------------
# Shared context manager: patches setup_logging + detect_resume_state + discovery
# ---------------------------------------------------------------------------

class _AppTestContext:
    """Reduces boilerplate for patching and running the app."""

    def __init__(self, state, *, debug=False, runner_git_return=None):
        self.state = state
        self.debug = debug
        self.runner_git_return = runner_git_return or _fail_result()

    async def __aenter__(self):
        self.app = SetupApp(debug=self.debug)
        self.app.runner.git = MagicMock(return_value=self.runner_git_return)

        self._patch_state = patch(
            "setup_tui.screens.welcome.detect_resume_state",
            return_value=self.state,
        )
        self._patch_logging = patch("setup_tui.app.setup_logging")
        self._patch_discover = patch(
            "setup_tui.screens.bootstrap.discover_playbook",
            return_value=MOCK_MANIFEST,
        )

        self._patch_state.start()
        self._patch_logging.start()
        self._patch_discover.start()

        self._ctx = self.app.run_test()
        self.pilot = await self._ctx.__aenter__()

        # Give the @work(thread=True) worker time to complete.
        await self.pilot.pause()
        return self

    async def __aexit__(self, *exc):
        await self._ctx.__aexit__(*exc)
        self._patch_state.stop()
        self._patch_logging.stop()
        self._patch_discover.stop()


# ===========================================================================
# Smoke tests — app mounts without error
# ===========================================================================

class TestAppMounts:
    """Verify the app can be instantiated and mounted headlessly."""

    @pytest.mark.asyncio
    async def test_app_starts_and_shows_welcome(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_app_debug_mode(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state, debug=True) as ctx:
            assert ctx.app._debug_mode is True
            assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_app_has_runner(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            assert ctx.app.runner is not None

    @pytest.mark.asyncio
    async def test_app_has_platform(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            assert ctx.app.platform in ("macos", "linux")


# ===========================================================================
# WelcomeScreen — unpersonalized (fresh template)
# ===========================================================================

class TestWelcomeScreenUnpersonalized:
    """Fresh template repo — should show first-run option only."""

    @pytest.mark.asyncio
    async def test_shows_first_run_option(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "first-run" in ids

    @pytest.mark.asyncio
    async def test_shows_quit_option(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "quit" in ids

    @pytest.mark.asyncio
    async def test_no_bootstrap_option(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "bootstrap" not in ids

    @pytest.mark.asyncio
    async def test_no_edit_secrets_option(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "edit-secrets" not in ids

    @pytest.mark.asyncio
    async def test_status_text(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "not been personalized" in text

    @pytest.mark.asyncio
    async def test_menu_has_focus(self, unpersonalized_state):
        """OptionList should auto-focus so arrows work immediately."""
        async with _AppTestContext(unpersonalized_state) as ctx:
            from textual.widgets import OptionList

            menu = ctx.app.screen.query_one("#menu", OptionList)
            assert menu.has_focus

    @pytest.mark.asyncio
    async def test_first_option_highlighted(self, unpersonalized_state):
        """First option should be highlighted by default."""
        async with _AppTestContext(unpersonalized_state) as ctx:
            from textual.widgets import OptionList

            menu = ctx.app.screen.query_one("#menu", OptionList)
            assert menu.highlighted == 0


# ===========================================================================
# WelcomeScreen — personalized (full menu)
# ===========================================================================

class TestWelcomeScreenPersonalized:
    """Personalized repo — should show bootstrap, secrets, first-run, quit."""

    @pytest.mark.asyncio
    async def test_shows_all_menu_options(self, personalized_state):
        async with _AppTestContext(
            personalized_state,
            runner_git_return=_ok_result(stdout="https://github.com/u/r.git"),
        ) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "bootstrap" in ids
            assert "edit-secrets" in ids
            assert "first-run" in ids
            assert "quit" in ids

    @pytest.mark.asyncio
    async def test_shows_origin_url(self, personalized_state):
        async with _AppTestContext(
            personalized_state,
            runner_git_return=_ok_result(
                stdout="https://github.com/testuser/my-repo.git"
            ),
        ) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "testuser/my-repo" in text

    @pytest.mark.asyncio
    async def test_status_shows_personalized(self, personalized_state):
        async with _AppTestContext(personalized_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "personalized" in text.lower()

    @pytest.mark.asyncio
    async def test_placeholder_secrets_warning(self, placeholder_secrets_state):
        async with _AppTestContext(placeholder_secrets_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "placeholder" in text.lower()

    @pytest.mark.asyncio
    async def test_no_placeholder_warning_when_clean(self, personalized_state):
        async with _AppTestContext(personalized_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "placeholder" not in text.lower()


# ===========================================================================
# WelcomeScreen — personalized with pending steps (e.g. bootstrap machine)
# ===========================================================================

class TestWelcomeScreenWithPendingSteps:
    """Personalized repo with pending steps should still show full menu."""

    @pytest.mark.asyncio
    async def test_shows_full_menu_not_resume(self, partial_state):
        """Pending steps must NOT block access to bootstrap."""
        async with _AppTestContext(partial_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "bootstrap" in ids
            assert "edit-secrets" in ids
            assert "first-run" in ids
            assert "quit" in ids
            assert "resume" not in ids

    @pytest.mark.asyncio
    async def test_pending_steps_shown_as_warning(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "GitHub remote" in text
            assert "pre-commit" in text

    @pytest.mark.asyncio
    async def test_still_shows_personalized(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "personalized" in text.lower()

    @pytest.mark.asyncio
    async def test_can_bootstrap_with_pending_steps(self, partial_state):
        """User must be able to bootstrap even with pending first-run steps."""
        async with _AppTestContext(partial_state) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)


# ===========================================================================
# Navigation — option selection pushes correct screens
# ===========================================================================

class TestNavigation:
    """Option selection should navigate between screens correctly."""

    @pytest.mark.asyncio
    async def test_first_run_option_navigates(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            await _select_option(ctx, "first-run")
            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)

    @pytest.mark.asyncio
    async def test_bootstrap_option_navigates(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)

    @pytest.mark.asyncio
    async def test_edit_secrets_option_navigates(self, personalized_state):
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(
                personalized_state, runner_git_return=_ok_result()
            ) as ctx:
                await _select_option(ctx, "edit-secrets")
                assert isinstance(ctx.app.screen, SecretsScreen)

    @pytest.mark.asyncio
    async def test_back_from_bootstrap_mode(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)

            await ctx.pilot.press("escape")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_back_from_first_run(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            await _select_option(ctx, "first-run")
            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)

            await ctx.pilot.click("#back")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_back_from_secrets(self, personalized_state):
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(
                personalized_state, runner_git_return=_ok_result()
            ) as ctx:
                await _select_option(ctx, "edit-secrets")
                assert isinstance(ctx.app.screen, SecretsScreen)

                await ctx.pilot.press("escape")
                await ctx.pilot.pause()
                assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_quit_option(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            await _select_option(ctx, "quit")

    @pytest.mark.asyncio
    async def test_q_key_binding(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            await ctx.pilot.press("q")

    @pytest.mark.asyncio
    async def test_arrow_keys_navigate_options(self, personalized_state):
        """Up/Down arrows should move the highlight in the OptionList."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            from textual.widgets import OptionList

            menu = ctx.app.screen.query_one("#menu", OptionList)
            assert menu.highlighted == 0

            await ctx.pilot.press("down")
            assert menu.highlighted == 1

            await ctx.pilot.press("down")
            assert menu.highlighted == 2

            await ctx.pilot.press("up")
            assert menu.highlighted == 1

    @pytest.mark.asyncio
    async def test_enter_selects_highlighted_option(self, unpersonalized_state):
        """Enter key on highlighted option should trigger navigation."""
        async with _AppTestContext(unpersonalized_state) as ctx:
            # First option (first-run) is highlighted by default.
            await ctx.pilot.press("enter")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)


# ===========================================================================
# Bootstrap screens — mode, phase, password selection
# ===========================================================================

class TestBootstrapModeScreen:
    """BootstrapModeScreen should render radio buttons and navigate forward."""

    @pytest.mark.asyncio
    async def test_mode_screen_renders(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)

            # Should have a RadioSet with 3 options.
            from textual.widgets import RadioSet
            radio_set = ctx.app.screen.query_one("#mode-select", RadioSet)
            assert radio_set is not None

    @pytest.mark.asyncio
    async def test_mode_screen_has_next_button(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            next_btn = ctx.app.screen.query_one("#next")
            assert next_btn is not None

    @pytest.mark.asyncio
    async def test_next_navigates_to_phase_screen(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)

            # Click Next with default selection.
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPhaseScreen)

    @pytest.mark.asyncio
    async def test_escape_goes_back(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapModeScreen)

            await ctx.pilot.press("escape")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, WelcomeScreen)


class TestBootstrapPhaseScreen:
    """BootstrapPhaseScreen should render checkboxes for each phase."""

    @pytest.mark.asyncio
    async def test_phase_screen_renders_selections(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPhaseScreen)

            # Should have one option per phase in the SelectionList.
            from textual.widgets import SelectionList
            selection_list = ctx.app.screen.query_one(SelectionList)
            assert selection_list.option_count == len(MOCK_MANIFEST.phases)

    @pytest.mark.asyncio
    async def test_fresh_mode_selects_default_phases(self, personalized_state):
        """Fresh install should default to phases in DEFAULT_PHASES."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#fresh")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()

            from textual.widgets import SelectionList
            selection_list = ctx.app.screen.query_one(SelectionList)
            assert len(selection_list.selected) == len(DEFAULT_PHASES["fresh"])

    @pytest.mark.asyncio
    async def test_next_navigates_to_role_screen(self, personalized_state):
        """Phase screen with multi-role phases should go to role screen."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPhaseScreen)

            # Default mode (existing_account) selects security, dev-tools, desktop, dotfiles.
            # These have >1 role total, so role screen should appear.
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

    @pytest.mark.asyncio
    async def test_escape_goes_back_to_mode(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPhaseScreen)

            await ctx.pilot.press("escape")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapModeScreen)


class TestBootstrapRoleScreen:
    """BootstrapRoleScreen should render role checkboxes and handle skip_tags."""

    @pytest.mark.asyncio
    async def test_role_screen_renders(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

            from textual.widgets import SelectionList
            role_list = ctx.app.screen.query_one("#role-list", SelectionList)
            assert role_list is not None
            # Should have roles from all default phases.
            assert role_list.option_count > 0

    @pytest.mark.asyncio
    async def test_all_roles_selected_by_default(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

            from textual.widgets import SelectionList
            role_list = ctx.app.screen.query_one("#role-list", SelectionList)
            assert len(role_list.selected) == role_list.option_count

    @pytest.mark.asyncio
    async def test_next_navigates_to_password_screen(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPasswordScreen)

    @pytest.mark.asyncio
    async def test_escape_goes_back_to_phases(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

            await ctx.pilot.press("escape")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPhaseScreen)


class TestBootstrapPasswordScreen:
    """BootstrapPasswordScreen should collect sudo password."""

    @pytest.mark.asyncio
    async def test_password_screen_renders(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            # Role screen
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPasswordScreen)

            password_input = ctx.app.screen.query_one("#sudo-password")
            assert password_input is not None

    @pytest.mark.asyncio
    async def test_password_screen_shows_summary(self, personalized_state):
        """Should show the selected mode and phases."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()

            status = ctx.app.screen.query_one("#main-content Static")
            text = str(status.content)
            assert "Existing user account" in text

    @pytest.mark.asyncio
    async def test_escape_goes_back_to_roles(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPasswordScreen)

            await ctx.pilot.press("escape")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapRoleScreen)

    @pytest.mark.asyncio
    async def test_empty_password_does_not_proceed(self, personalized_state):
        """Clicking Run with empty password should stay on screen."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            await ctx.pilot.click("#next")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, BootstrapPasswordScreen)

            await ctx.pilot.click("#run")
            await ctx.pilot.pause()
            # Should still be on password screen.
            assert isinstance(ctx.app.screen, BootstrapPasswordScreen)


class TestBootstrapRunScreen:
    """BootstrapRunScreen should render with output log and step sidebar."""

    @pytest.mark.asyncio
    async def test_run_screen_renders(self, personalized_state):
        """Directly push a BootstrapRunScreen to verify it composes."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            # Patch the bootstrap steps to avoid running real commands.
            with patch.object(
                BootstrapRunScreen, "_run_bootstrap", lambda self: None
            ):
                ctx.app.push_screen(
                    BootstrapRunScreen("fresh", ["dotfiles"], "testpass")
                )
                await ctx.pilot.pause()
                assert isinstance(ctx.app.screen, BootstrapRunScreen)

                # Should have output log and step sidebar.
                from textual.widgets import RichLog
                output = ctx.app.screen.query_one("#output", RichLog)
                assert output is not None

                step_list = ctx.app.screen.query_one("#step-list")
                assert step_list is not None

    @pytest.mark.asyncio
    async def test_run_screen_accepts_skip_tags(self, personalized_state):
        """BootstrapRunScreen should accept and store skip_tags."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            with patch.object(
                BootstrapRunScreen, "_run_bootstrap", lambda self: None
            ):
                screen = BootstrapRunScreen(
                    "fresh", ["dev-tools"], "testpass",
                    skip_tags=["docker", "node"],
                )
                ctx.app.push_screen(screen)
                await ctx.pilot.pause()
                assert screen.skip_tags == ["docker", "node"]


class TestBootstrapSkipTagsIntegration:
    """End-to-end: role screen skipped for single-role phases, skip_tags threaded."""

    @pytest.mark.asyncio
    async def test_single_role_phase_skips_role_screen(self, personalized_state):
        """Selecting only 'gaming' (1 role) should skip the role screen."""
        single_role_manifest = PlaybookManifest(
            platform="linux",
            phases=(
                DiscoveredPhase(
                    phase_id="gaming",
                    order=5,
                    display_name="Gaming",
                    roles=(
                        DiscoveredRole("gaming", ("gaming", "steam"), "Steam"),
                    ),
                ),
            ),
        )
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            # Override discovery to return single-role manifest.
            with patch(
                "setup_tui.screens.bootstrap.discover_playbook",
                return_value=single_role_manifest,
            ):
                await _select_option(ctx, "bootstrap")
                await ctx.pilot.click("#next")
                await ctx.pilot.pause()
                assert isinstance(ctx.app.screen, BootstrapPhaseScreen)

                # Toggle gaming on (it's the only phase).
                from textual.widgets import SelectionList
                sel = ctx.app.screen.query_one("#phase-list", SelectionList)
                sel.select_all()
                await ctx.pilot.pause()

                await ctx.pilot.click("#next")
                await ctx.pilot.pause()
                # Should skip role screen and go straight to password.
                assert isinstance(ctx.app.screen, BootstrapPasswordScreen)

    @pytest.mark.asyncio
    async def test_password_screen_shows_skip_tags(self, personalized_state):
        """Password screen should display skipped roles."""
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            screen = BootstrapPasswordScreen(
                "fresh",
                ["dev-tools"],
                MOCK_MANIFEST,
                skip_tags=["docker", "node"],
            )
            ctx.app.push_screen(screen)
            await ctx.pilot.pause()

            status = ctx.app.screen.query_one("#main-content Static")
            text = str(status.content)
            assert "docker" in text
            assert "node" in text


# ===========================================================================
# Placeholder screens — verify they compose without errors
# ===========================================================================

class TestPlaceholderScreensRender:
    """Remaining placeholder screens should mount and show a back button."""

    @pytest.mark.asyncio
    async def test_first_run_placeholder_has_back(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(FirstRunPlaceholderScreen())
            await ctx.pilot.pause()

            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)
            assert ctx.app.screen.query_one("#back") is not None

    @pytest.mark.asyncio
    async def test_first_run_placeholder_back_navigates(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(FirstRunPlaceholderScreen())
            await ctx.pilot.pause()

            await ctx.pilot.click("#back")
            await ctx.pilot.pause()
            assert isinstance(ctx.app.screen, WelcomeScreen)


# ===========================================================================
# SecretsScreen — form rendering, pre-fill, save, and navigation
# ===========================================================================

class TestSecretsScreen:
    """SecretsScreen should render inputs, pre-fill, mask passwords, and save."""

    @pytest.mark.asyncio
    async def test_form_renders_all_inputs(self, unpersonalized_state):
        """All 5 secret fields should appear as Input widgets."""
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                from textual.widgets import Input as TInput
                for key in [
                    "git_user_email",
                    "git_user_name",
                    "git_signing_key",
                    "ANTHROPIC_API_KEY",
                    "HOMEBREW_GITHUB_API_TOKEN",
                ]:
                    widget = ctx.app.screen.query_one(f"#field-{key}", TInput)
                    assert widget is not None

    @pytest.mark.asyncio
    async def test_existing_values_prefill(self, unpersonalized_state):
        """Decrypted values should pre-fill the corresponding Input widgets."""
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={"git_user_email": "me@example.com", "git_user_name": "Me"},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={"ANTHROPIC_API_KEY": "sk-ant-test"},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                from textual.widgets import Input as TInput
                assert ctx.app.screen.query_one("#field-git_user_email", TInput).value == "me@example.com"
                assert ctx.app.screen.query_one("#field-git_user_name", TInput).value == "Me"
                assert ctx.app.screen.query_one("#field-ANTHROPIC_API_KEY", TInput).value == "sk-ant-test"

    @pytest.mark.asyncio
    async def test_password_fields_masked(self, unpersonalized_state):
        """ANTHROPIC_API_KEY and HOMEBREW_GITHUB_API_TOKEN should be password inputs."""
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                from textual.widgets import Input as TInput
                assert ctx.app.screen.query_one("#field-ANTHROPIC_API_KEY", TInput).password is True
                assert ctx.app.screen.query_one("#field-HOMEBREW_GITHUB_API_TOKEN", TInput).password is True
                assert ctx.app.screen.query_one("#field-git_user_email", TInput).password is False

    @pytest.mark.asyncio
    async def test_back_button_pops_screen(self, unpersonalized_state):
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                # Button may be off-screen; use .press() directly.
                ctx.app.screen.query_one("#back", Button).press()
                await ctx.pilot.pause()
                assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_escape_pops_screen(self, unpersonalized_state):
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                await ctx.pilot.press("escape")
                await ctx.pilot.pause()
                assert isinstance(ctx.app.screen, WelcomeScreen)

    @pytest.mark.asyncio
    async def test_save_calls_both_save_functions(self, unpersonalized_state):
        mock_save_ansible = MagicMock()
        mock_save_shell = MagicMock()
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ), patch(
            "setup_tui.screens.secrets.save_ansible_vars",
            mock_save_ansible,
        ), patch(
            "setup_tui.screens.secrets.save_shell_exports",
            mock_save_shell,
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                # Fill in one field so we can verify collected values.
                from textual.widgets import Input as TInput
                ctx.app.screen.query_one("#field-git_user_email", TInput).value = "test@test.com"

                # Button may be off-screen; use .press() directly.
                ctx.app.screen.query_one("#save", Button).press()
                await ctx.pilot.pause()

                mock_save_ansible.assert_called_once()
                ansible_args = mock_save_ansible.call_args[0]
                assert ansible_args[1]["git_user_email"] == "test@test.com"
                # Empty ansible vars should become PLACEHOLDER.
                assert ansible_args[1]["git_user_name"] == "PLACEHOLDER"

                mock_save_shell.assert_called_once()
                # Empty shell secrets should be omitted.
                shell_args = mock_save_shell.call_args[0]
                assert shell_args[1] == {}

    @pytest.mark.asyncio
    async def test_load_failure_still_shows_form(self, unpersonalized_state):
        """If decryption fails, the form should still appear for fresh entry."""
        with patch(
            "setup_tui.screens.secrets.load_existing_ansible_vars",
            side_effect=RuntimeError("no age key"),
        ), patch(
            "setup_tui.screens.secrets.load_existing_shell_exports",
            return_value={},
        ):
            async with _AppTestContext(unpersonalized_state) as ctx:
                ctx.app.push_screen(SecretsScreen())
                await ctx.pilot.pause()

                # Form should be visible despite load failure.
                form = ctx.app.screen.query_one("#secrets-form")
                assert form.display is True
                # Status should mention the error.
                status = ctx.app.screen.query_one("#secrets-status")
                status_text = str(status.content)
                assert "no age key" in status_text
