#!/usr/bin/env python3
"""Convert Raycast snippet exports (JSON) to Espanso match files (YAML).

Usage:
    uv run --with pyyaml scripts/raycast_to_espanso.py input.json [output.yml]

If output is omitted, writes to stdout.

Placeholder mapping:
    {clipboard}             -> {{clipboard}}
    {date}                  -> Espanso date extension (YYYY-MM-DD)
    {time}                  -> Espanso date extension (HH:MM)
    {datetime}              -> Espanso date extension (YYYY-MM-DD HH:MM)
    {day}                   -> Espanso date extension (dddd)
    {date format="..."}     -> Espanso date extension (ICU format translated to strftime)
    {time format="..."}     -> Espanso date extension (ICU format translated to strftime)
    Others                  -> stripped with warning on stderr
"""

from __future__ import annotations

import json
import re
import sys
from typing import TextIO

import yaml

# ICU/Java date format tokens → Python strftime equivalents.
# Ordered longest-first so e.g. MMMM matches before MMM before MM.
_ICU_TO_STRFTIME: list[tuple[str, str]] = [
    ("MMMM", "%B"),   # Full month name
    ("MMM", "%b"),    # Abbreviated month name
    ("MM", "%m"),     # Zero-padded month number
    ("EEEE", "%A"),   # Full weekday name
    ("EEE", "%a"),    # Abbreviated weekday name
    ("yyyy", "%Y"),   # 4-digit year
    ("yy", "%y"),     # 2-digit year
    ("dd", "%d"),     # Zero-padded day
    ("HH", "%H"),     # 24-hour hour
    ("hh", "%I"),     # 12-hour hour
    ("mm", "%M"),     # Minute
    ("ss", "%S"),     # Second
    ("a", "%p"),      # AM/PM
    ("Z", "%z"),      # Timezone offset
]


def icu_to_strftime(icu_format: str) -> str:
    """Translate an ICU/Java date format string to Python strftime.

    Handles quoted literals (e.g., ``'GMT'`` → ``GMT``), ICU tokens,
    and passes through non-token characters (hyphens, spaces, colons).
    """
    result: list[str] = []
    i = 0
    while i < len(icu_format):
        # Quoted literal: 'GMT' → GMT, '' → '
        if icu_format[i] == "'":
            end = icu_format.index("'", i + 1) if "'" in icu_format[i + 1:] else len(icu_format)
            literal = icu_format[i + 1:end]
            # Escape any % in literals so strftime doesn't interpret them.
            result.append(literal.replace("%", "%%"))
            i = end + 1
            continue

        # Try each ICU token (longest-first).
        matched = False
        for token, code in _ICU_TO_STRFTIME:
            if icu_format[i:i + len(token)] == token:
                result.append(code)
                i += len(token)
                matched = True
                break

        if not matched:
            # Pass through non-token characters (-, :, space, T, etc.).
            ch = icu_format[i]
            # Escape % so strftime doesn't choke on literal percent signs.
            result.append("%%" if ch == "%" else ch)
            i += 1

    return "".join(result)


# Raycast placeholders that map directly to Espanso's clipboard extension.
_CLIPBOARD_PLACEHOLDER = re.compile(r"\{clipboard\}")

# Raycast date/time placeholders -> Espanso date extension format strings.
_DATE_FORMATS: dict[str, str] = {
    "{date}": "%Y-%m-%d",
    "{time}": "%H:%M",
    "{datetime}": "%Y-%m-%d %H:%M",
    "{day}": "%A",
}

# Parametric Raycast date/time placeholders: {date format="..."} or {time format="..."}.
_PARAMETRIC_DATE = re.compile(r"\{(date|time)\s+format=\"([^\"]+)\"\}")

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

    # Check for parametric date/time placeholders first (e.g., {date format="yyyy-MM-dd"}).
    date_vars: list[dict] = []
    param_counter = 0
    for match in _PARAMETRIC_DATE.finditer(text):
        param_counter += 1
        kind = match.group(1)  # "date" or "time"
        icu_fmt = match.group(2)
        strftime_fmt = icu_to_strftime(icu_fmt)
        var_name = kind if param_counter == 1 else f"{kind}{param_counter}"
        date_vars.append({"name": var_name, "type": "date", "params": {"format": strftime_fmt}})
    if date_vars:
        # Replace all parametric matches, assigning unique var names.
        idx = 0
        def _indexed_replacer(m: re.Match) -> str:
            nonlocal idx
            idx += 1
            kind = m.group(1)
            var_name = kind if idx == 1 else f"{kind}{idx}"
            return "{{" + var_name + "}}"
        text = _PARAMETRIC_DATE.sub(_indexed_replacer, text)

    # Check for simple date/time placeholders (e.g., {date}, {time}).
    # Use regex to avoid matching inside already-substituted {{var}} references.
    for placeholder, fmt in _DATE_FORMATS.items():
        var_name = placeholder.strip("{}")
        # Match {date} but not {{date}} — negative lookbehind/lookahead for braces.
        simple_re = re.compile(r"(?<!\{)\{" + re.escape(var_name) + r"\}(?!\})")
        if simple_re.search(text):
            text = simple_re.sub("{{" + var_name + "}}", text)
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
