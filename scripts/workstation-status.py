#!/usr/bin/env python3
"""Headless workstation verification.

Exit codes: 0 = all pass, 1 = failures, 2 = runtime error.

Usage:
    uv run --with pyyaml scripts/workstation-status.py --verify
    uv run --with pyyaml scripts/workstation-status.py --verify --role git
    uv run --with pyyaml scripts/workstation-status.py --verify --phase dev-tools
"""

from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

# Add scripts/ to path so we can import setup_tui.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from setup_tui.lib.verify import (
    CheckResult,
    filter_entries,
    load_registry,
    run_all_checks,
)


def detect_platform() -> str:
    return "macos" if platform.system() == "Darwin" else "linux"


def main() -> None:
    parser = argparse.ArgumentParser(description="Workstation verification")
    parser.add_argument(
        "--verify", action="store_true", help="Run verification checks"
    )
    parser.add_argument(
        "--role", type=str, default=None, help="Filter to a specific role"
    )
    parser.add_argument(
        "--phase", type=str, default=None, help="Filter to a specific phase"
    )
    parser.add_argument(
        "--tag", type=str, default=None, help="Filter to a specific tag"
    )
    args = parser.parse_args()

    if not args.verify:
        parser.print_help()
        sys.exit(2)

    try:
        entries = load_registry()
    except Exception as exc:
        print(f"ERROR: Failed to load registry: {exc}", file=sys.stderr)
        sys.exit(2)

    plat = detect_platform()
    entries = filter_entries(
        entries,
        platform=plat,
        roles=[args.role] if args.role else None,
        phases=[args.phase] if args.phase else None,
        tags=[args.tag] if args.tag else None,
    )

    if not entries:
        print(f"No entries match the given filters (platform={plat}).")
        sys.exit(0)

    results = run_all_checks(entries, parallel=True)

    # Sort by phase then name for readable output.
    results.sort(key=lambda r: (r.entry.phase, r.entry.name))

    pass_count = 0
    fail_count = 0
    warn_count = 0

    current_phase = ""
    for r in results:
        if r.entry.phase != current_phase:
            current_phase = r.entry.phase
            print(f"\n  {current_phase}")
            print(f"  {'─' * 60}")

        if r.passed:
            mark = "PASS"
            pass_count += 1
        elif r.entry.optional:
            mark = "WARN"
            warn_count += 1
        else:
            mark = "FAIL"
            fail_count += 1

        note = ""
        if not r.passed and r.entry.optional and r.entry.note:
            note = f" ({r.entry.note})"

        print(f"  {mark:4s}  {r.entry.name:<30s} {r.detail}{note}")

    print(f"\n  {pass_count} passed, {fail_count} failed, {warn_count} warnings\n")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
