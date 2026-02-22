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

# Add scripts/ to path so setup_tui package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.app import SetupApp
from setup_tui.lib.state import ResumeState
from setup_tui.screens.welcome import (
    BootstrapPlaceholderScreen,
    FirstRunPlaceholderScreen,
    SecretsPlaceholderScreen,
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
# Shared context manager: patches setup_logging + detect_resume_state
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

        self._patch_state.start()
        self._patch_logging.start()

        self._ctx = self.app.run_test()
        self.pilot = await self._ctx.__aenter__()

        # Give the @work(thread=True) worker time to complete.
        await self.pilot.pause()
        return self

    async def __aexit__(self, *exc):
        await self._ctx.__aexit__(*exc)
        self._patch_state.stop()
        self._patch_logging.stop()


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
# WelcomeScreen — partial first-run (resume)
# ===========================================================================

class TestWelcomeScreenPartialFirstRun:
    """Partially completed first-run — should show resume + start over."""

    @pytest.mark.asyncio
    async def test_shows_resume_option(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "resume" in ids

    @pytest.mark.asyncio
    async def test_shows_start_over_option(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            ids = _menu_option_ids(ctx.app)
            assert "first-run" in ids

    @pytest.mark.asyncio
    async def test_shows_pending_steps_in_status(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "GitHub remote" in text
            assert "pre-commit" in text

    @pytest.mark.asyncio
    async def test_shows_not_finished_message(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            status = ctx.app.screen.query_one("#status")
            text = str(status.content)
            assert "not finished" in text.lower() or "started but" in text.lower()


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
            assert isinstance(ctx.app.screen, BootstrapPlaceholderScreen)

    @pytest.mark.asyncio
    async def test_edit_secrets_option_navigates(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "edit-secrets")
            assert isinstance(ctx.app.screen, SecretsPlaceholderScreen)

    @pytest.mark.asyncio
    async def test_resume_option_navigates(self, partial_state):
        async with _AppTestContext(partial_state) as ctx:
            await _select_option(ctx, "resume")
            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)

    @pytest.mark.asyncio
    async def test_back_from_bootstrap(self, personalized_state):
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "bootstrap")
            assert isinstance(ctx.app.screen, BootstrapPlaceholderScreen)

            await ctx.pilot.click("#back")
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
        async with _AppTestContext(
            personalized_state, runner_git_return=_ok_result()
        ) as ctx:
            await _select_option(ctx, "edit-secrets")
            assert isinstance(ctx.app.screen, SecretsPlaceholderScreen)

            await ctx.pilot.click("#back")
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
# Placeholder screens — verify they compose without errors
# ===========================================================================

class TestPlaceholderScreensRender:
    """Each placeholder screen should mount and show a back button."""

    @pytest.mark.asyncio
    async def test_bootstrap_placeholder_has_back(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(BootstrapPlaceholderScreen())
            await ctx.pilot.pause()

            assert isinstance(ctx.app.screen, BootstrapPlaceholderScreen)
            assert ctx.app.screen.query_one("#back") is not None

    @pytest.mark.asyncio
    async def test_first_run_placeholder_has_back(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(FirstRunPlaceholderScreen())
            await ctx.pilot.pause()

            assert isinstance(ctx.app.screen, FirstRunPlaceholderScreen)
            assert ctx.app.screen.query_one("#back") is not None

    @pytest.mark.asyncio
    async def test_secrets_placeholder_has_back(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(SecretsPlaceholderScreen())
            await ctx.pilot.pause()

            assert isinstance(ctx.app.screen, SecretsPlaceholderScreen)
            assert ctx.app.screen.query_one("#back") is not None

    @pytest.mark.asyncio
    async def test_bootstrap_placeholder_content(self, unpersonalized_state):
        async with _AppTestContext(unpersonalized_state) as ctx:
            ctx.app.push_screen(BootstrapPlaceholderScreen())
            await ctx.pilot.pause()

            status = ctx.app.screen.query_one("#main-content Static")
            text = str(status.content)
            assert "Phase 2" in text or "bootstrap" in text.lower()
