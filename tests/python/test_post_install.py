"""Tests for post-install checklist generation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add scripts/ to path so setup_tui package is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.lib.post_install import (
    BOTH_PLATFORMS,
    LINUX_ITEMS,
    ChecklistItem,
    _MACOS_ITEMS_STATIC,
    _filter_items,
    _setapp_apps,
    generate_and_open,
    items_for_platform,
    open_file,
    render_html,
)


class TestChecklistData:
    """Checklist item definitions are well-formed."""

    def test_both_platforms_items_have_both_platforms(self):
        for item in BOTH_PLATFORMS:
            assert "linux" in item.platforms
            assert "macos" in item.platforms

    def test_linux_items_are_linux_only(self):
        for item in LINUX_ITEMS:
            assert item.platforms == ["linux"]

    def test_macos_static_items_are_macos_only(self):
        for item in _MACOS_ITEMS_STATIC:
            assert item.platforms == ["macos"]

    def test_no_empty_text(self):
        for item in BOTH_PLATFORMS + LINUX_ITEMS + _MACOS_ITEMS_STATIC:
            assert item.text.strip(), f"Empty text in checklist item: {item}"

    def test_items_have_phase_or_are_generic(self):
        """Every item either has a phase annotation or is intentionally generic."""
        for item in BOTH_PLATFORMS + LINUX_ITEMS + _MACOS_ITEMS_STATIC:
            # Items without a phase are shown regardless of selection.
            # Just verify the field exists (even if empty).
            assert isinstance(item.phase, str)


class TestFilterItems:
    """_filter_items respects phases and skip_tags."""

    def test_no_filters_returns_all(self):
        items = [ChecklistItem("a", phase="desktop", tags=["foo"])]
        assert _filter_items(items, [], []) == items

    def test_phase_filter_excludes_unmatched(self):
        items = [
            ChecklistItem("a", phase="desktop", tags=["foo"]),
            ChecklistItem("b", phase="security", tags=["bar"]),
        ]
        result = _filter_items(items, ["desktop"], [])
        assert len(result) == 1
        assert result[0].text == "a"

    def test_skip_tags_excludes_matched(self):
        items = [
            ChecklistItem("a", phase="desktop", tags=["foo"]),
            ChecklistItem("b", phase="desktop", tags=["bar"]),
        ]
        result = _filter_items(items, [], ["bar"])
        assert len(result) == 1
        assert result[0].text == "a"

    def test_items_without_phase_always_shown(self):
        items = [
            ChecklistItem("generic"),
            ChecklistItem("phased", phase="gaming", tags=["steam"]),
        ]
        result = _filter_items(items, ["desktop"], [])
        assert len(result) == 1
        assert result[0].text == "generic"

    def test_combined_phase_and_skip(self):
        items = [
            ChecklistItem("a", phase="desktop", tags=["foo"]),
            ChecklistItem("b", phase="desktop", tags=["bar"]),
            ChecklistItem("c", phase="security", tags=["baz"]),
        ]
        result = _filter_items(items, ["desktop"], ["bar"])
        assert len(result) == 1
        assert result[0].text == "a"


class TestSetappApps:
    """_setapp_apps reads from verify-registry.yml and filters."""

    def test_returns_known_setapp_apps(self):
        apps = _setapp_apps([], [])
        # At minimum, these should be in the registry.
        assert "Dato" in apps
        assert "CleanShot X" in apps

    def test_phase_filter_excludes_apps(self):
        # Setapp apps are all in the "desktop" phase.
        # Selecting only "security" should return none.
        apps = _setapp_apps(["security"], [])
        assert len(apps) == 0

    def test_skip_tag_excludes_app(self):
        all_apps = _setapp_apps([], [])
        filtered = _setapp_apps([], ["dato"])
        assert "Dato" in all_apps
        assert "Dato" not in filtered


class TestItemsForPlatform:
    """Platform filtering returns the correct sections."""

    def test_linux_includes_both_and_linux(self):
        sections = items_for_platform("linux")
        assert "Both Platforms" in sections
        assert "Linux" in sections
        assert "macOS" not in sections

    def test_macos_includes_both_and_macos(self):
        sections = items_for_platform("macos")
        assert "Both Platforms" in sections
        assert "macOS" in sections
        assert "Linux" not in sections

    def test_both_platforms_always_first(self):
        for plat in ("linux", "macos"):
            sections = items_for_platform(plat)
            assert list(sections.keys())[0] == "Both Platforms"

    def test_macos_setapp_item_built_dynamically(self):
        sections = items_for_platform("macos")
        macos_items = sections["macOS"]
        setapp_items = [i for i in macos_items if "Setapp" in i.text]
        assert len(setapp_items) == 1
        assert "Dato" in setapp_items[0].text

    def test_phase_filter_reduces_items(self):
        all_sections = items_for_platform("macos")
        filtered = items_for_platform("macos", phases=["security"])
        all_count = sum(len(v) for v in all_sections.values())
        filtered_count = sum(len(v) for v in filtered.values())
        assert filtered_count < all_count

    def test_skip_tags_reduces_items(self):
        all_sections = items_for_platform("macos")
        filtered = items_for_platform("macos", skip_tags=["raycast"])
        all_texts = [i.text for v in all_sections.values() for i in v]
        filtered_texts = [i.text for v in filtered.values() for i in v]
        assert any("Raycast" in t for t in all_texts)
        assert not any("Raycast" in t for t in filtered_texts)


class TestRenderHtml:
    """HTML rendering produces valid, platform-specific output."""

    def test_renders_without_error(self):
        html = render_html(
            plat="linux",
            phases=["system", "desktop"],
            skip_tags=["docker"],
            log_path="/tmp/bootstrap.log",
        )
        assert "<!DOCTYPE html>" in html
        assert "Post-Install Checklist" in html

    def test_contains_platform_label(self):
        html = render_html(
            plat="macos",
            phases=[],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert "macOS" in html

    def test_linux_excludes_macos_section(self):
        html = render_html(
            plat="linux",
            phases=[],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert "Setapp" not in html
        assert "Cinnamon" in html

    def test_macos_excludes_linux_section(self):
        html = render_html(
            plat="macos",
            phases=[],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert "Cinnamon" not in html
        assert "Setapp" in html

    def test_phases_shown_as_tags(self):
        html = render_html(
            plat="linux",
            phases=["system", "desktop"],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert "system" in html
        assert "desktop" in html

    def test_skip_tags_shown(self):
        html = render_html(
            plat="linux",
            phases=[],
            skip_tags=["docker", "vpn"],
            log_path="/tmp/bootstrap.log",
        )
        assert "docker" in html
        assert "vpn" in html

    def test_log_path_shown(self):
        html = render_html(
            plat="linux",
            phases=[],
            skip_tags=[],
            log_path="/home/user/bootstrap.log",
        )
        assert "/home/user/bootstrap.log" in html

    def test_checkboxes_present(self):
        html = render_html(
            plat="linux",
            phases=[],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert 'type="checkbox"' in html

    def test_custom_templates_dir(self, tmp_path):
        """Render with a custom template directory."""
        from setup_tui.lib.post_install import TEMPLATES_DIR

        # Copy the real template to tmp_path to verify the override works.
        tpl = (TEMPLATES_DIR / "post_install.html.j2").read_text()
        (tmp_path / "post_install.html.j2").write_text(tpl)

        html = render_html(
            plat="linux",
            phases=[],
            skip_tags=[],
            log_path="/tmp/test.log",
            templates_dir=tmp_path,
        )
        assert "Post-Install Checklist" in html

    def test_skipped_phase_excludes_items(self):
        """Items from a skipped phase don't appear in output."""
        html = render_html(
            plat="macos",
            phases=["security"],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        # Desktop-phase items should be gone.
        assert "Setapp" not in html
        assert "Raycast" not in html
        # Security-phase items should remain.
        assert "1Password" in html


class TestGenerateAndOpen:
    """Integration: write HTML to disk."""

    def test_writes_to_desktop(self, tmp_path):
        with patch(
            "setup_tui.lib.post_install._desktop_path", return_value=tmp_path
        ):
            doc = generate_and_open(
                plat="linux",
                phases=["system"],
                skip_tags=[],
                log_path="/tmp/bootstrap.log",
            )
        assert doc.exists()
        assert doc.name == "post-install-checklist.html"
        assert "<!DOCTYPE html>" in doc.read_text()

    def test_overwrites_existing(self, tmp_path):
        existing = tmp_path / "post-install-checklist.html"
        existing.write_text("old content")

        with patch(
            "setup_tui.lib.post_install._desktop_path", return_value=tmp_path
        ):
            doc = generate_and_open(
                plat="linux",
                phases=[],
                skip_tags=[],
                log_path="/tmp/bootstrap.log",
            )
        assert "old content" not in doc.read_text()
        assert "<!DOCTYPE html>" in doc.read_text()


class TestOpenFile:
    """open_file dispatches to the platform opener."""

    def test_linux_uses_xdg_open(self, tmp_path):
        dummy = tmp_path / "test.html"
        dummy.write_text("<html></html>")

        with patch("setup_tui.lib.post_install.platform") as mock_plat, \
             patch("setup_tui.lib.post_install.subprocess.Popen") as mock_popen:
            mock_plat.system.return_value = "Linux"
            open_file(dummy)
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "xdg-open"

    def test_macos_uses_open(self, tmp_path):
        dummy = tmp_path / "test.html"
        dummy.write_text("<html></html>")

        with patch("setup_tui.lib.post_install.platform") as mock_plat, \
             patch("setup_tui.lib.post_install.subprocess.Popen") as mock_popen:
            mock_plat.system.return_value = "Darwin"
            open_file(dummy)
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            assert args[0] == "open"

    def test_missing_opener_does_not_raise(self, tmp_path):
        dummy = tmp_path / "test.html"
        dummy.write_text("<html></html>")

        with patch("setup_tui.lib.post_install.platform") as mock_plat, \
             patch(
                 "setup_tui.lib.post_install.subprocess.Popen",
                 side_effect=FileNotFoundError,
             ):
            mock_plat.system.return_value = "Linux"
            # Should log a warning, not raise.
            open_file(dummy)
