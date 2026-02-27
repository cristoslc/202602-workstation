"""Tests for the verification engine and registry."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add scripts/ to path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.lib.verify import (
    PHASE_ORDER,
    AppEntry,
    CheckResult,
    StowLayerResult,
    check_stow_links,
    filter_entries,
    load_registry,
    run_all_checks,
    run_check,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# ── Registry parsing ─────────────────────────────────────────────────


class TestLoadRegistry:
    """Tests for loading and validating the YAML registry."""

    def test_registry_parses(self):
        """Registry YAML loads without error."""
        entries = load_registry()
        assert len(entries) > 0

    def test_entries_have_required_fields(self):
        """Every entry has name, platforms, and check."""
        entries = load_registry()
        for entry in entries:
            assert entry.name, f"Entry missing name in role {entry.role}"
            assert entry.platforms, f"{entry.name} missing platforms"
            assert entry.check, f"{entry.name} missing check"

    def test_entries_have_valid_check_type(self):
        """Every entry uses a known check type."""
        valid_keys = {"command", "app_paths", "path"}
        entries = load_registry()
        for entry in entries:
            keys = set(entry.check.keys())
            assert keys & valid_keys, (
                f"{entry.name} in {entry.role} has unknown check type: {keys}"
            )

    def test_entries_have_valid_platforms(self):
        """Every platform is macos or linux."""
        entries = load_registry()
        for entry in entries:
            for p in entry.platforms:
                assert p in ("macos", "linux"), (
                    f"{entry.name}: invalid platform '{p}'"
                )

    def test_entries_have_valid_phase(self):
        """Every entry's phase is in the known phase list."""
        entries = load_registry()
        for entry in entries:
            assert entry.phase in PHASE_ORDER, (
                f"{entry.name} in {entry.role}: unknown phase '{entry.phase}'"
            )

    def test_no_duplicate_entries(self):
        """No duplicate name+platform within the same role."""
        entries = load_registry()
        seen: set[tuple[str, str, str]] = set()
        for entry in entries:
            for plat in entry.platforms:
                key = (entry.role, entry.name, plat)
                assert key not in seen, (
                    f"Duplicate entry: {entry.name} ({plat}) in role {entry.role}"
                )
                seen.add(key)

    def test_custom_registry(self, tmp_path):
        """Can load a custom registry file."""
        reg = tmp_path / "test-reg.yml"
        reg.write_text(
            "roles:\n"
            "  test-role:\n"
            "    phase: system\n"
            "    apps:\n"
            "      - name: test-tool\n"
            "        platforms: [macos]\n"
            "        check: {command: test-tool}\n"
            "        tags: [test]\n"
        )
        entries = load_registry(reg)
        assert len(entries) == 1
        assert entries[0].name == "test-tool"
        assert entries[0].role == "test-role"
        assert entries[0].phase == "system"

    def test_optional_and_note_fields(self, tmp_path):
        """Optional and note fields are parsed correctly."""
        reg = tmp_path / "test-reg.yml"
        reg.write_text(
            "roles:\n"
            "  test-role:\n"
            "    phase: desktop\n"
            "    apps:\n"
            "      - name: MyApp\n"
            "        platforms: [macos]\n"
            "        check: {app_paths: ['/Applications/MyApp.app']}\n"
            "        tags: [myapp]\n"
            "        optional: true\n"
            "        note: Install via Setapp\n"
        )
        entries = load_registry(reg)
        assert entries[0].optional is True
        assert entries[0].note == "Install via Setapp"

    def test_version_flag_override(self, tmp_path):
        """version_flag field overrides default."""
        reg = tmp_path / "test-reg.yml"
        reg.write_text(
            "roles:\n"
            "  docker:\n"
            "    phase: dev-tools\n"
            "    apps:\n"
            "      - name: docker\n"
            "        platforms: [macos]\n"
            "        check: {command: docker}\n"
            "        version_flag: version\n"
            "        tags: [docker]\n"
        )
        entries = load_registry(reg)
        assert entries[0].version_flag == "version"


# ── Registry completeness ────────────────────────────────────────────


class TestRegistryCompleteness:
    """Every role directory should have at least one registry entry."""

    def _get_role_dirs(self) -> set[str]:
        """Collect all role directory names from the repo."""
        dirs: set[str] = set()
        for role_root in [
            REPO_ROOT / "shared" / "roles",
            REPO_ROOT / "linux" / "roles",
            REPO_ROOT / "macos" / "roles",
        ]:
            if role_root.exists():
                for d in role_root.iterdir():
                    if d.is_dir() and not d.name.startswith("."):
                        dirs.add(d.name)
        return dirs

    def test_all_roles_registered(self):
        """Every role directory appears in the registry."""
        entries = load_registry()
        registered_roles = {e.role for e in entries}
        # Also count roles with empty apps lists.
        from setup_tui.lib.verify import REGISTRY_PATH

        import yaml
        with open(REGISTRY_PATH) as f:
            data = yaml.safe_load(f)
        all_registered = set(data.get("roles", {}).keys())

        role_dirs = self._get_role_dirs()
        missing = role_dirs - all_registered
        assert not missing, (
            f"Role directories missing from verify-registry.yml: {sorted(missing)}"
        )


# ── Filtering ────────────────────────────────────────────────────────


class TestFilterEntries:
    """Tests for filter_entries()."""

    @pytest.fixture
    def entries(self):
        return [
            AppEntry(
                name="git", role="git", phase="dev-tools",
                platforms=["macos", "linux"],
                check={"command": "git"}, tags=["git"],
            ),
            AppEntry(
                name="Raycast", role="launchers", phase="desktop",
                platforms=["macos"],
                check={"app_paths": ["/Applications/Raycast.app"]},
                tags=["raycast"],
            ),
            AppEntry(
                name="Firefox", role="browsers", phase="desktop",
                platforms=["macos", "linux"],
                check={"app_paths": ["/Applications/Firefox.app"]},
                tags=["firefox"],
            ),
        ]

    def test_filter_by_platform(self, entries):
        result = filter_entries(entries, platform="linux")
        names = {e.name for e in result}
        assert "git" in names
        assert "Firefox" in names
        assert "Raycast" not in names

    def test_filter_by_role(self, entries):
        result = filter_entries(entries, roles=["git"])
        assert len(result) == 1
        assert result[0].name == "git"

    def test_filter_by_phase(self, entries):
        result = filter_entries(entries, phases=["desktop"])
        names = {e.name for e in result}
        assert "Raycast" in names
        assert "Firefox" in names
        assert "git" not in names

    def test_filter_by_tag(self, entries):
        result = filter_entries(entries, tags=["firefox"])
        assert len(result) == 1
        assert result[0].name == "Firefox"

    def test_filter_combined(self, entries):
        result = filter_entries(entries, platform="linux", phases=["desktop"])
        names = {e.name for e in result}
        assert "Firefox" in names
        assert "Raycast" not in names
        assert "git" not in names

    def test_no_filters_returns_all(self, entries):
        result = filter_entries(entries)
        assert len(result) == len(entries)


# ── Check engine ─────────────────────────────────────────────────────


class TestRunCheck:
    """Tests for run_check() with various check types."""

    def test_command_found(self):
        """A command that exists passes."""
        entry = AppEntry(
            name="python3", role="python", phase="dev-tools",
            platforms=["macos", "linux"],
            check={"command": "python3"}, tags=["python"],
        )
        result = run_check(entry)
        assert result.passed is True
        assert result.detail  # version string or path

    @patch("setup_tui.lib.verify.shutil.which", return_value=None)
    def test_command_not_found(self, _mock_which):
        """A command that doesn't exist fails."""
        entry = AppEntry(
            name="nonexistent", role="test", phase="dev-tools",
            platforms=["macos"],
            check={"command": "nonexistent_tool_xyz"}, tags=[],
        )
        result = run_check(entry)
        assert result.passed is False
        assert "not installed" in result.detail

    @patch("setup_tui.lib.verify.subprocess.run")
    @patch("setup_tui.lib.verify.shutil.which", return_value="/usr/bin/slow")
    def test_command_timeout(self, _mock_which, mock_run):
        """Timeout on version probe still passes (tool exists)."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="slow", timeout=5)
        entry = AppEntry(
            name="slow-tool", role="test", phase="dev-tools",
            platforms=["macos"],
            check={"command": "slow"}, tags=[],
        )
        result = run_check(entry)
        assert result.passed is True

    def test_path_exists(self, tmp_path):
        """A path check passes when the file exists."""
        test_file = tmp_path / "config.yml"
        test_file.write_text("test")
        entry = AppEntry(
            name="config", role="test", phase="dotfiles",
            platforms=["macos"],
            check={"path": str(test_file)}, tags=[],
        )
        result = run_check(entry)
        assert result.passed is True

    def test_path_not_exists(self):
        """A path check fails when the file is missing."""
        entry = AppEntry(
            name="config", role="test", phase="dotfiles",
            platforms=["macos"],
            check={"path": "/nonexistent/path/xyz"}, tags=[],
        )
        result = run_check(entry)
        assert result.passed is False

    def test_app_paths_found(self, tmp_path):
        """An app_paths check passes when one path exists."""
        app_dir = tmp_path / "Test.app"
        app_dir.mkdir()
        entry = AppEntry(
            name="Test App", role="test", phase="desktop",
            platforms=["macos"],
            check={"app_paths": ["/nonexistent/A.app", str(app_dir)]},
            tags=[],
        )
        result = run_check(entry)
        assert result.passed is True

    def test_app_paths_not_found(self):
        """An app_paths check fails when no paths exist."""
        entry = AppEntry(
            name="Missing App", role="test", phase="desktop",
            platforms=["macos"],
            check={"app_paths": ["/nonexistent/A.app", "/nonexistent/B.app"]},
            tags=[],
        )
        result = run_check(entry)
        assert result.passed is False

    def test_unknown_check_type(self):
        """Unknown check type reports failure."""
        entry = AppEntry(
            name="mystery", role="test", phase="system",
            platforms=["macos"],
            check={"unknown_type": "value"}, tags=[],
        )
        result = run_check(entry)
        assert result.passed is False
        assert "unknown" in result.detail


class TestRunAllChecks:
    """Tests for run_all_checks()."""

    @patch("setup_tui.lib.verify.shutil.which", return_value=None)
    def test_parallel_execution(self, _mock_which):
        """Parallel mode returns results for all entries."""
        entries = [
            AppEntry(
                name=f"tool-{i}", role="test", phase="dev-tools",
                platforms=["macos"],
                check={"command": f"tool-{i}"}, tags=[],
            )
            for i in range(5)
        ]
        results = run_all_checks(entries, parallel=True)
        assert len(results) == 5

    @patch("setup_tui.lib.verify.shutil.which", return_value=None)
    def test_sequential_execution(self, _mock_which):
        """Sequential mode returns results for all entries."""
        entries = [
            AppEntry(
                name=f"tool-{i}", role="test", phase="dev-tools",
                platforms=["macos"],
                check={"command": f"tool-{i}"}, tags=[],
            )
            for i in range(3)
        ]
        results = run_all_checks(entries, parallel=False)
        assert len(results) == 3

    @patch("setup_tui.lib.verify.shutil.which", return_value=None)
    def test_on_result_callback(self, _mock_which):
        """on_result callback is called for each check."""
        entries = [
            AppEntry(
                name="tool", role="test", phase="dev-tools",
                platforms=["macos"],
                check={"command": "tool"}, tags=[],
            ),
        ]
        callback = MagicMock()
        run_all_checks(entries, parallel=False, on_result=callback)
        assert callback.call_count == 1


# ── Stow link checks ────────────────────────────────────────────────


class TestStowLinks:
    """Tests for check_stow_links()."""

    def test_nonexistent_dir(self, tmp_path):
        """Nonexistent stow dir returns zero counts."""
        result = check_stow_links(tmp_path / "missing", tmp_path / "target")
        assert result.total == 0
        assert result.healthy == 0

    def test_healthy_links(self, tmp_path):
        """Correctly stowed symlinks are counted as healthy."""
        stow_dir = tmp_path / "stow"
        pkg = stow_dir / "mypkg" / ".config" / "tool"
        pkg.mkdir(parents=True)
        (pkg / "config.yml").write_text("test")

        target = tmp_path / "home"
        target_config = target / ".config" / "tool"
        target_config.mkdir(parents=True)
        (target_config / "config.yml").symlink_to(pkg / "config.yml")

        result = check_stow_links(stow_dir, target)
        assert result.total == 1
        assert result.healthy == 1
        assert len(result.broken) == 0

    def test_broken_links(self, tmp_path):
        """Missing symlink targets are counted as broken."""
        stow_dir = tmp_path / "stow"
        pkg = stow_dir / "mypkg" / ".config" / "tool"
        pkg.mkdir(parents=True)
        (pkg / "config.yml").write_text("test")

        target = tmp_path / "home"
        # No symlink created — should count as broken.
        result = check_stow_links(stow_dir, target)
        assert result.total == 1
        assert result.healthy == 0
        assert len(result.broken) == 1
