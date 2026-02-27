#!/usr/bin/env python3
"""Convert Raycast snippet exports (JSON) to Espanso match files (YAML).

Usage:
    uv run --with pyyaml scripts/raycast_to_espanso.py input.json [output.yml]

If output is omitted, writes to stdout.

Placeholder mapping:
    {clipboard}  -> {{clipboard}}
    {date}       -> Espanso date extension (YYYY-MM-DD)
    {time}       -> Espanso date extension (HH:MM)
    {datetime}   -> Espanso date extension (YYYY-MM-DD HH:MM)
    {day}        -> Espanso date extension (dddd)
    Others       -> stripped with warning on stderr
"""

from __future__ import annotations

import json
import re
import sys
from typing import TextIO

import yaml

# Raycast placeholders that map directly to Espanso's clipboard extension.
_CLIPBOARD_PLACEHOLDER = re.compile(r"\{clipboard\}")

# Raycast date/time placeholders -> Espanso date extension format strings.
_DATE_FORMATS: dict[str, str] = {
    "{date}": "%Y-%m-%d",
    "{time}": "%H:%M",
    "{datetime}": "%Y-%m-%d %H:%M",
    "{day}": "%A",
}

# Raycast placeholders with no Espanso equivalent — stripped with a warning.
_UNSUPPORTED_PLACEHOLDERS = re.compile(
    r"\{(?:cursor|uuid|selection|argument|browser-tab|snippet name=\"[^\"]*\")\}"
)


def _convert_text(text: str, name: str, warnings: list[str]) -> str | dict:
    """Convert Raycast snippet text to Espanso replacement value.

    Returns a plain string for simple replacements, or a list of form/date
    blocks when date extensions are needed.
    """
    # Check for unsupported placeholders first (collect warnings).
    for match in _UNSUPPORTED_PLACEHOLDERS.finditer(text):
        warnings.append(
            f"Snippet {name!r}: stripped unsupported placeholder {match.group()}"
        )
    text = _UNSUPPORTED_PLACEHOLDERS.sub("", text)

    # Map {clipboard} -> {{clipboard}}.
    text = _CLIPBOARD_PLACEHOLDER.sub("{{clipboard}}", text)

    # Check for date/time placeholders — these require Espanso's date extension.
    date_vars: list[dict] = []
    for placeholder, fmt in _DATE_FORMATS.items():
        if placeholder in text:
            var_name = placeholder.strip("{}")
            text = text.replace(placeholder, "{{" + var_name + "}}")
            date_vars.append({"name": var_name, "type": "date", "params": {"format": fmt}})

    if date_vars:
        return {"text": text, "vars": date_vars}
    return text


def convert_snippets(
    snippets: list[dict],
    warnings_out: list[str] | None = None,
) -> list[dict]:
    """Convert a list of Raycast snippet dicts to Espanso match dicts.

    Each Raycast snippet has keys: name, text, keyword (optional).
    Returns a list of Espanso match dicts with trigger, replace, and label.
    Snippets without a keyword are skipped (Espanso requires a trigger).
    """
    warnings: list[str] = warnings_out if warnings_out is not None else []
    matches: list[dict] = []

    for snippet in snippets:
        keyword = snippet.get("keyword", "").strip()
        if not keyword:
            name = snippet.get("name", "<unnamed>")
            warnings.append(f"Skipped snippet {name!r}: no keyword defined")
            continue

        # Espanso convention: triggers start with ':'.
        if not keyword.startswith(":"):
            keyword = ":" + keyword

        name = snippet.get("name", "")
        text = snippet.get("text", "")
        converted = _convert_text(text, name, warnings)

        match: dict = {"trigger": keyword}

        if isinstance(converted, dict):
            # Date extension needed — use replace + vars.
            match["replace"] = converted["text"]
            match["vars"] = converted["vars"]
        else:
            match["replace"] = converted

        if name:
            match["label"] = name

        matches.append(match)

    return matches


def build_espanso_yaml(matches: list[dict]) -> str:
    """Serialize Espanso matches to YAML string."""
    return yaml.dump(
        {"matches": matches},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def convert_file(
    input_path: str,
    output: TextIO | None = None,
) -> str:
    """Read Raycast JSON, convert, write Espanso YAML.

    Returns the YAML string. Warnings are printed to stderr.
    """
    with open(input_path, encoding="utf-8") as f:
        snippets = json.load(f)

    warnings: list[str] = []
    matches = convert_snippets(snippets, warnings)

    for w in warnings:
        print(f"WARNING: {w}", file=sys.stderr)

    yaml_str = build_espanso_yaml(matches)

    if output is not None:
        output.write(yaml_str)

    return yaml_str


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.json [output.yml]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
        with open(output_path, "w", encoding="utf-8") as f:
            convert_file(input_path, f)
        print(f"Wrote {output_path}", file=sys.stderr)
    else:
        convert_file(input_path, sys.stdout)


if __name__ == "__main__":
    main()
