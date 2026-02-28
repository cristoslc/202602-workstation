"""Tests for @tui annotation scanner (var_scanner.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.lib.var_scanner import (
    ScannedVar,
    UnannotatedCandidate,
    _humanize_key,
    _looks_like_secret,
    _parse_annotation,
    _parse_defaults_file,
    find_unannotated_candidates,
    scan_role_defaults,
    scanned_to_ansible_vars,
    scanned_to_shell_secrets,
)


# ---------------------------------------------------------------------------
# _humanize_key
# ---------------------------------------------------------------------------


class TestHumanizeKey:
    def test_basic(self):
        assert _humanize_key("restic_b2_bucket") == "Restic b2 bucket"

    def test_single_word(self):
        assert _humanize_key("password") == "Password"

    def test_long_name(self):
        assert _humanize_key("git_user_email") == "Git user email"


# ---------------------------------------------------------------------------
# _parse_annotation
# ---------------------------------------------------------------------------


class TestParseAnnotation:
    def test_basic_secret(self):
        result = _parse_annotation("secret")
        assert result["directive"] == "secret"
        assert result["password"] is False
        assert result["optional"] is False

    def test_secret_with_password(self):
        result = _parse_annotation("secret password")
        assert result["directive"] == "secret"
        assert result["password"] is True

    def test_secret_with_optional(self):
        result = _parse_annotation("secret optional")
        assert result["directive"] == "secret"
        assert result["optional"] is True

    def test_secret_with_label(self):
        result = _parse_annotation('secret label="B2 bucket name"')
        assert result["label"] == "B2 bucket name"

    def test_secret_with_all_kv(self):
        result = _parse_annotation(
            'secret password label="My key" placeholder="sk-..." '
            'doc_url="https://example.com" description="API key"'
        )
        assert result["directive"] == "secret"
        assert result["password"] is True
        assert result["label"] == "My key"
        assert result["placeholder"] == "sk-..."
        assert result["doc_url"] == "https://example.com"
        assert result["description"] == "API key"

    def test_shell_secret(self):
        result = _parse_annotation("shell-secret password")
        assert result["directive"] == "shell-secret"
        assert result["password"] is True

    def test_skip(self):
        result = _parse_annotation("skip")
        assert result["directive"] == "skip"

    def test_unknown_directive(self):
        result = _parse_annotation("unknown")
        assert result is None

    def test_empty(self):
        result = _parse_annotation("")
        assert result is None


# ---------------------------------------------------------------------------
# _parse_defaults_file
# ---------------------------------------------------------------------------


class TestParseDefaultsFile:
    def test_basic_secret(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            'my_api_key: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 1
        assert results[0].key == "my_api_key"
        assert results[0].role == "test-role"
        assert results[0].directive == "secret"
        assert results[0].label == "My api key"

    def test_skip_directive(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui skip\n"
            'auto_provisioned: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 0

    def test_label_override(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            '# @tui secret label="Custom Label"\n'
            'my_var: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].label == "Custom Label"

    def test_inline_comment_becomes_description(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            'my_var: ""  # This is a description\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].description == "This is a description"

    def test_placeholder_from_eg_pattern(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            'bucket_name: ""  # e.g. "my-backups"\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].placeholder == "my-backups"

    def test_password_flag(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret password\n"
            'repo_password: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].password is True

    def test_optional_flag(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret optional\n"
            'webhook_url: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].optional is True

    def test_doc_url(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            '# @tui secret doc_url="https://example.com/docs"\n'
            'api_key: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert results[0].doc_url == "https://example.com/docs"

    def test_non_empty_default_ignored(self, tmp_path):
        """Variables with non-empty defaults are not matched."""
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            'version: "1.0.0"\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 0

    def test_unannotated_empty_string_ignored(self, tmp_path):
        """Empty-string vars without @tui annotation are not matched."""
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            '# Just a regular comment\n'
            'some_var: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 0

    def test_multiple_vars(self, tmp_path):
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            'var_a: ""\n'
            'not_annotated: ""\n'
            "# @tui secret password\n"
            'var_b: ""\n'
            "# @tui skip\n"
            'var_c: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 2
        assert results[0].key == "var_a"
        assert results[1].key == "var_b"
        assert results[1].password is True

    def test_annotation_without_following_var_is_consumed(self, tmp_path):
        """An annotation followed by a non-matching line is consumed."""
        f = tmp_path / "main.yml"
        f.write_text(
            "---\n"
            "# @tui secret\n"
            "# another comment\n"
            "# @tui secret\n"
            'actual_var: ""\n'
        )
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 1
        assert results[0].key == "actual_var"

    def test_missing_file(self, tmp_path):
        f = tmp_path / "nonexistent.yml"
        results = _parse_defaults_file(f, "test-role")
        assert len(results) == 0


# ---------------------------------------------------------------------------
# scan_role_defaults (integration with real repo)
# ---------------------------------------------------------------------------


class TestScanRoleDefaults:
    def test_finds_vars_in_repo(self):
        """Scanning the actual repo should find annotated vars."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        results = scan_role_defaults(repo_root)
        keys = {v.key for v in results}

        # Known annotated vars should be present.
        assert "restic_b2_bucket" in keys
        assert "git_user_email" in keys
        assert "docker_mcp_brave_api_key" in keys

        # Skipped vars should NOT be present.
        assert "restic_b2_account_id" not in keys
        assert "restic_b2_account_key" not in keys

    def test_sorted_by_directive_role_key(self):
        """Results should be sorted by (directive, role, key)."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        results = scan_role_defaults(repo_root)
        sort_keys = [(v.directive, v.role, v.key) for v in results]
        assert sort_keys == sorted(sort_keys)


class TestScanFilters:
    def test_scanned_to_ansible_vars(self):
        repo_root = Path(__file__).resolve().parent.parent.parent
        scanned = scan_role_defaults(repo_root)
        ansible = scanned_to_ansible_vars(scanned)
        assert all(v.directive == "secret" for v in ansible)
        assert len(ansible) > 0

    def test_scanned_to_shell_secrets_empty_in_repo(self):
        """No roles declare @tui shell-secret in defaults today."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        scanned = scan_role_defaults(repo_root)
        shell = scanned_to_shell_secrets(scanned)
        assert len(shell) == 0


# ---------------------------------------------------------------------------
# secrets.py integration — SHARED_ANSIBLE_VARS populated by scanner
# ---------------------------------------------------------------------------


class TestSecretsIntegration:
    def test_shared_ansible_vars_populated(self):
        from setup_tui.lib.secrets import SHARED_ANSIBLE_VARS

        assert len(SHARED_ANSIBLE_VARS) >= 10  # at least 10 vars expected
        keys = {f.key for f in SHARED_ANSIBLE_VARS}
        assert "restic_b2_bucket" in keys
        assert "git_user_email" in keys

    def test_shared_ansible_vars_are_secret_fields(self):
        from setup_tui.lib.secrets import SHARED_ANSIBLE_VARS, SecretField

        for f in SHARED_ANSIBLE_VARS:
            assert isinstance(f, SecretField)
            assert f.key
            assert f.label
            assert f.used_by


# ---------------------------------------------------------------------------
# _looks_like_secret heuristic
# ---------------------------------------------------------------------------


class TestLooksLikeSecret:
    def test_api_key(self):
        assert _looks_like_secret("stripe_api_key") is not None

    def test_token(self):
        assert _looks_like_secret("github_token") is not None

    def test_password(self):
        assert _looks_like_secret("db_password") is not None

    def test_credential(self):
        assert _looks_like_secret("aws_credential") is not None

    def test_bare_key(self):
        assert _looks_like_secret("b2_master_key") is not None

    def test_allcaps_api_key(self):
        assert _looks_like_secret("OPENAI_API_KEY") is not None

    def test_allcaps_token(self):
        assert _looks_like_secret("GITHUB_TOKEN") is not None

    def test_allcaps_secret(self):
        assert _looks_like_secret("MY_APP_SECRET") is not None

    def test_public_key_excluded(self):
        assert _looks_like_secret("ssh_public_key") is None

    def test_signing_key_excluded(self):
        assert _looks_like_secret("git_signing_key") is None

    def test_key_id_excluded(self):
        assert _looks_like_secret("b2_master_key_id") is None

    def test_normal_var(self):
        assert _looks_like_secret("app_version") is None

    def test_empty_string_default(self):
        assert _looks_like_secret("some_host") is None

    def test_bucket(self):
        assert _looks_like_secret("restic_b2_bucket") is None


# ---------------------------------------------------------------------------
# find_unannotated_candidates
# ---------------------------------------------------------------------------


class TestFindUnannotatedCandidates:
    def test_catches_unannotated_api_key(self, tmp_path):
        role_dir = tmp_path / "shared/roles/my-app/defaults"
        role_dir.mkdir(parents=True)
        (role_dir / "main.yml").write_text(
            "---\n"
            'my_app_api_key: ""\n'
            'normal_var: ""\n'
        )
        candidates = find_unannotated_candidates(tmp_path, known_keys=set())
        assert len(candidates) == 1
        assert candidates[0].key == "my_app_api_key"
        assert candidates[0].source == "role:my-app/defaults"

    def test_catches_unannotated_password(self, tmp_path):
        role_dir = tmp_path / "shared/roles/db/defaults"
        role_dir.mkdir(parents=True)
        (role_dir / "main.yml").write_text(
            "---\n"
            'db_password: ""\n'
        )
        candidates = find_unannotated_candidates(tmp_path, known_keys=set())
        assert len(candidates) == 1
        assert candidates[0].key == "db_password"

    def test_skips_annotated_vars(self, tmp_path):
        role_dir = tmp_path / "shared/roles/my-app/defaults"
        role_dir.mkdir(parents=True)
        (role_dir / "main.yml").write_text(
            "---\n"
            "# @tui secret\n"
            'my_app_api_key: ""\n'
        )
        candidates = find_unannotated_candidates(
            tmp_path, known_keys={"my_app_api_key"}
        )
        assert len(candidates) == 0

    def test_skips_known_keys(self, tmp_path):
        role_dir = tmp_path / "shared/roles/my-app/defaults"
        role_dir.mkdir(parents=True)
        (role_dir / "main.yml").write_text(
            "---\n"
            'my_app_token: ""\n'
        )
        candidates = find_unannotated_candidates(
            tmp_path, known_keys={"my_app_token"}
        )
        assert len(candidates) == 0

    def test_catches_shell_export_placeholder(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "templatize.sh").write_text(
            '#!/bin/bash\n'
            'export MY_SERVICE_API_KEY="PLACEHOLDER"\n'
            'export NORMAL_PATH="/usr/bin"\n'
        )
        candidates = find_unannotated_candidates(tmp_path, known_keys=set())
        assert len(candidates) == 1
        assert candidates[0].key == "MY_SERVICE_API_KEY"
        assert "shell-export" in candidates[0].source

    def test_ignores_shell_export_with_real_value(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "templatize.sh").write_text(
            '#!/bin/bash\n'
            'export MY_API_KEY="sk-ant-real-value-here"\n'
        )
        candidates = find_unannotated_candidates(tmp_path, known_keys=set())
        assert len(candidates) == 0

    def test_real_repo_no_unannotated_ansible_secrets(self):
        """In the real repo, all secret-like vars in defaults should be annotated."""
        from setup_tui.lib.secrets import SHELL_SECRETS

        repo_root = Path(__file__).resolve().parent.parent.parent
        scanned = scan_role_defaults(repo_root)
        known = {v.key for v in scanned} | {s.key for s in SHELL_SECRETS}
        candidates = find_unannotated_candidates(repo_root, known_keys=known)

        # Filter to only role defaults (not shell exports like OPENAI_API_KEY).
        role_candidates = [c for c in candidates if c.source.startswith("role:")]
        assert role_candidates == [], (
            f"Unannotated secret-like vars in role defaults: "
            f"{[(c.key, c.source) for c in role_candidates]}"
        )
