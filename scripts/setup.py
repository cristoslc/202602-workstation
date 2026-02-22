#!/usr/bin/env python3
"""Workstation setup wizard — unified first-run + bootstrap.

Run via: ./setup.sh
Direct: uv run --with textual,pyyaml scripts/setup.py [--debug]
"""

from __future__ import annotations

import argparse
import os
import sys

# Restrict file creation to owner-only (defense-in-depth).
os.umask(0o077)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Workstation setup wizard (Textual TUI)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    from setup_tui.app import SetupApp

    app = SetupApp(debug=args.debug)
    app.run()


if __name__ == "__main__":
    main()
