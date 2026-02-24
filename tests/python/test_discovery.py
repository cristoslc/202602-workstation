"""Tests for setup_tui.lib.discovery — playbook auto-discovery."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# Add scripts/ to path so setup_tui package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.lib.discovery import (
    DiscoveredPhase,
    DiscoveredRole,
    PlaybookManifest,
    _make_description,
    _parse_display_name,
    _parse_order,
    _parse_phase_id,
    _parse_play_file,
    discover_playbook,
    validate_config,
)
from setup_tui.lib.runner import REPO_ROOT


# ===========================================================================
# Unit tests — parsing helpers
# ===========================================================================


class TestParsePhaseId:
    def test_standard_filename(self):
        assert _parse_phase_id("02-dev-tools.yml") == "dev-tools"

    def test_single_word(self):
        assert _parse_phase_id("05-gaming.yml") == "gaming"

    def test_zero_prefix(self):
        assert _parse_phase_id("00-system.yml") == "system"

    def test_no_prefix(self):
        assert _parse_phase_id("dotfiles.yml") == "dotfiles"


class TestParseOrder:
    def test_standard(self):
        assert _parse_order("02-dev-tools.yml") == 2

    def test_zero(self):
        assert _parse_order("00-system.yml") == 0

    def test_no_prefix(self):
        assert _parse_order("dotfiles.yml") == 0


class TestParseDisplayName:
    def test_strips_prefix(self):
        assert _parse_display_name("Phase 2: Development tools") == "Development tools"

    def test_no_prefix(self):
        assert _parse_display_name("My Play") == "My Play"

    def test_strips_whitespace(self):
        assert _parse_display_name("Phase 0:  System foundation ") == "System foundation"


class TestMakeDescription:
    def test_subtool_tags(self):
        desc = _make_description(
            ["browsers", "firefox", "brave", "chrome", "desktop"],
            "browsers",
            "desktop",
        )
        assert desc == "Firefox, Brave, Chrome"

    def test_no_subtools(self):
        desc = _make_description(["gaming"], "gaming", "gaming")
        assert desc == ""

    def test_hyphenated_tags(self):
        desc = _make_description(
            ["stream-deck", "opendeck", "desktop"],
            "stream-deck",
            "desktop",
        )
        assert desc == "Opendeck"

    def test_excludes_role_name_and_phase_id(self):
        desc = _make_description(
            ["docker", "dev-tools"],
            "docker",
            "dev-tools",
        )
        assert desc == ""


# ===========================================================================
# Unit tests — YAML parsing with synthetic files
# ===========================================================================


class TestParsePlayFile:
    def test_basic_play(self, tmp_path):
        play_file = tmp_path / "02-dev-tools.yml"
        play_file.write_text(textwrap.dedent("""\
            ---
            - name: "Phase 2: Development tools"
              hosts: localhost
              connection: local
              roles:
                - role: docker
                  tags: [docker, dev-tools]
                - role: git
                  tags: [git, gh, lazygit, dev-tools]
        """))
        phase = _parse_play_file(play_file)
        assert phase is not None
        assert phase.phase_id == "dev-tools"
        assert phase.order == 2
        assert phase.display_name == "Development tools"
        assert len(phase.roles) == 2
        assert phase.roles[0].name == "docker"
        assert phase.roles[1].name == "git"
        assert phase.roles[1].description == "Gh, Lazygit"
        assert phase.has_pre_tasks is False

    def test_play_with_pre_tasks(self, tmp_path):
        play_file = tmp_path / "00-system.yml"
        play_file.write_text(textwrap.dedent("""\
            ---
            - name: "Phase 0: System foundation"
              hosts: localhost
              pre_tasks:
                - name: Verify OS
                  ansible.builtin.assert:
                    that: true
              roles:
                - role: base
                  tags: [base, system]
                  when: apply_system_roles | default(true) | bool
        """))
        phase = _parse_play_file(play_file)
        assert phase is not None
        assert phase.has_pre_tasks is True
        assert phase.roles[0].has_when is True

    def test_play_with_no_roles(self, tmp_path):
        play_file = tmp_path / "99-empty.yml"
        play_file.write_text(textwrap.dedent("""\
            ---
            - name: "Phase 99: Empty"
              hosts: localhost
        """))
        phase = _parse_play_file(play_file)
        assert phase is not None
        assert phase.roles == ()

    def test_malformed_yaml(self, tmp_path):
        play_file = tmp_path / "bad.yml"
        play_file.write_text("{{invalid yaml")
        phase = _parse_play_file(play_file)
        assert phase is None

    def test_empty_file(self, tmp_path):
        play_file = tmp_path / "empty.yml"
        play_file.write_text("")
        phase = _parse_play_file(play_file)
        assert phase is None


# ===========================================================================
# Unit tests — PlaybookManifest
# ===========================================================================


class TestPlaybookManifest:
    @pytest.fixture
    def manifest(self):
        return PlaybookManifest(
            platform="linux",
            phases=(
                DiscoveredPhase(
                    phase_id="system",
                    order=0,
                    display_name="System foundation",
                    roles=(
                        DiscoveredRole("base", ("base", "system"), "", True),
                    ),
                    has_pre_tasks=True,
                ),
                DiscoveredPhase(
                    phase_id="dev-tools",
                    order=2,
                    display_name="Development tools",
                    roles=(
                        DiscoveredRole("docker", ("docker", "dev-tools"), ""),
                        DiscoveredRole("git", ("git", "gh", "dev-tools"), "Gh"),
                    ),
                ),
            ),
        )

    def test_phase_ids(self, manifest):
        assert manifest.phase_ids() == ["system", "dev-tools"]

    def test_phase_by_id_found(self, manifest):
        p = manifest.phase_by_id("dev-tools")
        assert p is not None
        assert p.display_name == "Development tools"

    def test_phase_by_id_not_found(self, manifest):
        assert manifest.phase_by_id("nonexistent") is None

    def test_roles_for_phases(self, manifest):
        roles = manifest.roles_for_phases(["dev-tools"])
        assert [r.name for r in roles] == ["docker", "git"]

    def test_roles_for_multiple_phases(self, manifest):
        roles = manifest.roles_for_phases(["system", "dev-tools"])
        assert [r.name for r in roles] == ["base", "docker", "git"]

    def test_roles_for_empty_phases(self, manifest):
        assert manifest.roles_for_phases([]) == []


# ===========================================================================
# Unit tests — discover_playbook with synthetic directory
# ===========================================================================


class TestDiscoverPlaybook:
    def test_discovers_phases_in_order(self, tmp_path, monkeypatch):
        plays_dir = tmp_path / "linux" / "plays"
        plays_dir.mkdir(parents=True)

        (plays_dir / "02-dev-tools.yml").write_text(textwrap.dedent("""\
            ---
            - name: "Phase 2: Dev tools"
              hosts: localhost
              roles:
                - role: docker
                  tags: [docker, dev-tools]
        """))
        (plays_dir / "00-system.yml").write_text(textwrap.dedent("""\
            ---
            - name: "Phase 0: System"
              hosts: localhost
              pre_tasks:
                - name: check
                  ansible.builtin.debug:
                    msg: ok
              roles:
                - role: base
                  tags: [base, system]
        """))

        monkeypatch.setattr(
            "setup_tui.lib.discovery.REPO_ROOT", tmp_path
        )
        manifest = discover_playbook("linux")

        assert manifest.platform == "linux"
        assert len(manifest.phases) == 2
        assert manifest.phases[0].phase_id == "system"
        assert manifest.phases[0].order == 0
        assert manifest.phases[0].has_pre_tasks is True
        assert manifest.phases[1].phase_id == "dev-tools"
        assert manifest.phases[1].order == 2

    def test_missing_dir_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "setup_tui.lib.discovery.REPO_ROOT", tmp_path
        )
        with pytest.raises(FileNotFoundError, match="Plays directory not found"):
            discover_playbook("linux")

    def test_skips_malformed_files(self, tmp_path, monkeypatch):
        plays_dir = tmp_path / "linux" / "plays"
        plays_dir.mkdir(parents=True)
        (plays_dir / "00-good.yml").write_text(textwrap.dedent("""\
            ---
            - name: "Phase 0: Good"
              hosts: localhost
              roles:
                - role: base
                  tags: [base]
        """))
        (plays_dir / "01-bad.yml").write_text("{{not yaml")

        monkeypatch.setattr(
            "setup_tui.lib.discovery.REPO_ROOT", tmp_path
        )
        manifest = discover_playbook("linux")
        assert len(manifest.phases) == 1
        assert manifest.phases[0].phase_id == "good"

    def test_macos_platform_dir(self, tmp_path, monkeypatch):
        plays_dir = tmp_path / "macos" / "plays"
        plays_dir.mkdir(parents=True)
        (plays_dir / "00-system.yml").write_text(textwrap.dedent("""\
            ---
            - name: "Phase 0: System"
              hosts: localhost
              roles:
                - role: homebrew
                  tags: [homebrew, system]
        """))

        monkeypatch.setattr(
            "setup_tui.lib.discovery.REPO_ROOT", tmp_path
        )
        manifest = discover_playbook("macos")
        assert manifest.platform == "macos"
        assert manifest.phases[0].roles[0].name == "homebrew"


# ===========================================================================
# Unit tests — validate_config
# ===========================================================================


class TestValidateConfig:
    @pytest.fixture
    def manifest(self):
        return PlaybookManifest(
            platform="linux",
            phases=(
                DiscoveredPhase("system", 0, "System", ()),
                DiscoveredPhase("security", 1, "Security", ()),
                DiscoveredPhase("dev-tools", 2, "Dev Tools", ()),
            ),
        )

    def test_valid_config_no_warnings(self, manifest):
        warnings = validate_config(
            manifest,
            {"fresh": ["system", "security"]},
            {"dev-tools": ["security"]},
        )
        assert warnings == []

    def test_unknown_default_phase(self, manifest):
        warnings = validate_config(
            manifest,
            {"fresh": ["system", "gaming"]},
            {},
        )
        assert len(warnings) == 1
        assert "gaming" in warnings[0]

    def test_unknown_dep_key(self, manifest):
        warnings = validate_config(
            manifest,
            {},
            {"gaming": ["system"]},
        )
        assert len(warnings) == 1
        assert "gaming" in warnings[0]

    def test_unknown_dep_value(self, manifest):
        warnings = validate_config(
            manifest,
            {},
            {"system": ["gaming"]},
        )
        assert len(warnings) == 1
        assert "gaming" in warnings[0]


# ===========================================================================
# Integration tests — parse real playbook directories
# ===========================================================================


class TestRealPlaybooks:
    """Parse the actual linux/plays/ and macos/plays/ directories."""

    @pytest.mark.parametrize("platform", ["linux", "macos"])
    def test_playbook_discovery(self, platform):
        plays_dir = REPO_ROOT / ("macos" if platform == "macos" else "linux") / "plays"
        if not plays_dir.is_dir():
            pytest.skip(f"{platform}/plays/ not found")

        manifest = discover_playbook(platform)
        assert manifest.platform == platform
        ids = manifest.phase_ids()
        # Core phases present on both platforms.
        for phase in ("system", "security", "dev-tools", "desktop", "dotfiles", "gaming"):
            assert phase in ids
        # Phases should be ordered.
        assert ids == sorted(ids, key=lambda x: ids.index(x))
        # dev-tools should have multiple roles.
        dev = manifest.phase_by_id("dev-tools")
        assert dev is not None
        assert len(dev.roles) >= 5
        # gaming should have 1 role.
        gaming = manifest.phase_by_id("gaming")
        assert gaming is not None
        assert len(gaming.roles) == 1

    @pytest.mark.skipif(
        not (REPO_ROOT / "linux" / "plays").is_dir(),
        reason="linux/plays/ not found",
    )
    def test_role_descriptions_generated(self):
        """Roles with sub-tool tags should have non-empty descriptions."""
        manifest = discover_playbook("linux")
        dev = manifest.phase_by_id("dev-tools")
        assert dev is not None
        git_role = next((r for r in dev.roles if r.name == "git"), None)
        assert git_role is not None
        # git has tags [git, gh, lazygit, delta, dev-tools] → description should exist.
        assert git_role.description != ""
        assert "Gh" in git_role.description or "gh" in git_role.description.lower()

    @pytest.mark.skipif(
        not (REPO_ROOT / "linux" / "plays").is_dir(),
        reason="linux/plays/ not found",
    )
    def test_when_conditions_detected(self):
        """Roles with 'when:' should have has_when=True."""
        manifest = discover_playbook("linux")
        sys_phase = manifest.phase_by_id("system")
        assert sys_phase is not None
        # All system roles have when: apply_system_roles.
        for role in sys_phase.roles:
            assert role.has_when is True

    @pytest.mark.skipif(
        not (REPO_ROOT / "linux" / "plays").is_dir(),
        reason="linux/plays/ not found",
    )
    def test_config_validates_against_real_playbook(self):
        """DEFAULT_PHASES and PHASE_DEPS from bootstrap.py should validate."""
        from setup_tui.screens.bootstrap import DEFAULT_PHASES, PHASE_DEPS

        manifest = discover_playbook("linux")
        warnings = validate_config(manifest, DEFAULT_PHASES, PHASE_DEPS)
        assert warnings == [], f"Config validation warnings: {warnings}"
