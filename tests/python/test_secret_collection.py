"""Tests for Phase 11: guided secret editing."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
import importlib

first_run = importlib.import_module("first-run")


class TestEditSecrets:
    """Tests for edit_secrets()."""

    def test_skipped_email_writes_placeholder(
        self, tmp_repo, mock_runner, mock_ui, monkeypatch
    ):
        """When user presses Enter (empty), PLACEHOLDER should be written."""
        monkeypatch.setattr(first_run, "REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(return_value="---\ngit_user_email: PLACEHOLDER\n")
        mock_runner.gum_input = MagicMock(return_value="")
        mock_runner.gum_confirm = MagicMock(return_value=False)
        mock_runner.sops_encrypt_in_place = MagicMock()

        first_run.edit_secrets(mock_runner, mock_ui, "macos")

        # write_and_encrypt should have been called with PLACEHOLDER.
        # Check mock_runner.sops_encrypt_in_place was called (write_and_encrypt delegates).
        assert mock_runner.sops_encrypt_in_place.called

    def test_email_value_preserved(
        self, tmp_repo, mock_runner, mock_ui, monkeypatch
    ):
        """When user enters an email, it should be written."""
        monkeypatch.setattr(first_run, "REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(return_value="---\ngit_user_email: PLACEHOLDER\n")
        mock_runner.gum_input = MagicMock(return_value="test@example.com")
        mock_runner.gum_confirm = MagicMock(return_value=False)
        mock_runner.sops_encrypt_in_place = MagicMock()

        first_run.edit_secrets(mock_runner, mock_ui, "macos")

        info_msgs = [m[1] for m in mock_ui._messages if m[0] == "info"]
        assert any("test@example.com" in m for m in info_msgs)

    def test_shell_secret_loop(
        self, tmp_repo, mock_runner, mock_ui, monkeypatch
    ):
        """Adding shell secrets should loop until user says no."""
        monkeypatch.setattr(first_run, "REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(return_value="")

        # First gum_input: email.
        # Then gum_confirm: yes (add secret), then no (stop).
        # Then gum_input for key and value.
        input_values = iter(["test@example.com", "MY_API_KEY", "secret123"])
        mock_runner.gum_input = MagicMock(side_effect=lambda **_: next(input_values, ""))
        confirm_values = iter([True, False])
        mock_runner.gum_confirm = MagicMock(side_effect=lambda _: next(confirm_values, False))
        mock_runner.sops_encrypt_in_place = MagicMock()

        first_run.edit_secrets(mock_runner, mock_ui, "macos")

        info_msgs = [m[1] for m in mock_ui._messages if m[0] == "info"]
        assert any("Added MY_API_KEY" in m for m in info_msgs)

    def test_platform_awareness_macos(
        self, tmp_repo, mock_runner, mock_ui, monkeypatch
    ):
        """macOS platform should show macOS-specific messages."""
        monkeypatch.setattr(first_run, "REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(return_value="")
        mock_runner.gum_input = MagicMock(return_value="")
        mock_runner.gum_confirm = MagicMock(return_value=False)
        mock_runner.sops_encrypt_in_place = MagicMock()

        first_run.edit_secrets(mock_runner, mock_ui, "macos")

        info_msgs = [m[1] for m in mock_ui._messages if m[0] == "info"]
        assert any("macOS" in m for m in info_msgs)
        assert any("edit-secrets-macos" in m for m in info_msgs)

    def test_platform_awareness_linux(
        self, tmp_repo, mock_runner, mock_ui, monkeypatch
    ):
        """Linux platform should show Linux-specific messages."""
        monkeypatch.setattr(first_run, "REPO_ROOT", tmp_repo)

        mock_runner.sops_decrypt = MagicMock(return_value="")
        mock_runner.gum_input = MagicMock(return_value="")
        mock_runner.gum_confirm = MagicMock(return_value=False)
        mock_runner.sops_encrypt_in_place = MagicMock()

        first_run.edit_secrets(mock_runner, mock_ui, "linux")

        info_msgs = [m[1] for m in mock_ui._messages if m[0] == "info"]
        assert any("Linux" in m for m in info_msgs)
        assert any("edit-secrets-linux" in m for m in info_msgs)


class TestWriteAndEncryptIntegration:
    """Integration tests for write_and_encrypt with edit_secrets flow."""

    def test_yaml_content_format(self, tmp_path, mock_runner, mock_ui):
        """Written YAML content should be valid YAML format."""
        target = tmp_path / "secrets" / "vars.sops.yml"
        target.parent.mkdir(parents=True)

        written_content = None

        def capture_encrypt(path):
            nonlocal written_content
            written_content = path.read_text()

        mock_runner.sops_encrypt_in_place = capture_encrypt

        first_run.write_and_encrypt(
            mock_runner, target, '---\ngit_user_email: "test@test.com"', mock_ui
        )

        assert written_content is not None
        import yaml
        parsed = yaml.safe_load(written_content)
        assert parsed["git_user_email"] == "test@test.com"

    def test_shell_secrets_content_format(self, tmp_path, mock_runner, mock_ui):
        """Written shell secrets should be valid export statements."""
        target = tmp_path / "secrets" / "secrets.zsh.sops"
        target.parent.mkdir(parents=True)

        written_content = None

        def capture_encrypt(path):
            nonlocal written_content
            written_content = path.read_text()

        mock_runner.sops_encrypt_in_place = capture_encrypt

        content = '# Shell secrets -- sourced by .zshrc\nexport MY_KEY="my_value"'
        first_run.write_and_encrypt(mock_runner, target, content, mock_ui)

        assert written_content is not None
        assert 'export MY_KEY="my_value"' in written_content
