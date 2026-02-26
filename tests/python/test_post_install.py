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
    MACOS_ITEMS,
    ChecklistItem,
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

    def test_macos_items_are_macos_only(self):
        for item in MACOS_ITEMS:
            assert item.platforms == ["macos"]

    def test_no_empty_text(self):
        for item in BOTH_PLATFORMS + LINUX_ITEMS + MACOS_ITEMS:
            assert item.text.strip(), f"Empty text in checklist item: {item}"


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


class TestRenderHtml:
    """HTML rendering produces valid, platform-specific output."""

    def test_renders_without_error(self):
        html = render_html(
            plat="linux",
            phases=["system", "apps"],
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
        # Should have Linux section header, not macOS
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
            phases=["system", "apps"],
            skip_tags=[],
            log_path="/tmp/bootstrap.log",
        )
        assert "system" in html
        assert "apps" in html

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
