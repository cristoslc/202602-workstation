#!/usr/bin/env python3
"""Workstation status dashboard (stub).

Run via: uv run --with rich scripts/workstation-status.py

Phase 1 (now): prints basic status info.
Phase 2 (later): Rich tables, dotfile link health, package versions.
"""

import os
import platform
import subprocess
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel

    console = Console()

    # System info
    console.print(Panel(
        f"[bold]Platform:[/bold] {platform.system()} {platform.release()}\n"
        f"[bold]Machine:[/bold] {platform.machine()}\n"
        f"[bold]Shell:[/bold] {os.environ.get('SHELL', 'unknown')}",
        title="System Info",
    ))

    # Age key status
    age_key = Path.home() / ".config" / "sops" / "age" / "keys.txt"
    key_status = "[green]Found[/green]" if age_key.exists() else "[red]Not found[/red]"
    console.print(f"\nAge key: {key_status} ({age_key})")

    # Tool check
    table = Table(title="Tool Status")
    table.add_column("Tool", style="cyan")
    table.add_column("Status", style="green")

    for tool in ["git", "zsh", "node", "docker", "code", "ansible-playbook", "sops", "age", "stow", "uv"]:
        try:
            result = subprocess.run([tool, "--version"], capture_output=True, text=True, timeout=5)
            version = result.stdout.strip().split("\n")[0] if result.returncode == 0 else "not found"
            status = f"[green]{version}[/green]" if result.returncode == 0 else "[red]not installed[/red]"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            status = "[red]not installed[/red]"
        table.add_row(tool, status)

    console.print(table)

except ImportError:
    print("Rich not available. Install with: uv run --with rich scripts/workstation-status.py")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Shell: {os.environ.get('SHELL', 'unknown')}")
