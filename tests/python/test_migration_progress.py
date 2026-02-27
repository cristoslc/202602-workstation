"""Tests for migration progress tracking logic."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add scripts/ to path so we can import setup_tui.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

from setup_tui.screens.migration import (  # noqa: E402
    MigrationProgress,
    _FOLDER_DONE_RE,
    _FOLDER_START_RE,
    _PROGRESS2_RE,
    _SCAN_RE,
    _TOTAL_RE,
    _format_bytes,
    _format_duration,
)


# ------------------------------------------------------------------
# _format_bytes
# ------------------------------------------------------------------

class TestFormatBytes:
    def test_zero(self):
        assert _format_bytes(0) == "0 B"

    def test_bytes(self):
        assert _format_bytes(512) == "512 B"

    def test_kilobytes(self):
        result = _format_bytes(1536)  # 1.5 KB
        assert "KB" in result
        assert "1.5" in result

    def test_megabytes(self):
        result = _format_bytes(5 * 1024 * 1024)
        assert "MB" in result
        assert "5.0" in result

    def test_gigabytes(self):
        result = _format_bytes(2.5 * 1024**3)
        assert "GB" in result
        assert "2.5" in result

    def test_terabytes(self):
        result = _format_bytes(1.2 * 1024**4)
        assert "TB" in result
        assert "1.2" in result


# ------------------------------------------------------------------
# _format_duration
# ------------------------------------------------------------------

class TestFormatDuration:
    def test_zero(self):
        assert _format_duration(0) == "0:00"

    def test_seconds(self):
        assert _format_duration(45) == "0:45"

    def test_minutes(self):
        assert _format_duration(125) == "2:05"

    def test_hours(self):
        assert _format_duration(3661) == "1:01:01"

    def test_negative(self):
        assert _format_duration(-5) == "0:00"


# ------------------------------------------------------------------
# Regex patterns
# ------------------------------------------------------------------

class TestScanRegex:
    def test_matches_scan_marker(self):
        m = _SCAN_RE.match("@@SCAN:Documents:1234567@@")
        assert m is not None
        assert m.group(1) == "Documents"
        assert m.group(2) == "1234567"

    def test_no_match_on_plain_text(self):
        assert _SCAN_RE.match("Scanning remote folder sizes...") is None

    def test_matches_zero_size(self):
        m = _SCAN_RE.match("@@SCAN:Desktop:0@@")
        assert m is not None
        assert m.group(2) == "0"


class TestTotalRegex:
    def test_matches_total_marker(self):
        m = _TOTAL_RE.match("@@TOTAL:9876543210@@")
        assert m is not None
        assert m.group(1) == "9876543210"

    def test_no_match_on_scan_marker(self):
        assert _TOTAL_RE.match("@@SCAN:Desktop:100@@") is None


class TestFolderStartRegex:
    def test_matches(self):
        m = _FOLDER_START_RE.match("@@FOLDER_START:Desktop@@")
        assert m is not None
        assert m.group(1) == "Desktop"

    def test_no_match_on_done(self):
        assert _FOLDER_START_RE.match("@@FOLDER_DONE:Desktop@@") is None


class TestFolderDoneRegex:
    def test_matches(self):
        m = _FOLDER_DONE_RE.match("@@FOLDER_DONE:Downloads@@")
        assert m is not None
        assert m.group(1) == "Downloads"


class TestProgress2Regex:
    def test_matches_typical_line(self):
        line = "  1,234,567,890  45%  12.34MB/s    0:01:23"
        m = _PROGRESS2_RE.match(line)
        assert m is not None
        assert m.group("pct") == "45"
        assert m.group("speed") == "12.34MB/s"
        assert m.group("eta") == "0:01:23"

    def test_matches_100_percent(self):
        line = "  9,876,543,210  100%  50.00MB/s    0:00:00"
        m = _PROGRESS2_RE.match(line)
        assert m is not None
        assert m.group("pct") == "100"

    def test_matches_no_commas_in_bytes(self):
        line = "  12345  10%  1.00kB/s    0:05"
        m = _PROGRESS2_RE.match(line)
        assert m is not None
        assert m.group("bytes") == "12345"
        assert m.group("pct") == "10"

    def test_no_match_on_plain_text(self):
        assert _PROGRESS2_RE.match("=== Syncing Desktop from host ===") is None


# ------------------------------------------------------------------
# MigrationProgress
# ------------------------------------------------------------------

class TestMigrationProgress:
    def test_initial_state(self):
        p = MigrationProgress()
        assert p.total_bytes == 0
        assert p.bytes_completed == 0
        assert p.overall_pct == 0.0
        assert p.current_folder is None
        assert p.completed_folders == []

    def test_bytes_completed_with_done_folders(self):
        p = MigrationProgress()
        p.folder_sizes = {"Desktop": 1000, "Documents": 2000, "Downloads": 3000}
        p.total_bytes = 6000
        p.completed_folders = ["Desktop", "Documents"]
        assert p.bytes_completed == 3000

    def test_bytes_completed_includes_current_folder_progress(self):
        p = MigrationProgress()
        p.folder_sizes = {"Desktop": 1000, "Documents": 2000}
        p.total_bytes = 3000
        p.completed_folders = ["Desktop"]
        p.current_folder = "Documents"
        p.current_pct = 50
        # Desktop (1000) + 50% of Documents (1000) = 2000
        assert p.bytes_completed == 2000

    def test_overall_pct(self):
        p = MigrationProgress()
        p.folder_sizes = {"Desktop": 1000, "Documents": 3000}
        p.total_bytes = 4000
        p.completed_folders = ["Desktop"]
        # 1000 / 4000 = 25%
        assert p.overall_pct == 25.0

    def test_overall_pct_zero_total(self):
        p = MigrationProgress()
        p.total_bytes = 0
        assert p.overall_pct == 0.0

    def test_overall_pct_capped_at_100(self):
        p = MigrationProgress()
        p.folder_sizes = {"Desktop": 5000}
        p.total_bytes = 1000  # total smaller than folder (edge case)
        p.completed_folders = ["Desktop"]
        assert p.overall_pct == 100.0

    def test_summary_line_contains_sizes(self):
        p = MigrationProgress()
        p.folder_sizes = {"Desktop": 1024 * 1024}  # 1 MB
        p.total_bytes = 10 * 1024 * 1024  # 10 MB
        p.completed_folders = ["Desktop"]
        p.current_folder = None
        summary = p.summary_line()
        assert "MB" in summary
        assert "remaining" in summary

    def test_summary_line_includes_speed(self):
        p = MigrationProgress()
        p.total_bytes = 1000
        p.current_speed = "5.00MB/s"
        summary = p.summary_line()
        assert "5.00MB/s" in summary

    def test_eta_display_estimating_at_start(self):
        p = MigrationProgress()
        assert p.eta_display == "estimating..."

    def test_elapsed_seconds_zero_before_start(self):
        p = MigrationProgress()
        assert p.elapsed_seconds == 0.0

    def test_elapsed_seconds_after_start(self):
        p = MigrationProgress()
        p.start()
        # Just check it's positive (timing-dependent)
        assert p.elapsed_seconds >= 0.0
