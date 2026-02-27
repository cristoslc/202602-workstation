"""Verification engine — load registry, run checks, report results."""

from __future__ import annotations

import os
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "verify-registry.yml"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Phase display names (matches playbook naming).
PHASE_DISPLAY = {
    "system": "System",
    "security": "Security",
    "dev-tools": "Dev Tools",
    "desktop": "Desktop",
    "dotfiles": "Dotfiles",
    "gaming": "Gaming",
    "bureau-veritas": "Bureau Veritas",
    "remote-access": "Remote Access",
    "sync": "Sync",
}

# Canonical phase order.
PHASE_ORDER = list(PHASE_DISPLAY.keys())


@dataclass
class AppEntry:
    """A single app/tool to verify."""

    name: str
    role: str
    phase: str
    platforms: list[str]
    check: dict[str, object]
    tags: list[str] = field(default_factory=list)
    version_flag: str = "--version"
    optional: bool = False
    note: str = ""


@dataclass
class CheckResult:
    """Outcome of verifying a single AppEntry."""

    entry: AppEntry
    passed: bool
    detail: str  # version string, path, or error message
    skipped: bool = False


@dataclass
class StowLayerResult:
    """Outcome of checking one stow symlink layer."""

    label: str
    total: int
    healthy: int
    broken: list[str]


def load_registry(path: Path | None = None) -> list[AppEntry]:
    """Parse verify-registry.yml and return a flat list of AppEntry."""
    path = path or REGISTRY_PATH
    with open(path) as f:
        data = yaml.safe_load(f)

    entries: list[AppEntry] = []
    for role_name, role_data in data.get("roles", {}).items():
        phase = role_data.get("phase", "")
        for app in role_data.get("apps", []):
            entries.append(
                AppEntry(
                    name=app["name"],
                    role=role_name,
                    phase=phase,
                    platforms=app.get("platforms", []),
                    check=app.get("check", {}),
                    tags=app.get("tags", []),
                    version_flag=app.get("version_flag", "--version"),
                    optional=app.get("optional", False),
                    note=app.get("note", ""),
                )
            )
    return entries


def filter_entries(
    entries: list[AppEntry],
    *,
    platform: str | None = None,
    roles: list[str] | None = None,
    tags: list[str] | None = None,
    phases: list[str] | None = None,
) -> list[AppEntry]:
    """Filter entries by platform, role, tag, and/or phase."""
    result = entries
    if platform:
        result = [e for e in result if platform in e.platforms]
    if roles:
        role_set = set(roles)
        result = [e for e in result if e.role in role_set]
    if tags:
        tag_set = set(tags)
        result = [e for e in result if tag_set & set(e.tags)]
    if phases:
        phase_set = set(phases)
        result = [e for e in result if e.phase in phase_set]
    return result


def run_check(entry: AppEntry, timeout: int = 5) -> CheckResult:
    """Run a single verification check."""
    check = entry.check

    if "command" in check:
        return _check_command(entry, str(check["command"]), timeout)
    elif "app_paths" in check:
        return _check_app_paths(entry, list(check["app_paths"]))
    elif "path" in check:
        return _check_path(entry, str(check["path"]))
    else:
        return CheckResult(entry=entry, passed=False, detail="unknown check type")


def run_all_checks(
    entries: list[AppEntry],
    *,
    parallel: bool = True,
    timeout: int = 5,
    on_result: object | None = None,
) -> list[CheckResult]:
    """Run checks for all entries. Optionally call on_result(CheckResult) as each completes."""
    if not parallel:
        results = []
        for entry in entries:
            result = run_check(entry, timeout=timeout)
            results.append(result)
            if on_result:
                on_result(result)
        return results

    results: list[CheckResult] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_to_entry = {
            pool.submit(run_check, entry, timeout): entry for entry in entries
        }
        for future in as_completed(future_to_entry):
            result = future.result()
            results.append(result)
            if on_result:
                on_result(result)
    return results


def check_stow_links(stow_dir: Path, target: Path) -> StowLayerResult:
    """Check symlink health for a stow directory."""
    total = 0
    healthy = 0
    broken: list[str] = []
    label = stow_dir.name

    if not stow_dir.exists():
        return StowLayerResult(label=label, total=0, healthy=0, broken=[])

    for pkg in stow_dir.iterdir():
        if not pkg.is_dir() or pkg.name.startswith("."):
            continue
        for root, _dirs, files in os.walk(pkg):
            for f in files:
                src = Path(root) / f
                rel = src.relative_to(pkg)
                dest = target / rel
                total += 1
                if dest.is_symlink() and dest.resolve().exists():
                    healthy += 1
                else:
                    broken.append(str(rel))

    return StowLayerResult(label=label, total=total, healthy=healthy, broken=broken)


def check_all_stow_layers(platform: str) -> list[StowLayerResult]:
    """Check symlink health across all stow layers."""
    home = Path.home()
    platform_dir = "macos" if platform == "macos" else "linux"
    layers = [
        ("Shared dotfiles", REPO_ROOT / "shared" / "dotfiles"),
        (
            "Shared secrets",
            REPO_ROOT / "shared" / "secrets" / ".decrypted" / "dotfiles",
        ),
        (
            f"{platform_dir.title()} dotfiles",
            REPO_ROOT / platform_dir / "dotfiles",
        ),
        (
            f"{platform_dir.title()} secrets",
            REPO_ROOT / platform_dir / "secrets" / ".decrypted" / "dotfiles",
        ),
    ]
    results = []
    for label, stow_dir in layers:
        result = check_stow_links(stow_dir, home)
        result.label = label
        results.append(result)
    return results


# ── Private helpers ──────────────────────────────────────────────────


def _check_command(entry: AppEntry, cmd: str, timeout: int) -> CheckResult:
    """Check a CLI tool: which + version probe."""
    which_path = shutil.which(cmd)
    if not which_path:
        return CheckResult(entry=entry, passed=False, detail="not installed")

    # Try version probe for detail.
    try:
        result = subprocess.run(
            [cmd, entry.version_flag],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            ver = (result.stdout.strip() or result.stderr.strip()).split("\n")[0]
            return CheckResult(entry=entry, passed=True, detail=ver)
        # Command exists but version flag failed — still pass.
        return CheckResult(entry=entry, passed=True, detail=which_path)
    except (subprocess.TimeoutExpired, OSError):
        # Exists but version probe failed — still counts as installed.
        return CheckResult(entry=entry, passed=True, detail=which_path)


def _check_app_paths(entry: AppEntry, paths: list[str]) -> CheckResult:
    """Check desktop app by path existence."""
    for p in paths:
        expanded = Path(p).expanduser()
        if expanded.exists():
            return CheckResult(entry=entry, passed=True, detail=str(expanded))
    return CheckResult(entry=entry, passed=False, detail="not found")


def _check_path(entry: AppEntry, path: str) -> CheckResult:
    """Check a file or directory by path."""
    expanded = Path(path).expanduser()
    if expanded.exists():
        return CheckResult(entry=entry, passed=True, detail=str(expanded))
    return CheckResult(entry=entry, passed=False, detail="not found")
