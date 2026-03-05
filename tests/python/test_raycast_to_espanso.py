"""Tests for scripts/raycast_to_espanso.py — Raycast snippet to Espanso converter."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

# Add scripts/ to path so we can import the converter module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import raycast_to_espanso as converter


class TestConvertSnippets:
    """Core conversion logic."""

    def test_basic_snippet(self):
        snippets = [{"name": "Email", "text": "user@example.com", "keyword": "@@"}]
        matches = converter.convert_snippets(snippets)
        assert len(matches) == 1
        assert matches[0]["trigger"] == ":@@"
        assert matches[0]["replace"] == "user@example.com"
        assert matches[0]["label"] == "Email"

    def test_keyword_already_has_colon(self):
        snippets = [{"name": "Test", "text": "hello", "keyword": ":hi"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["trigger"] == ":hi"

    def test_no_keyword_skipped(self):
        snippets = [{"name": "No Trigger", "text": "orphan text"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert len(matches) == 0
        assert any("Skipped" in w and "No Trigger" in w for w in warnings)

    def test_empty_keyword_skipped(self):
        snippets = [{"name": "Blank", "text": "text", "keyword": "  "}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert len(matches) == 0

    def test_empty_input(self):
        matches = converter.convert_snippets([])
        assert matches == []

    def test_no_name_no_label(self):
        snippets = [{"text": "hello", "keyword": "hi"}]
        matches = converter.convert_snippets(snippets)
        assert "label" not in matches[0]

    def test_multiple_snippets(self):
        snippets = [
            {"name": "A", "text": "aaa", "keyword": "a"},
            {"name": "B", "text": "bbb", "keyword": "b"},
            {"name": "C", "text": "ccc", "keyword": "c"},
        ]
        matches = converter.convert_snippets(snippets)
        assert len(matches) == 3
        assert [m["trigger"] for m in matches] == [":a", ":b", ":c"]


class TestPlaceholderMapping:
    """Raycast placeholder -> Espanso conversion."""

    def test_clipboard_placeholder(self):
        snippets = [{"name": "Paste", "text": "prefix {clipboard} suffix", "keyword": "cp"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "prefix {{clipboard}} suffix"
        assert "vars" not in matches[0]

    def test_date_placeholder(self):
        snippets = [{"name": "Date", "text": "Today: {date}", "keyword": "td"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "Today: {{date}}"
        assert len(matches[0]["vars"]) == 1
        assert matches[0]["vars"][0]["name"] == "date"
        assert matches[0]["vars"][0]["type"] == "date"
        assert matches[0]["vars"][0]["params"]["format"] == "%Y-%m-%d"

    def test_time_placeholder(self):
        snippets = [{"name": "Time", "text": "Now: {time}", "keyword": "tn"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "Now: {{time}}"
        assert matches[0]["vars"][0]["params"]["format"] == "%H:%M"

    def test_datetime_placeholder(self):
        snippets = [{"name": "DT", "text": "{datetime}", "keyword": "dt"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{datetime}}"
        assert matches[0]["vars"][0]["params"]["format"] == "%Y-%m-%d %H:%M"

    def test_day_placeholder(self):
        snippets = [{"name": "Day", "text": "{day}", "keyword": "dy"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{day}}"
        assert matches[0]["vars"][0]["params"]["format"] == "%A"

    def test_multiple_date_vars(self):
        snippets = [{"name": "Full", "text": "{date} at {time}", "keyword": "ft"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{date}} at {{time}}"
        var_names = {v["name"] for v in matches[0]["vars"]}
        assert var_names == {"date", "time"}

    def test_unsupported_cursor_stripped(self):
        snippets = [{"name": "Sig", "text": "Hello{cursor}", "keyword": "sig"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "Hello"
        assert any("{cursor}" in w for w in warnings)

    def test_unsupported_uuid_stripped(self):
        snippets = [{"name": "ID", "text": "id-{uuid}", "keyword": "uid"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "id-"
        assert any("{uuid}" in w for w in warnings)

    def test_unsupported_selection_stripped(self):
        snippets = [{"name": "Sel", "text": "({selection})", "keyword": "sel"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "()"
        assert any("{selection}" in w for w in warnings)

    def test_unsupported_argument_stripped(self):
        snippets = [{"name": "Arg", "text": "run {argument}", "keyword": "rn"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "run "
        assert any("{argument}" in w for w in warnings)

    def test_unsupported_browser_tab_stripped(self):
        snippets = [{"name": "Tab", "text": "url: {browser-tab}", "keyword": "bt"}]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "url: "

    def test_unsupported_snippet_ref_stripped(self):
        snippets = [
            {"name": "Ref", "text": 'see {snippet name="other"}', "keyword": "ref"}
        ]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "see "

    def test_mixed_supported_and_unsupported(self):
        snippets = [
            {"name": "Mix", "text": "{date} {cursor} {clipboard}", "keyword": "mx"}
        ]
        warnings: list[str] = []
        matches = converter.convert_snippets(snippets, warnings)
        assert matches[0]["replace"] == "{{date}}  {{clipboard}}"
        assert len(matches[0]["vars"]) == 1
        assert any("{cursor}" in w for w in warnings)


class TestIcuToStrftime:
    """ICU/Java date format → Python strftime translation."""

    def test_simple_date(self):
        assert converter.icu_to_strftime("yyyy-MM-dd") == "%Y-%m-%d"

    def test_datetime_no_separator(self):
        assert converter.icu_to_strftime("yyyy-MM-dd HHmm") == "%Y-%m-%d %H%M"

    def test_quoted_literal(self):
        assert converter.icu_to_strftime("'GMT'Z") == "GMT%z"

    def test_full_month_name(self):
        assert converter.icu_to_strftime("MMMM dd, yyyy") == "%B %d, %Y"

    def test_abbreviated_month(self):
        assert converter.icu_to_strftime("dd MMM yyyy") == "%d %b %Y"

    def test_weekday(self):
        assert converter.icu_to_strftime("EEEE, MMMM dd") == "%A, %B %d"

    def test_12_hour_with_ampm(self):
        assert converter.icu_to_strftime("hh:mm a") == "%I:%M %p"

    def test_time_with_seconds(self):
        assert converter.icu_to_strftime("HH:mm:ss") == "%H:%M:%S"

    def test_passthrough_chars(self):
        assert converter.icu_to_strftime("yyyy/MM/dd") == "%Y/%m/%d"

    def test_empty_string(self):
        assert converter.icu_to_strftime("") == ""

    def test_only_literal(self):
        assert converter.icu_to_strftime("'hello'") == "hello"

    def test_two_digit_year(self):
        assert converter.icu_to_strftime("MM/dd/yy") == "%m/%d/%y"


class TestParametricPlaceholders:
    """Parametric {date format="..."} and {time format="..."} conversion."""

    def test_parametric_date(self):
        snippets = [{"name": "Date", "text": '{date format="yyyy-MM-dd"}', "keyword": "d;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{date}}"
        assert len(matches[0]["vars"]) == 1
        assert matches[0]["vars"][0]["name"] == "date"
        assert matches[0]["vars"][0]["params"]["format"] == "%Y-%m-%d"

    def test_parametric_datetime(self):
        snippets = [{"name": "DT", "text": '{date format="yyyy-MM-dd HHmm"}', "keyword": "dt;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{date}}"
        assert matches[0]["vars"][0]["params"]["format"] == "%Y-%m-%d %H%M"

    def test_parametric_gmt_offset(self):
        snippets = [{"name": "TZ", "text": """{date format="'GMT'Z"}""", "keyword": "dtz;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{date}}"
        assert matches[0]["vars"][0]["params"]["format"] == "GMT%z"

    def test_parametric_time(self):
        snippets = [{"name": "Time", "text": '{time format="HH:mm"}', "keyword": "t;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{time}}"
        assert matches[0]["vars"][0]["params"]["format"] == "%H:%M"

    def test_parametric_with_surrounding_text(self):
        snippets = [{"name": "Stamped", "text": 'Created: {date format="yyyy-MM-dd"} done', "keyword": "st;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "Created: {{date}} done"

    def test_multiple_parametric(self):
        snippets = [{"name": "Both", "text": '{date format="yyyy-MM-dd"} at {date format="HH:mm"}', "keyword": "both;;"}]
        matches = converter.convert_snippets(snippets)
        assert matches[0]["replace"] == "{{date}} at {{date2}}"
        assert len(matches[0]["vars"]) == 2
        assert matches[0]["vars"][0]["params"]["format"] == "%Y-%m-%d"
        assert matches[0]["vars"][1]["params"]["format"] == "%H:%M"


class TestYamlOutput:
    """YAML serialization."""

    def test_valid_yaml_roundtrip(self):
        snippets = [{"name": "Test", "text": "hello world", "keyword": "hw"}]
        matches = converter.convert_snippets(snippets)
        yaml_str = converter.build_espanso_yaml(matches)
        parsed = yaml.safe_load(yaml_str)
        assert "matches" in parsed
        assert len(parsed["matches"]) == 1
        assert parsed["matches"][0]["trigger"] == ":hw"

    def test_multiline_text(self):
        snippets = [{"name": "Multi", "text": "line1\nline2\nline3", "keyword": "ml"}]
        matches = converter.convert_snippets(snippets)
        yaml_str = converter.build_espanso_yaml(matches)
        parsed = yaml.safe_load(yaml_str)
        assert parsed["matches"][0]["replace"] == "line1\nline2\nline3"

    def test_unicode_preserved(self):
        snippets = [{"name": "Unicode", "text": "café ñ 日本語", "keyword": "uni"}]
        matches = converter.convert_snippets(snippets)
        yaml_str = converter.build_espanso_yaml(matches)
        assert "café" in yaml_str
        assert "日本語" in yaml_str

    def test_empty_matches_valid_yaml(self):
        yaml_str = converter.build_espanso_yaml([])
        parsed = yaml.safe_load(yaml_str)
        assert parsed == {"matches": []}


class TestConvertFile:
    """End-to-end file conversion."""

    def test_convert_file_to_string(self, tmp_path):
        input_file = tmp_path / "snippets.json"
        input_file.write_text(json.dumps([
            {"name": "Email", "text": "user@example.com", "keyword": "@@"},
            {"name": "Phone", "text": "555-1234", "keyword": "ph"},
        ]))
        result = converter.convert_file(str(input_file))
        parsed = yaml.safe_load(result)
        assert len(parsed["matches"]) == 2

    def test_convert_file_with_output(self, tmp_path):
        input_file = tmp_path / "snippets.json"
        input_file.write_text(json.dumps([
            {"name": "Test", "text": "hello", "keyword": "hi"},
        ]))
        output_file = tmp_path / "output.yml"
        with open(output_file, "w") as f:
            converter.convert_file(str(input_file), f)
        parsed = yaml.safe_load(output_file.read_text())
        assert parsed["matches"][0]["trigger"] == ":hi"

    def test_convert_file_warnings_on_stderr(self, tmp_path, capsys):
        input_file = tmp_path / "snippets.json"
        input_file.write_text(json.dumps([
            {"name": "NoKey", "text": "orphan"},
        ]))
        converter.convert_file(str(input_file))
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "Skipped" in captured.err
