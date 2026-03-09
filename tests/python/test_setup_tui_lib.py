"""Tests for setup_tui.lib modules — the new UI-decoupled business logic."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

# Add scripts/ to path so setup_tui package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.lib.runner import REPO_ROOT, ToolRunner
from setup_tui.lib.state import (
    AGE_KEY_PATH,
    AGE_TOKEN,
    RepoConfig,
    ResumeState,
    detect_resume_state,
    extract_resume_config,
)
from setup_tui.lib.age import AgeKeyError, generate_age_key, generate_or_load_age_key, load_age_key
from setup_tui.lib.tokens import replace_tokens
from setup_tui.lib.encryption import EncryptionError, encrypt_secret_files, write_and_encrypt
from setup_tui.lib.git_ops import (
    GitError,
    GitHubError,
    commit_and_push,
    create_github_repo,
    detach_from_template,
    remove_origin,
)
from setup_tui.lib.secrets import (
    SHARED_ANSIBLE_VARS,
    SHELL_SECRETS,
    SecretField,
    mask_value,
    load_existing_ansible_vars,
    load_existing_shell_exports,
    save_ansible_vars,
    save_shell_exports,
)
from setup_tui.lib.prereqs import detect_platform, install_precommit
from setup_tui.lib.setup_logging import LOG_DIR, LOG_FILE, setup_logging
from setup_tui.lib.defaults import (
    AGE_KEYS_PATH,
    EXPORT_ITEMS,
    ITERM2_PLIST_AGE_PATH,
    ITERM2_PLIST_PATH,
    OPENIN_APP_PATH,
    OPENIN_PLIST_AGE_PATH,
    OPENIN_PLIST_PATH,
    RAYCAST_CONFIG_AGE_PATH,
    RAYCAST_IMPORT_TMP,
    STREAMDECK_PLUGINS_AGE_PATH,
    _normalize_keybinding,
    cleanup_raycast_import,
    export_iterm2_plist,
    export_openin_settings,
    export_streamdeck_plugin_list,
    get_export_fn,
    import_iterm2_settings,
    import_openin_settings,
    import_raycast_settings,
    load_action_registry,
    run_all_imports,
    save_action_registry,
    scan_streamdeck_plugins,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_runner():
    """ToolRunner with all subprocess/tool calls mocked."""
    runner = ToolRunner(debug=True)
    ok = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    runner.run = MagicMock(return_value=ok)
    runner.git = MagicMock(return_value=ok)
    runner.gh = MagicMock(return_value=ok)
    runner.sops_encrypt_in_place = MagicMock()
    runner.sops_decrypt = MagicMock(return_value="")
    runner.age_keygen = MagicMock(return_value=("private-key", "age1abc"))
    runner.age_public_key_from_file = MagicMock(return_value="age1abc")
    runner.command_exists = MagicMock(return_value=True)
    return runner


@pytest.fixture
def sample_config():
    """A sample RepoConfig for testing."""
    return RepoConfig(
        age_public_key="age1ql3z7hjy54pw3hyww5ayyfg7zqgvc7w3j2elw8zmrj2kg5sfn9aqmcac8p",
        github_username="testuser",
        repo_name="my-workstation",
    )


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a minimal repo structure with template tokens."""
    sops_yaml = tmp_path / ".sops.yaml"
    sops_yaml.write_text(
        "creation_rules:\n"
        "  - path_regex: '.*/secrets/.*'\n"
        "    age: '${AGE_PUBLIC_KEY}'\n"
    )

    setup_sh = tmp_path / "setup.sh"
    setup_sh.write_text(
        '#!/usr/bin/env bash\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'git clone "${GITHUB_REPO_URL}" ~/.workstation\n'
    )
    setup_sh.chmod(0o755)

    bootstrap_sh = tmp_path / "bootstrap.sh"
    bootstrap_sh.write_text(
        '#!/usr/bin/env bash\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'git clone "${GITHUB_REPO_URL}" ~/.workstation\n'
    )
    bootstrap_sh.chmod(0o755)

    readme = tmp_path / "README.md"
    readme.write_text(
        "# ${REPO_NAME}\n\n"
        "Clone: ${GITHUB_REPO_URL}\n"
        "By: ${GITHUB_USERNAME}\n"
    )

    secrets_dir = tmp_path / "shared" / "secrets"
    secrets_dir.mkdir(parents=True)
    (secrets_dir / "vars.sops.yml").write_text("---\ngit_user_email: PLACEHOLDER\n")

    shell_dir = secrets_dir / "dotfiles" / "zsh" / ".config" / "zsh"
    shell_dir.mkdir(parents=True)
    (shell_dir / "secrets.zsh.sops").write_text(
        "# Shell secrets -- sourced by .zshrc\n"
    )

    for plat in ["macos", "linux"]:
        plat_secrets = tmp_path / plat / "secrets"
        plat_secrets.mkdir(parents=True)
        (plat_secrets / "vars.sops.yml").write_text("---\nplaceholder: true\n")

    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "hooks").mkdir()

    return tmp_path


# ===========================================================================
# SetupApp (app.py)
# ===========================================================================

class TestSetupApp:
    """Tests for the main Textual app — instantiation only (no UI rendering)."""

    def test_instantiation(self):
        """SetupApp must not collide with Textual's debug property."""
        from setup_tui.app import SetupApp
        app = SetupApp(debug=False)
        assert app._debug_mode is False
        assert isinstance(app.runner, ToolRunner)

    def test_debug_mode_flag(self):
        from setup_tui.app import SetupApp
        app = SetupApp(debug=True)
        assert app._debug_mode is True
        assert app.runner.debug is True

    def test_platform_detection(self):
        from setup_tui.app import SetupApp
        app = SetupApp()
        assert app.platform in ("macos", "linux")

    def test_sops_env_var_set(self):
        import os
        from setup_tui.app import SetupApp
        SetupApp()
        assert os.environ.get("SOPS_AGE_KEY_FILE") == str(AGE_KEY_PATH)


# ===========================================================================
# Pure functions
# ===========================================================================

class TestMaskValue:
    def test_short_values_fully_masked(self):
        assert mask_value("abc") == "***"
        assert mask_value("1234567890") == "**********"

    def test_long_values_show_ends(self):
        result = mask_value("sk-ant-abcdef12345xyz")
        assert result.startswith("sk-a")
        assert result.endswith("5xyz")
        assert "*" in result
        assert len(result) == len("sk-ant-abcdef12345xyz")

    def test_empty_string(self):
        assert mask_value("") == ""

    def test_boundary_length_11(self):
        """Exactly 11 chars: should show first 4 + last 4 with 3 stars."""
        result = mask_value("12345678901")
        assert result == "1234***8901"


class TestDetectPlatform:
    def test_returns_known_platform(self):
        result = detect_platform()
        assert result in ("macos", "linux")


class TestRepoConfig:
    def test_github_repo_url(self, sample_config):
        assert sample_config.github_repo_url == (
            "https://github.com/testuser/my-workstation.git"
        )

    def test_default_values(self):
        config = RepoConfig()
        assert config.age_public_key == ""
        assert config.github_username == ""
        assert config.repo_name == ""
        assert config.github_repo_url == "https://github.com//.git"

    def test_url_with_special_chars_in_name(self):
        config = RepoConfig(github_username="user", repo_name="my-repo-2025")
        assert config.github_repo_url == "https://github.com/user/my-repo-2025.git"


class TestExportItemsRegistry:
    """Validate the EXPORT_ITEMS data-driven registry structure."""

    def test_all_items_have_required_keys(self):
        for item in EXPORT_ITEMS:
            assert "id" in item, f"Missing 'id' in {item}"
            assert "label" in item, f"Missing 'label' in {item}"
            assert "interactive" in item, f"Missing 'interactive' in {item}"
            assert isinstance(item["interactive"], bool)

    def test_non_interactive_items_have_export_fn(self):
        for item in EXPORT_ITEMS:
            if not item["interactive"]:
                assert "export_fn" in item, (
                    f"Non-interactive item {item['id']} missing 'export_fn'"
                )
                fn = get_export_fn(item)
                assert callable(fn), (
                    f"export_fn for {item['id']} is not callable"
                )

    def test_interactive_items_have_make_target(self):
        for item in EXPORT_ITEMS:
            if item["interactive"]:
                assert "make_target" in item, (
                    f"Interactive item {item['id']} missing 'make_target'"
                )
                assert isinstance(item["make_target"], str)

    def test_ids_are_unique(self):
        ids = [item["id"] for item in EXPORT_ITEMS]
        assert len(ids) == len(set(ids)), "Duplicate IDs in EXPORT_ITEMS"

    def test_known_items_present(self):
        ids = {item["id"] for item in EXPORT_ITEMS}
        assert "iterm2" in ids
        assert "streamdeck" in ids
        assert "raycast" in ids
        assert "openin" in ids


class TestExportIterm2Plist:
    def test_runs_make_and_age_encrypt(self, mock_runner):
        export_iterm2_plist(mock_runner)
        assert mock_runner.run.call_count == 2
        # First call: make export-iterm2
        mock_runner.run.assert_any_call(
            ["make", "export-iterm2"],
            cwd=REPO_ROOT,
            check=False,
        )
        # Second call: age encrypt
        age_call = mock_runner.run.call_args_list[1]
        assert age_call[0][0][0] == "age"
        assert "-r" in age_call[0][0]
        assert str(ITERM2_PLIST_AGE_PATH) in age_call[0][0]

    def test_raises_on_make_failure(self, mock_runner):
        mock_runner.run = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="boom",
            )
        )

        with pytest.raises(RuntimeError, match="boom"):
            export_iterm2_plist(mock_runner)


class TestImportIterm2Settings:
    def test_decrypts_then_configures_when_age_exists(self, mock_runner):
        with patch.object(
            type(ITERM2_PLIST_AGE_PATH), "exists", return_value=True
        ):
            msg = import_iterm2_settings(mock_runner)
        # age decrypt + stow + 2 defaults write = 4 calls
        assert mock_runner.run.call_count == 4
        decrypt_call = mock_runner.run.call_args_list[0]
        assert decrypt_call == call(
            [
                "age", "-d",
                "-i", str(AGE_KEYS_PATH),
                "-o", str(ITERM2_PLIST_PATH),
                str(ITERM2_PLIST_AGE_PATH),
            ],
            check=True,
        )
        stow_call = mock_runner.run.call_args_list[1]
        assert stow_call[0][0][0] == "stow"
        assert "--no-folding" in stow_call[0][0]
        assert "iterm2" in stow_call[0][0]
        assert "iterm2" in msg.lower()

    def test_skips_decrypt_when_no_age_file(self, mock_runner):
        with patch.object(
            type(ITERM2_PLIST_AGE_PATH), "exists", return_value=False
        ):
            msg = import_iterm2_settings(mock_runner)
        # stow + 2 defaults write calls (no decrypt)
        assert mock_runner.run.call_count == 3
        mock_runner.run.assert_any_call(
            [
                "defaults", "write", "com.googlecode.iterm2",
                "PrefsCustomFolder", "-string", "~/.config/iterm2",
            ],
            check=True,
        )
        mock_runner.run.assert_any_call(
            [
                "defaults", "write", "com.googlecode.iterm2",
                "LoadPrefsFromCustomFolder", "-bool", "true",
            ],
            check=True,
        )
        assert "iterm2" in msg.lower()


class TestExportOpenInSettings:
    def test_runs_make_and_age_encrypt(self, mock_runner):
        export_openin_settings(mock_runner)
        assert mock_runner.run.call_count == 2
        # First call: make export-openin
        mock_runner.run.assert_any_call(
            ["make", "export-openin"],
            cwd=REPO_ROOT,
            check=False,
        )
        # Second call: age encrypt
        age_call = mock_runner.run.call_args_list[1]
        assert age_call[0][0][0] == "age"
        assert "-r" in age_call[0][0]
        assert str(OPENIN_PLIST_AGE_PATH) in age_call[0][0]

    def test_raises_on_make_failure(self, mock_runner):
        mock_runner.run = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="boom",
            )
        )

        with pytest.raises(RuntimeError, match="boom"):
            export_openin_settings(mock_runner)


class TestImportOpenInSettings:
    def test_skip_when_no_export(self, mock_runner):
        with patch(
            "setup_tui.lib.defaults.OPENIN_PLIST_AGE_PATH",
        ) as mock_age:
            mock_age.exists.return_value = False
            msg = import_openin_settings(mock_runner)
        assert "skipping" in msg.lower()
        mock_runner.run.assert_not_called()

    def test_skip_when_app_not_installed(self, mock_runner):
        with patch(
            "setup_tui.lib.defaults.OPENIN_PLIST_AGE_PATH",
        ) as mock_age, patch(
            "setup_tui.lib.defaults.OPENIN_APP_PATH",
        ) as mock_app:
            mock_age.exists.return_value = True
            mock_app.exists.return_value = False
            msg = import_openin_settings(mock_runner)
        assert "not installed" in msg.lower()
        mock_runner.run.assert_not_called()

    def test_decrypt_and_import_when_export_exists(self, mock_runner):
        # PlistBuddy returns bundle ID on stdout
        bundle_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="com.loshadki.OpenIn\n", stderr=""
        )
        default_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        )
        mock_runner.run = MagicMock(side_effect=[bundle_result, default_result, default_result])

        with patch(
            "setup_tui.lib.defaults.OPENIN_PLIST_AGE_PATH",
        ) as mock_age, patch(
            "setup_tui.lib.defaults.OPENIN_APP_PATH",
        ) as mock_app, patch(
            "setup_tui.lib.defaults.OPENIN_PLIST_PATH",
        ) as mock_plist:
            mock_age.exists.return_value = True
            mock_app.exists.return_value = True
            mock_app.__truediv__ = lambda self, other: Path("/Applications/Setapp/OpenIn.app") / other
            msg = import_openin_settings(mock_runner)
        assert mock_runner.run.call_count == 3
        # First: PlistBuddy to get bundle ID
        plist_call = mock_runner.run.call_args_list[0]
        assert "/usr/libexec/PlistBuddy" in plist_call[0][0][0]
        # Second: age decrypt
        decrypt_call = mock_runner.run.call_args_list[1]
        assert decrypt_call[0][0][0] == "age"
        # Third: defaults import
        import_call = mock_runner.run.call_args_list[2]
        assert import_call[0][0][:2] == ["defaults", "import"]
        assert "com.loshadki.OpenIn" in import_call[0][0]
        assert "openin" in msg.lower()


class TestImportRaycastSettings:
    def test_skip_when_no_export(self, mock_runner):
        with patch.object(
            type(RAYCAST_CONFIG_AGE_PATH), "exists", return_value=False
        ):
            msg, needs_confirm = import_raycast_settings(mock_runner)
        assert "skipping" in msg.lower()
        assert needs_confirm is False
        mock_runner.run.assert_not_called()

    def test_decrypt_and_open_when_export_exists(self, mock_runner):
        with patch.object(
            type(RAYCAST_CONFIG_AGE_PATH), "exists", return_value=True
        ):
            msg, needs_confirm = import_raycast_settings(mock_runner)
        assert needs_confirm is True
        assert mock_runner.run.call_count == 2
        # First call: age decrypt
        decrypt_call = mock_runner.run.call_args_list[0]
        assert decrypt_call == call(
            [
                "age", "-d",
                "-i", str(AGE_KEYS_PATH),
                "-o", str(RAYCAST_IMPORT_TMP),
                str(RAYCAST_CONFIG_AGE_PATH),
            ],
            check=True,
        )
        # Second call: open
        open_call = mock_runner.run.call_args_list[1]
        assert open_call == call(
            ["open", str(RAYCAST_IMPORT_TMP)], check=True
        )


class TestCleanupRaycastImport:
    def test_removes_temp_file(self, tmp_path):
        tmp_file = tmp_path / "raycast-import.rayconfig"
        tmp_file.write_text("data")
        with patch(
            "setup_tui.lib.defaults.RAYCAST_IMPORT_TMP", tmp_file
        ):
            cleanup_raycast_import()
        assert not tmp_file.exists()

    def test_no_error_when_missing(self, tmp_path):
        tmp_file = tmp_path / "nonexistent"
        with patch(
            "setup_tui.lib.defaults.RAYCAST_IMPORT_TMP", tmp_file
        ):
            cleanup_raycast_import()  # should not raise


class TestRunAllImports:
    def test_orchestrates_all_imports(self, mock_runner):
        with patch.object(
            type(RAYCAST_CONFIG_AGE_PATH), "exists", return_value=True
        ), patch(
            "setup_tui.lib.defaults.STREAMDECK_BACKUP_AGE_PATH",
            RAYCAST_CONFIG_AGE_PATH,  # reuse existing mock path
        ):
            messages, confirmations = run_all_imports(mock_runner)
        assert len(messages) == 4  # iTerm2 + OpenIn + Raycast + Stream Deck
        assert len(confirmations) == 1  # Raycast needs confirm; Stream Deck is headless
        # iTerm2 (decrypt + stow + 2 defaults write = 4) +
        # OpenIn (PlistBuddy + decrypt + defaults import = 3) +
        # Raycast (decrypt + open = 2) +
        # Stream Deck (decrypt = 1, then zipfile fails on mock path)
        assert mock_runner.run.call_count == 10

    def test_no_confirm_when_no_exports(self, mock_runner):
        with patch.object(
            type(RAYCAST_CONFIG_AGE_PATH), "exists", return_value=False
        ), patch(
            "setup_tui.lib.defaults.STREAMDECK_BACKUP_AGE_PATH",
            RAYCAST_CONFIG_AGE_PATH,  # also reports not found
        ):
            messages, confirmations = run_all_imports(mock_runner)
        assert len(messages) == 4  # iTerm2 + OpenIn skip + Raycast skip + Stream Deck skip
        assert len(confirmations) == 0
        # Only iTerm2 calls (stow + 2 defaults write, no decrypt since exists=False)
        assert mock_runner.run.call_count == 3

    def test_continues_after_iterm2_failure(self, mock_runner):
        # First call (iTerm2) raises, subsequent calls should still run
        call_count = [0]
        original_run = mock_runner.run

        def failing_then_ok(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 1:
                raise RuntimeError("iTerm2 boom")
            return original_run(*args, **kwargs)

        mock_runner.run = MagicMock(side_effect=failing_then_ok)
        with patch.object(
            type(RAYCAST_CONFIG_AGE_PATH), "exists", return_value=False
        ), patch(
            "setup_tui.lib.defaults.STREAMDECK_BACKUP_AGE_PATH",
            RAYCAST_CONFIG_AGE_PATH,
        ):
            messages, confirmations = run_all_imports(mock_runner)
        assert any("iterm2 import failed" in m.lower() for m in messages)
        assert len(messages) == 4


class TestResumeState:
    def test_defaults(self):
        state = ResumeState()
        assert state.is_personalized is False
        assert state.has_origin is False
        assert state.has_commit is False
        assert state.is_pushed is False
        assert state.has_precommit is False
        assert state.has_placeholder_secrets is False
        assert state.pending == []

    def test_pending_is_mutable_default(self):
        """Each instance should get its own pending list."""
        s1 = ResumeState()
        s2 = ResumeState()
        s1.pending.append("task")
        assert s2.pending == []


class TestSecretFieldDeclarations:
    def test_shell_secrets_have_doc_urls(self):
        """Hand-curated shell secrets should have doc_url; auto-detected may not."""
        for sf in SHELL_SECRETS:
            if "(auto-detected" in sf.description:
                continue  # heuristic entries lack hand-tuned metadata
            assert sf.doc_url, f"{sf.key} should have a doc_url"
            assert sf.doc_url.startswith("https://")

    def test_all_fields_have_used_by(self):
        for sf in SHARED_ANSIBLE_VARS + SHELL_SECRETS:
            assert sf.used_by, f"{sf.key} should have a used_by"

    def test_ansible_vars_password_matches_sensitivity(self):
        """Sensitive vars (keys, passwords, tokens) should be masked."""
        sensitive_patterns = ("api_key", "token", "password", "_key")
        non_sensitive_patterns = ("_key_id", "signing_key")  # public key / ID, not secret
        for sf in SHARED_ANSIBLE_VARS:
            if any(p in sf.key for p in sensitive_patterns) and not any(
                p in sf.key for p in non_sensitive_patterns
            ):
                assert sf.password is True, f"{sf.key} is sensitive and should be masked"

    def test_shell_secrets_are_passwords(self):
        """Shell secrets (API keys) should be masked."""
        for sf in SHELL_SECRETS:
            assert sf.password is True, f"{sf.key} should have password=True"

    def test_unique_keys(self):
        """All secret field keys must be unique."""
        all_keys = [sf.key for sf in SHARED_ANSIBLE_VARS + SHELL_SECRETS]
        assert len(all_keys) == len(set(all_keys))


class TestAgeToken:
    def test_token_value(self):
        assert AGE_TOKEN == "${AGE_PUBLIC_KEY}"


# ===========================================================================
# Token replacement (no `ui` param, returns messages)
# ===========================================================================

class TestReplaceTokens:
    def test_substitutes_age_key(self, tmp_repo, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        msgs = replace_tokens(sample_config)

        content = (tmp_repo / ".sops.yaml").read_text()
        assert "${AGE_PUBLIC_KEY}" not in content
        assert sample_config.age_public_key in content
        assert len(msgs) == 4  # one per file

    def test_substitutes_readme_tokens(self, tmp_repo, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        replace_tokens(sample_config)

        content = (tmp_repo / "README.md").read_text()
        assert "${GITHUB_REPO_URL}" not in content
        assert "${GITHUB_USERNAME}" not in content
        assert "${REPO_NAME}" not in content
        assert sample_config.github_username in content
        assert sample_config.repo_name in content

    def test_preserves_bash_variables(self, tmp_repo, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        replace_tokens(sample_config)

        content = (tmp_repo / "setup.sh").read_text()
        assert "${BASH_SOURCE[0]}" in content

    def test_setup_sh_executable_after_replacement(
        self, tmp_repo, sample_config, monkeypatch
    ):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        replace_tokens(sample_config)

        mode = (tmp_repo / "setup.sh").stat().st_mode
        assert mode & 0o755 == 0o755

    def test_substitutes_bootstrap_sh_url(
        self, tmp_repo, sample_config, monkeypatch
    ):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        replace_tokens(sample_config)

        content = (tmp_repo / "bootstrap.sh").read_text()
        assert "${GITHUB_REPO_URL}" not in content
        assert sample_config.github_repo_url in content
        mode = (tmp_repo / "bootstrap.sh").stat().st_mode
        assert mode & 0o755 == 0o755

    def test_returns_status_messages(self, tmp_repo, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        msgs = replace_tokens(sample_config)

        assert isinstance(msgs, list)
        assert all(isinstance(m, str) for m in msgs)
        assert any(".sops.yaml" in m for m in msgs)
        assert any("setup.sh" in m for m in msgs)
        assert any("bootstrap.sh" in m for m in msgs)
        assert any("README.md" in m for m in msgs)

    def test_idempotent(self, tmp_repo, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.tokens.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.tokens.SETUP_SH", tmp_repo / "setup.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.BOOTSTRAP_SH", tmp_repo / "bootstrap.sh")
        monkeypatch.setattr("setup_tui.lib.tokens.README_MD", tmp_repo / "README.md")

        replace_tokens(sample_config)
        content_first = (tmp_repo / ".sops.yaml").read_text()

        replace_tokens(sample_config)
        content_second = (tmp_repo / ".sops.yaml").read_text()

        assert content_first == content_second


# ===========================================================================
# Encryption (no `ui` param, returns tuple)
# ===========================================================================

class TestEncryptSecretFiles:
    def test_returns_count_and_messages(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.encryption.REPO_ROOT", tmp_repo)

        count, msgs = encrypt_secret_files(mock_runner)

        assert count > 0
        assert isinstance(msgs, list)
        assert mock_runner.sops_encrypt_in_place.call_count == count

    def test_skips_already_encrypted(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.encryption.REPO_ROOT", tmp_repo)

        sops_file = tmp_repo / "shared" / "secrets" / "vars.sops.yml"
        sops_file.write_text('sops:\n  age: []\ndata: "ENC[...]"\n')

        count, msgs = encrypt_secret_files(mock_runner)

        encrypted_files = [
            c.args[0] for c in mock_runner.sops_encrypt_in_place.call_args_list
        ]
        assert sops_file not in encrypted_files
        assert any("Already encrypted" in m for m in msgs)

    def test_skips_decrypted_directories(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.encryption.REPO_ROOT", tmp_repo)

        decrypted_dir = tmp_repo / "shared" / "secrets" / ".decrypted"
        decrypted_dir.mkdir()
        (decrypted_dir / "vars.sops.yml").write_text("git_user_email: test@test.com\n")

        count, msgs = encrypt_secret_files(mock_runner)

        encrypted_files = [
            str(c.args[0]) for c in mock_runner.sops_encrypt_in_place.call_args_list
        ]
        assert not any(".decrypted" in f for f in encrypted_files)

    def test_summary_message(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.encryption.REPO_ROOT", tmp_repo)

        count, msgs = encrypt_secret_files(mock_runner)

        assert any(f"Encrypted {count} file(s)" in m for m in msgs)


class TestWriteAndEncrypt:
    def test_no_ui_param(self, tmp_path, mock_runner):
        """write_and_encrypt takes (runner, target, content) — no ui."""
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        write_and_encrypt(mock_runner, target, "key: value")

        assert mock_runner.sops_encrypt_in_place.called

    def test_creates_tmpfile_in_target_directory(self, tmp_path, mock_runner):
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        write_and_encrypt(mock_runner, target, "key: value")

        encrypt_call = mock_runner.sops_encrypt_in_place.call_args
        encrypted_path = encrypt_call.args[0]
        assert str(encrypted_path).startswith(str(target.parent))

    def test_content_written_before_encryption(self, tmp_path, mock_runner):
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        written_content = None

        def capture_encrypt(path):
            nonlocal written_content
            written_content = path.read_text()

        mock_runner.sops_encrypt_in_place = capture_encrypt

        write_and_encrypt(mock_runner, target, "---\nkey: value")

        assert written_content is not None
        assert "key: value" in written_content

    def test_cleanup_on_failure(self, tmp_path, mock_runner):
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        mock_runner.sops_encrypt_in_place = MagicMock(
            side_effect=subprocess.CalledProcessError(1, "sops")
        )

        with pytest.raises(EncryptionError):
            write_and_encrypt(mock_runner, target, "key: value")

        tmpfiles = list(target.parent.glob(".tmp.*"))
        assert len(tmpfiles) == 0

    def test_target_file_created(self, tmp_path, mock_runner):
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        write_and_encrypt(mock_runner, target, "key: value")

        assert target.exists()

    def test_creates_parent_dirs(self, tmp_path, mock_runner):
        target = tmp_path / "deep" / "nested" / "secrets" / "vars.sops.yml"

        write_and_encrypt(mock_runner, target, "key: value")

        assert target.exists()


# ===========================================================================
# State detection
# ===========================================================================

class TestDetectResumeState:
    def test_unpersonalized(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", tmp_repo / ".sops.yaml")
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        state = detect_resume_state(mock_runner)

        assert state.is_personalized is False
        assert not state.pending

    def test_personalized(self, tmp_repo, mock_runner, monkeypatch):
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("creation_rules:\n  - age: 'age1abc123'\n")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )
        mock_runner.sops_decrypt = MagicMock(return_value="git_user_email: PLACEHOLDER")

        state = detect_resume_state(mock_runner)

        assert state.is_personalized is True
        assert state.has_placeholder_secrets is True

    def test_pending_steps_populated(self, tmp_repo, mock_runner, monkeypatch):
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("age: 'age1real'")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )
        mock_runner.sops_decrypt = MagicMock(return_value="")

        state = detect_resume_state(mock_runner)
        assert "set up GitHub remote" in state.pending
        assert "install pre-commit hooks" in state.pending

    def test_precommit_detected(self, tmp_repo, mock_runner, monkeypatch):
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("age: 'age1real'")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        hook = tmp_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/bash\n")

        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )
        mock_runner.sops_decrypt = MagicMock(return_value="")

        state = detect_resume_state(mock_runner)
        assert state.has_precommit is True
        assert "install pre-commit hooks" not in state.pending

    def test_no_placeholder_when_secrets_have_values(
        self, tmp_repo, mock_runner, monkeypatch
    ):
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("age: 'age1real'")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        vars_file = tmp_repo / "shared" / "secrets" / "vars.sops.yml"
        vars_file.write_text('sops:\n  age: []\n')
        mock_runner.sops_decrypt = MagicMock(
            return_value='git_user_email: "real@email.com"'
        )
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        state = detect_resume_state(mock_runner)
        assert state.has_placeholder_secrets is False

    def test_skips_sops_when_not_installed(
        self, tmp_repo, mock_runner, monkeypatch
    ):
        """When sops is not installed, sops_decrypt should not be called."""
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("age: 'age1real'")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        # Encrypted file without PLACEHOLDER in raw text.
        vars_file = tmp_repo / "shared" / "secrets" / "vars.sops.yml"
        vars_file.write_text('sops:\n  age: []\ndata: "ENC[AES256_GCM]"\n')

        mock_runner.command_exists = MagicMock(return_value=False)
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        state = detect_resume_state(mock_runner)

        mock_runner.sops_decrypt.assert_not_called()
        assert state.has_placeholder_secrets is False

    def test_calls_sops_when_installed(
        self, tmp_repo, mock_runner, monkeypatch
    ):
        """When sops is installed, sops_decrypt should be called for encrypted files."""
        sops = tmp_repo / ".sops.yaml"
        sops.write_text("age: 'age1real'")
        monkeypatch.setattr("setup_tui.lib.state.SOPS_YAML", sops)
        monkeypatch.setattr("setup_tui.lib.state.REPO_ROOT", tmp_repo)

        # Encrypted file without PLACEHOLDER in raw text.
        vars_file = tmp_repo / "shared" / "secrets" / "vars.sops.yml"
        vars_file.write_text('sops:\n  age: []\ndata: "ENC[AES256_GCM]"\n')

        mock_runner.command_exists = MagicMock(return_value=True)
        mock_runner.sops_decrypt = MagicMock(return_value="git_user_email: PLACEHOLDER")
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        state = detect_resume_state(mock_runner)

        mock_runner.sops_decrypt.assert_called_once()
        assert state.has_placeholder_secrets is True


class TestExtractResumeConfig:
    def test_extracts_from_setup_sh(self, tmp_repo, mock_runner, monkeypatch):
        setup_sh = tmp_repo / "setup.sh"
        setup_sh.write_text(
            '#!/usr/bin/env bash\n'
            'git clone "https://github.com/myuser/my-ws.git" ~/.workstation\n'
        )
        monkeypatch.setattr("setup_tui.lib.state.SETUP_SH", setup_sh)
        monkeypatch.setattr("setup_tui.lib.state.AGE_KEY_PATH", tmp_repo / "nokey")

        mock_runner.age_public_key_from_file = MagicMock(return_value="")
        mock_runner.run = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        config = extract_resume_config(mock_runner)

        assert config.github_username == "myuser"
        assert config.repo_name == "my-ws"
        assert config.github_repo_url == "https://github.com/myuser/my-ws.git"

    def test_falls_back_to_git_remote(self, tmp_repo, mock_runner, monkeypatch):
        setup_sh = tmp_repo / "setup.sh"
        setup_sh.write_text("#!/usr/bin/env bash\necho hello\n")  # no URL
        monkeypatch.setattr("setup_tui.lib.state.SETUP_SH", setup_sh)
        monkeypatch.setattr("setup_tui.lib.state.AGE_KEY_PATH", tmp_repo / "nokey")

        mock_runner.age_public_key_from_file = MagicMock(return_value="")
        mock_runner.run = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="https://github.com/remoteuser/remote-repo.git",
                stderr=""
            )
        )

        config = extract_resume_config(mock_runner)

        assert config.github_username == "remoteuser"
        assert config.repo_name == "remote-repo"

    def test_raises_if_no_url_found(self, tmp_repo, mock_runner, monkeypatch):
        setup_sh = tmp_repo / "setup.sh"
        setup_sh.write_text("#!/usr/bin/env bash\necho hello\n")
        monkeypatch.setattr("setup_tui.lib.state.SETUP_SH", setup_sh)
        monkeypatch.setattr("setup_tui.lib.state.AGE_KEY_PATH", tmp_repo / "nokey")

        mock_runner.age_public_key_from_file = MagicMock(return_value="")
        mock_runner.run = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        with pytest.raises(RuntimeError, match="Could not determine repo info"):
            extract_resume_config(mock_runner)

    def test_loads_existing_age_key(self, tmp_repo, mock_runner, monkeypatch):
        key_file = tmp_repo / "keys.txt"
        key_file.write_text("AGE-SECRET-KEY-1ABC\n")
        monkeypatch.setattr("setup_tui.lib.state.AGE_KEY_PATH", key_file)

        setup_sh = tmp_repo / "setup.sh"
        setup_sh.write_text(
            'git clone "https://github.com/u/r.git" ~/.workstation\n'
        )
        monkeypatch.setattr("setup_tui.lib.state.SETUP_SH", setup_sh)

        mock_runner.age_public_key_from_file = MagicMock(return_value="age1pubkey")

        config = extract_resume_config(mock_runner)

        assert config.age_public_key == "age1pubkey"
        mock_runner.age_public_key_from_file.assert_called_once_with(key_file)


# ===========================================================================
# Git operations (no `ui` param, no confirm prompt)
# ===========================================================================

class TestDetachFromTemplate:
    def test_no_origin_returns_none(self, mock_runner, sample_config):
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr=""
            )
        )

        result = detach_from_template(mock_runner, sample_config)

        assert result is None

    def test_matching_origin(self, mock_runner, sample_config):
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="https://github.com/testuser/my-workstation.git",
                stderr="",
            )
        )

        result = detach_from_template(mock_runner, sample_config)

        assert "already points to" in result

    def test_mismatched_origin(self, mock_runner, sample_config):
        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="https://github.com/template-owner/template-repo.git",
                stderr="",
            )
        )

        result = detach_from_template(mock_runner, sample_config)

        assert "does not match" in result
        assert "template-owner" in result


class TestRemoveOrigin:
    def test_calls_git_remote_remove(self, mock_runner):
        remove_origin(mock_runner)
        mock_runner.git.assert_called_once_with("remote", "remove", "origin")


class TestCreateGithubRepo:
    def test_creates_new_repo(self, mock_runner, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", Path("/tmp/test"))

        # gh auth ok, repo doesn't exist, creation succeeds.
        def gh_side_effect(*args, **kwargs):
            if args[:2] == ("auth", "status"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("repo", "view"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.gh = MagicMock(side_effect=gh_side_effect)

        msgs = create_github_repo(mock_runner, sample_config)

        assert any("Creating" in m for m in msgs)
        assert any("Remote set to" in m for m in msgs)

    def test_existing_repo_adds_remote(self, mock_runner, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", Path("/tmp/test"))

        def gh_side_effect(*args, **kwargs):
            if args[:2] == ("auth", "status"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("repo", "view"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="exists", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.gh = MagicMock(side_effect=gh_side_effect)

        msgs = create_github_repo(mock_runner, sample_config)

        assert any("already exists" in m for m in msgs)
        mock_runner.git.assert_called_once_with(
            "remote", "add", "origin", sample_config.github_repo_url
        )

    def test_public_repo_flag(self, mock_runner, sample_config, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", Path("/tmp/test"))

        def gh_side_effect(*args, **kwargs):
            if args[:2] == ("auth", "status"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("repo", "view"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.gh = MagicMock(side_effect=gh_side_effect)

        create_github_repo(mock_runner, sample_config, public=True)

        create_call = [
            c for c in mock_runner.gh.call_args_list
            if len(c.args) >= 2 and c.args[:2] == ("repo", "create")
        ]
        assert len(create_call) == 1
        assert "--public" in create_call[0].args


class TestCommitAndPush:
    def test_returns_messages(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
        )

        msgs = commit_and_push(mock_runner)

        assert isinstance(msgs, list)
        assert len(msgs) > 0

    def test_stages_personalized_files(self, mock_runner, tmp_repo, monkeypatch):
        """Commit stages all personalized config files."""
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        commit_and_push(mock_runner)

        mock_runner.git.assert_any_call(
            "add", ".sops.yaml", "setup.sh", "bootstrap.sh", "README.md"
        )

    def test_nothing_to_commit(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        msgs = commit_and_push(mock_runner)

        assert any("Nothing to commit" in m for m in msgs)
        commit_calls = [
            c for c in mock_runner.git.call_args_list
            if len(c.args) >= 1 and c.args[0] == "commit"
        ]
        assert len(commit_calls) == 0

    def test_no_origin_skips_push(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        msgs = commit_and_push(mock_runner)

        assert any("Committed locally" in m for m in msgs)
        push_calls = [
            c for c in mock_runner.git.call_args_list
            if len(c.args) >= 1 and c.args[0] == "push"
        ]
        assert len(push_calls) == 0

    def test_refuses_push_on_unrelated_history(
        self, mock_runner, tmp_repo, monkeypatch
    ):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0,
                    stdout="https://github.com/u/r.git", stderr=""
                )
            if args[:3] == ("ls-remote", "--refs", "origin"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0,
                    stdout="abc123\tHEAD", stderr=""
                )
            if args[0] == "merge-base":
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        msgs = commit_and_push(mock_runner)

        assert any("don't share history" in m or "Refusing" in m for m in msgs)
        push_calls = [
            c for c in mock_runner.git.call_args_list
            if len(c.args) >= 1 and c.args[0] == "push"
        ]
        assert len(push_calls) == 0

    def test_successful_push(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0,
                    stdout="https://github.com/u/r.git", stderr=""
                )
            if args[:3] == ("ls-remote", "--refs", "origin"):
                # Empty remote (new repo, no commits).
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        msgs = commit_and_push(mock_runner)

        assert any("Pushed" in m for m in msgs)

    def test_push_failure_workflow_hint(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_repo)

        def git_side_effect(*args, **kwargs):
            if args == ("diff", "--cached", "--quiet"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[:2] == ("remote", "get-url"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0,
                    stdout="https://github.com/u/r.git", stderr=""
                )
            if args[:3] == ("ls-remote", "--refs", "origin"):
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                )
            if args[0] == "push":
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="",
                    stderr="refusing to allow a GitHub workflow to push"
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )

        mock_runner.git = MagicMock(side_effect=git_side_effect)

        msgs = commit_and_push(mock_runner)

        assert any("workflow" in m for m in msgs)

    def test_initializes_git_if_no_git_dir(self, mock_runner, tmp_path, monkeypatch):
        """If .git doesn't exist, should git init + branch -M main."""
        monkeypatch.setattr("setup_tui.lib.git_ops.REPO_ROOT", tmp_path)

        mock_runner.git = MagicMock(
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
        )

        commit_and_push(mock_runner)

        mock_runner.git.assert_any_call("init")
        mock_runner.git.assert_any_call("branch", "-M", "main")


# ===========================================================================
# Age key
# ===========================================================================

class TestGenerateOrLoadAgeKey:
    def test_generates_new_key(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        status, pubkey = generate_or_load_age_key(mock_runner)

        assert "generated" in status.lower()
        assert pubkey == "age1abc"
        assert key_path.exists()
        assert key_path.read_text() == "private-key\n"
        mock_runner.age_keygen.assert_called_once()

    def test_loads_existing_key(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        key_path.write_text("AGE-SECRET-KEY-1ABC\n")
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        status, pubkey = generate_or_load_age_key(mock_runner)

        assert "exists" in status.lower()
        assert pubkey == "age1abc"
        mock_runner.age_keygen.assert_not_called()

    def test_raises_on_missing_public_key(self, mock_runner, tmp_path, monkeypatch):
        key_file = tmp_path / "keys.txt"
        key_file.write_text("# existing but bad\n")
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_file)

        mock_runner.age_public_key_from_file = MagicMock(return_value="")

        with pytest.raises(AgeKeyError):
            generate_or_load_age_key(mock_runner)

    def test_raises_on_empty_keygen_output(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        mock_runner.age_keygen = MagicMock(return_value=("private-key", ""))

        with pytest.raises(AgeKeyError, match="did not produce"):
            generate_or_load_age_key(mock_runner)

    def test_key_file_permissions(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "subdir" / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        generate_or_load_age_key(mock_runner)

        assert key_path.stat().st_mode & 0o777 == 0o600
        assert key_path.parent.stat().st_mode & 0o777 == 0o700


class TestLoadAgeKey:
    def test_loads_existing_key(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        key_path.write_text("AGE-SECRET-KEY-1ABC\n")
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        status, pubkey = load_age_key(mock_runner)

        assert "exists" in status.lower()
        assert pubkey == "age1abc"

    def test_raises_file_not_found_if_missing(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "nonexistent" / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        with pytest.raises(FileNotFoundError):
            load_age_key(mock_runner)

    def test_raises_age_key_error_on_bad_key(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        key_path.write_text("# corrupt key\n")
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        mock_runner.age_public_key_from_file = MagicMock(return_value="")

        with pytest.raises(AgeKeyError):
            load_age_key(mock_runner)


class TestGenerateAgeKey:
    def test_generates_new_key(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        status, pubkey = generate_age_key(mock_runner)

        assert "generated" in status.lower()
        assert pubkey == "age1abc"
        assert key_path.exists()
        assert key_path.read_text() == "private-key\n"
        mock_runner.age_keygen.assert_called_once()

    def test_raises_on_empty_keygen_output(self, mock_runner, tmp_path, monkeypatch):
        key_path = tmp_path / "keys.txt"
        monkeypatch.setattr("setup_tui.lib.age.AGE_KEY_PATH", key_path)

        mock_runner.age_keygen = MagicMock(return_value=("private-key", ""))

        with pytest.raises(AgeKeyError, match="did not produce"):
            generate_age_key(mock_runner)


# ===========================================================================
# Secrets load/save helpers
# ===========================================================================

class TestLoadExistingAnsibleVars:
    def test_loads_decrypted_yaml(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(
            return_value='---\ngit_user_email: "test@example.com"\ngit_user_name: "Test"\n'
        )

        result = load_existing_ansible_vars(mock_runner)

        assert result["git_user_email"] == "test@example.com"
        assert result["git_user_name"] == "Test"

    def test_skips_placeholder_values(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(
            return_value='---\ngit_user_email: PLACEHOLDER\n'
        )

        result = load_existing_ansible_vars(mock_runner)

        assert "git_user_email" not in result

    def test_missing_file_returns_empty(self, tmp_path, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_path)

        result = load_existing_ansible_vars(mock_runner)

        assert result == {}

    def test_skips_comments_and_separators(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(
            return_value='---\n# comment\ngit_user_email: "a@b.com"\n'
        )

        result = load_existing_ansible_vars(mock_runner)

        assert "git_user_email" in result
        assert len(result) == 1  # no comment key


class TestLoadExistingShellExports:
    def test_loads_export_statements(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(
            return_value='# Shell secrets\nexport ANTHROPIC_API_KEY="sk-ant-123"\nexport OTHER="val"\n'
        )

        result = load_existing_shell_exports(mock_runner)

        assert result["ANTHROPIC_API_KEY"] == "sk-ant-123"
        assert result["OTHER"] == "val"

    def test_skips_non_export_lines(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(
            return_value='# comment\nexport KEY="val"\nsome other line\n'
        )

        result = load_existing_shell_exports(mock_runner)

        assert len(result) == 1
        assert result["KEY"] == "val"

    def test_missing_file_returns_empty(self, tmp_path, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_path)

        result = load_existing_shell_exports(mock_runner)

        assert result == {}


class TestSaveAnsibleVars:
    def test_writes_yaml_and_encrypts(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        written_content = None

        def capture_encrypt(path):
            nonlocal written_content
            written_content = path.read_text()

        mock_runner.sops_encrypt_in_place = capture_encrypt

        save_ansible_vars(mock_runner, {
            "git_user_email": "a@b.com",
            "git_user_name": "Test",
        })

        assert written_content is not None
        assert 'git_user_email: "a@b.com"' in written_content
        assert 'git_user_name: "Test"' in written_content
        assert written_content.startswith("---\n")


class TestSaveShellExports:
    def test_writes_exports_and_encrypts(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        written_content = None

        def capture_encrypt(path):
            nonlocal written_content
            written_content = path.read_text()

        mock_runner.sops_encrypt_in_place = capture_encrypt

        save_shell_exports(mock_runner, {
            "ANTHROPIC_API_KEY": "sk-ant-123",
            "OTHER_KEY": "val",
        })

        assert written_content is not None
        assert 'export ANTHROPIC_API_KEY="sk-ant-123"' in written_content
        assert 'export OTHER_KEY="val"' in written_content
        assert "Shell secrets" in written_content

    def test_empty_dict_no_write(self, tmp_repo, mock_runner, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.secrets.REPO_ROOT", tmp_repo)

        save_shell_exports(mock_runner, {})

        mock_runner.sops_encrypt_in_place.assert_not_called()


# ===========================================================================
# Prereqs
# ===========================================================================

class TestInstallPrecommit:
    def test_already_installed(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        hook = tmp_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/bash\n")

        msgs = install_precommit(mock_runner)

        assert any("already installed" in m for m in msgs)

    def test_installs_via_uv(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        hook = tmp_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/bash\n")

        call_count = [0]

        def command_exists(cmd):
            if cmd == "pre-commit":
                call_count[0] += 1
                return call_count[0] > 1  # False first, True after "install"
            return cmd == "uv"

        mock_runner.command_exists = MagicMock(side_effect=command_exists)

        msgs = install_precommit(mock_runner)

        assert any("Installing pre-commit" in m for m in msgs)
        mock_runner.run.assert_any_call(["uv", "tool", "install", "pre-commit"])

    def test_installs_via_pip3_fallback(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        hook = tmp_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/bash\n")

        call_count = [0]

        def command_exists(cmd):
            if cmd == "pre-commit":
                call_count[0] += 1
                return call_count[0] > 1
            if cmd == "uv":
                return False
            return cmd == "pip3"

        mock_runner.command_exists = MagicMock(side_effect=command_exists)

        install_precommit(mock_runner)

        mock_runner.run.assert_any_call(
            ["pip3", "install", "--user", "pre-commit"]
        )

    def test_raises_if_no_installer(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        def command_exists(cmd):
            return False  # Nothing is available.

        mock_runner.command_exists = MagicMock(side_effect=command_exists)

        with pytest.raises(RuntimeError, match="Neither uv nor pip3"):
            install_precommit(mock_runner)

    def test_raises_if_install_fails(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        def command_exists(cmd):
            if cmd == "pre-commit":
                return False  # Never succeeds.
            return cmd == "uv"

        mock_runner.command_exists = MagicMock(side_effect=command_exists)

        with pytest.raises(RuntimeError, match="installation failed"):
            install_precommit(mock_runner)

    def test_raises_if_hook_not_created(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        # pre-commit exists, but hook file doesn't get created.
        mock_runner.command_exists = MagicMock(return_value=True)
        # Don't create the hook file — .git/hooks/pre-commit won't exist.

        with pytest.raises(RuntimeError, match="not installed into .git/hooks"):
            install_precommit(mock_runner)

    def test_installs_hooks_in_git_repo(self, mock_runner, tmp_repo, monkeypatch):
        monkeypatch.setattr("setup_tui.lib.prereqs.REPO_ROOT", tmp_repo)

        hook = tmp_repo / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/bash\n")

        install_precommit(mock_runner)

        mock_runner.run.assert_any_call(
            ["pre-commit", "install"], cwd=tmp_repo
        )


# ===========================================================================
# Logging
# ===========================================================================

class TestSetupLogging:
    def test_creates_log_directory(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "log"
        log_file = log_dir / "setup.log"
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_DIR", log_dir)
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_FILE", log_file)

        # Clear any existing handlers from prior tests.
        logger = logging.getLogger("setup")
        logger.handlers.clear()

        setup_logging(debug=False)

        assert log_dir.exists()

    def test_writes_to_log_file(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "log"
        log_file = log_dir / "setup.log"
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_DIR", log_dir)
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_FILE", log_file)

        logger = logging.getLogger("setup")
        logger.handlers.clear()

        setup_logging(debug=False)

        assert log_file.exists()
        content = log_file.read_text()
        assert "setup.py" in content
        assert "platform:" in content

    def test_debug_adds_console_handler(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "log"
        log_file = log_dir / "setup.log"
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_DIR", log_dir)
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_FILE", log_file)

        logger = logging.getLogger("setup")
        logger.handlers.clear()

        setup_logging(debug=True)

        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler in handler_types
        assert logging.FileHandler in handler_types

    def test_no_console_handler_without_debug(self, tmp_path, monkeypatch):
        log_dir = tmp_path / "log"
        log_file = log_dir / "setup.log"
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_DIR", log_dir)
        monkeypatch.setattr("setup_tui.lib.setup_logging.LOG_FILE", log_file)

        logger = logging.getLogger("setup")
        logger.handlers.clear()

        setup_logging(debug=False)

        handler_types = [type(h) for h in logger.handlers]
        assert logging.StreamHandler not in handler_types
        assert logging.FileHandler in handler_types

    def test_log_constants(self):
        assert LOG_DIR == Path.home() / ".local" / "log"
        assert LOG_FILE == Path.home() / ".local" / "log" / "setup.log"


# ===========================================================================
# ToolRunner
# ===========================================================================

class TestToolRunner:
    def test_init_debug_flag(self):
        runner = ToolRunner(debug=True)
        assert runner.debug is True

        runner2 = ToolRunner(debug=False)
        assert runner2.debug is False

    def test_command_exists_true(self):
        runner = ToolRunner()
        assert runner.command_exists("python3") is True

    def test_command_exists_false(self):
        runner = ToolRunner()
        assert runner.command_exists("nonexistent_command_xyz_123") is False

    def test_repo_root_is_valid(self):
        """REPO_ROOT should point to the actual repo root."""
        assert REPO_ROOT.is_dir()
        assert (REPO_ROOT / "Makefile").exists()

    def test_run_missing_binary_check_false(self):
        """Missing binary with check=False returns returncode 127."""
        runner = ToolRunner()
        result = runner.run(
            ["nonexistent_binary_xyz_123", "--version"], check=False
        )
        assert result.returncode == 127
        assert "Command not found" in result.stderr

    def test_run_missing_binary_check_true(self):
        """Missing binary with check=True raises FileNotFoundError."""
        runner = ToolRunner()
        with pytest.raises(FileNotFoundError, match="Command not found"):
            runner.run(["nonexistent_binary_xyz_123", "--version"], check=True)


# ---------------------------------------------------------------------------
# Stream Deck plugin scanner
# ---------------------------------------------------------------------------

SAMPLE_MANIFEST = {
    "Name": "Counter",
    "UUID": "com.elgato.counter",
    "Version": "1.4",
    "URL": "https://marketplace.elgato.com/product/counter",
}


@pytest.fixture
def fake_plugins_dir(tmp_path):
    """Create a mock Plugins/ directory with sample .sdPlugin bundles."""
    plugins = tmp_path / "Plugins"
    plugins.mkdir()

    # Plugin with full manifest
    p1 = plugins / "com.elgato.counter.sdPlugin"
    p1.mkdir()
    (p1 / "manifest.json").write_text(json.dumps(SAMPLE_MANIFEST))

    # Plugin without URL — should get marketplace fallback
    p2 = plugins / "com.vendor.nourl.sdPlugin"
    p2.mkdir()
    (p2 / "manifest.json").write_text(json.dumps({
        "Name": "No URL Plugin",
        "UUID": "com.vendor.nourl",
        "Version": "2.0",
    }))

    # Directory that isn't .sdPlugin — should be ignored
    misc = plugins / "SomeOtherDir"
    misc.mkdir()

    # .sdPlugin without manifest.json — should be ignored
    empty = plugins / "com.broken.empty.sdPlugin"
    empty.mkdir()

    return plugins


class TestScanStreamdeckPlugins:
    def test_returns_list_of_dicts(self, fake_plugins_dir):
        result = scan_streamdeck_plugins(fake_plugins_dir)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_dict_structure(self, fake_plugins_dir):
        result = scan_streamdeck_plugins(fake_plugins_dir)
        for p in result:
            assert set(p.keys()) == {"name", "uuid", "url", "version"}

    def test_reads_manifest_fields(self, fake_plugins_dir):
        result = scan_streamdeck_plugins(fake_plugins_dir)
        counter = next(p for p in result if p["uuid"] == "com.elgato.counter")
        assert counter["name"] == "Counter"
        assert counter["version"] == "1.4"
        assert counter["url"] == "https://marketplace.elgato.com/product/counter"

    def test_fallback_url_when_missing(self, fake_plugins_dir):
        result = scan_streamdeck_plugins(fake_plugins_dir)
        nourl = next(p for p in result if p["uuid"] == "com.vendor.nourl")
        assert nourl["url"] == "https://marketplace.elgato.com/stream-deck/plugins"

    def test_empty_list_for_missing_dir(self, tmp_path):
        result = scan_streamdeck_plugins(tmp_path / "nonexistent")
        assert result == []

    def test_skips_invalid_json(self, fake_plugins_dir):
        bad = fake_plugins_dir / "com.bad.json.sdPlugin"
        bad.mkdir()
        (bad / "manifest.json").write_text("{invalid json")
        result = scan_streamdeck_plugins(fake_plugins_dir)
        # Still only the 2 valid plugins
        assert len(result) == 2


class TestExportStreamdeckPluginList:
    def test_writes_json_and_html(self, fake_plugins_dir, tmp_path):
        json_out = tmp_path / "plugins.json"
        html_out = tmp_path / "plugins.html"
        msg = export_streamdeck_plugin_list(
            plugins_dir=fake_plugins_dir,
            json_path=json_out,
            html_path=html_out,
            backup_path=tmp_path / "nonexistent.zip",
        )

        assert json_out.exists()
        assert html_out.exists()
        assert "2 plugins" in msg

    def test_json_is_valid(self, fake_plugins_dir, tmp_path):
        json_out = tmp_path / "plugins.json"
        html_out = tmp_path / "plugins.html"
        export_streamdeck_plugin_list(
            plugins_dir=fake_plugins_dir,
            json_path=json_out,
            html_path=html_out,
            backup_path=tmp_path / "nonexistent.zip",
        )
        data = json.loads(json_out.read_text())
        assert isinstance(data, list)
        assert len(data) == 2
        assert all("uuid" in p for p in data)

    def test_html_contains_plugin_names(self, fake_plugins_dir, tmp_path):
        json_out = tmp_path / "plugins.json"
        html_out = tmp_path / "plugins.html"
        export_streamdeck_plugin_list(
            plugins_dir=fake_plugins_dir,
            json_path=json_out,
            html_path=html_out,
            backup_path=tmp_path / "nonexistent.zip",
        )
        html = html_out.read_text()
        assert "Counter" in html
        assert "No URL Plugin" in html
        assert "Stream Deck Plugins" in html

    def test_empty_plugins_dir(self, tmp_path):
        empty_dir = tmp_path / "empty_plugins"
        empty_dir.mkdir()
        json_out = tmp_path / "plugins.json"
        html_out = tmp_path / "plugins.html"
        msg = export_streamdeck_plugin_list(
            plugins_dir=empty_dir,
            json_path=json_out,
            html_path=html_out,
            backup_path=tmp_path / "nonexistent.zip",
        )
        assert "0 plugins" in msg
        assert json.loads(json_out.read_text()) == []


# ---------------------------------------------------------------------------
# _normalize_keybinding / save_action_registry normalization
# ---------------------------------------------------------------------------


class TestNormalizeKeybinding:
    """Verify that _normalize_keybinding fixes macOS-isms and punctuation."""

    def test_opt_normalized_to_alt(self):
        kb = {
            "linux": "<Ctrl><Opt>Left",
            "macos": {"mods": ["ctrl", "opt"], "key": "left"},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Ctrl><Alt>Left"
        assert kb["macos"]["mods"] == ["ctrl", "alt"]

    def test_option_normalized(self):
        kb = {
            "linux": "<Option>v",
            "macos": {"mods": ["option"], "key": "v"},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Alt>v"
        assert kb["macos"]["mods"] == ["alt"]

    def test_command_normalized(self):
        kb = {
            "linux": "<Command>space",
            "macos": {"mods": ["command"], "key": "space"},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Super>space"
        assert kb["macos"]["mods"] == ["cmd"]

    def test_control_normalized(self):
        kb = {
            "linux": "<Control>x",
            "macos": {"mods": ["control"], "key": "x"},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Ctrl>x"
        assert kb["macos"]["mods"] == ["ctrl"]

    def test_period_key_normalized_linux(self):
        """Linux dconf needs keysym 'period'; macOS keeps bare '.'."""
        kb = {
            "linux": "<Alt>.",
            "macos": {"mods": ["alt"], "key": "."},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Alt>period"
        assert kb["macos"]["key"] == "."

    def test_valid_modifiers_unchanged(self):
        kb = {
            "linux": "<Ctrl><Alt>Left",
            "macos": {"mods": ["ctrl", "alt"], "key": "left"},
        }
        _normalize_keybinding(kb)
        assert kb["linux"] == "<Ctrl><Alt>Left"
        assert kb["macos"]["mods"] == ["ctrl", "alt"]

    def test_unknown_linux_modifier_raises(self):
        kb = {"linux": "<Foo>v", "macos": {"mods": ["alt"], "key": "v"}}
        with pytest.raises(ValueError, match="Unknown Linux modifier.*Foo"):
            _normalize_keybinding(kb)

    def test_unknown_macos_modifier_raises(self):
        kb = {"linux": "<Alt>v", "macos": {"mods": ["foo"], "key": "v"}}
        with pytest.raises(ValueError, match="Unknown macOS modifier.*foo"):
            _normalize_keybinding(kb)

    def test_save_round_trip_normalizes(self, tmp_path):
        """save_action_registry normalizes, then load reads back correct values."""
        yml = tmp_path / "main.yml"
        actions = [
            {
                "action": "test_action",
                "description": "Test",
                "keybinding": {
                    "linux": "<Command><Opt>v",
                    "macos": {"mods": ["command", "option"], "key": "v"},
                },
            }
        ]
        save_action_registry(actions, path=yml)
        reloaded = load_action_registry(path=yml)
        kb = reloaded[0]["keybinding"]
        assert kb["linux"] == "<Super><Alt>v"
        assert kb["macos"]["mods"] == ["cmd", "alt"]
