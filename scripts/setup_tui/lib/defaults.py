"""Editable defaults — action registry keybinding load/save and format conversion.

The action registry lives in shared/roles/keyboard/defaults/main.yml.
macOS Cmd and Linux Super are the same physical key, so the TUI presents
a single canonical binding per action (e.g. "Meta+Shift+V") and derives
both platform formats on save.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .runner import REPO_ROOT, ToolRunner

REGISTRY_PATH = (
    REPO_ROOT / "shared" / "roles" / "keyboard" / "defaults" / "main.yml"
)
ITERM2_PLIST_PATH = (
    REPO_ROOT / "macos" / "dotfiles" / "iterm2" / ".config" / "iterm2"
    / "com.googlecode.iterm2.plist"
)
RAYCAST_CONFIG_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "raycast" / "raycast.rayconfig.age"
)
RAYCAST_IMPORT_TMP = Path.home() / ".cache" / "workstation" / "raycast-import.rayconfig"
AGE_KEYS_PATH = Path.home() / ".config" / "sops" / "age" / "keys.txt"

_HEADER = """\
---
# Action registry: semantic actions with per-platform keybindings and implementations.
# The keyboard role reads this to configure Hammerspoon (macOS) and dconf (Linux).
#
# Modifier strategy — same physical keys on both platforms:
#   macOS Cmd  =  Linux Super  (same physical key)
#   +Shift where the bare combo conflicts (e.g. Cmd+V = paste → Cmd+Shift+V)
#
# This means muscle memory transfers 1:1 between machines.

"""

# ---------------------------------------------------------------------------
# Canonical display format  ↔  platform keybinding conversion
# ---------------------------------------------------------------------------
# Display uses "Meta" for the platform command key (Cmd on macOS, Super on Linux).
# Examples:
#   "Meta+Space"       →  linux: <Super>space        macOS: {mods: [cmd], key: space}
#   "Meta+Shift+V"     →  linux: <Super><Shift>v     macOS: {mods: [cmd, shift], key: v}
#   "Meta+Shift+Left"  →  linux: <Super><Shift>Left  macOS: {mods: [cmd, shift], key: left}

_DISPLAY_TO_LINUX_MOD = {"Meta": "Super", "Shift": "Shift", "Ctrl": "Ctrl", "Alt": "Alt"}
_LINUX_TO_DISPLAY_MOD = {v: k for k, v in _DISPLAY_TO_LINUX_MOD.items()}
_DISPLAY_TO_MACOS_MOD = {"Meta": "cmd", "Shift": "shift", "Ctrl": "ctrl", "Alt": "alt"}

# Arrow keys stay title-case in Linux dconf format.
_LINUX_TITLECASE_KEYS = {"Left", "Right", "Up", "Down"}


def _parse_linux_binding(binding: str) -> tuple[list[str], str]:
    """Parse '<Super><Shift>v' → (['Super', 'Shift'], 'v')."""
    mods = re.findall(r"<(\w+)>", binding)
    key = re.sub(r"<\w+>", "", binding)
    return mods, key


def keybinding_to_display(linux_binding: str) -> str:
    """Convert Linux dconf binding to canonical display format.

    '<Super><Shift>v' → 'Meta+Shift+V'
    '<Super>space'    → 'Meta+Space'
    '<Super>Left'     → 'Meta+Left'
    """
    mods, key = _parse_linux_binding(linux_binding)
    parts = [_LINUX_TO_DISPLAY_MOD.get(m, m) for m in mods]
    # Title-case the key for display: v→V, space→Space, Left→Left, 4→4
    display_key = key[0].upper() + key[1:] if key else key
    parts.append(display_key)
    return "+".join(parts)


def display_to_keybinding(display: str) -> dict:
    """Convert canonical display format to both platform keybindings.

    'Meta+Shift+V' → {
        linux: '<Super><Shift>v',
        macos: {mods: ['cmd', 'shift'], key: 'v'},
    }
    """
    parts = [p.strip() for p in display.split("+")]
    key_display = parts[-1]
    mod_displays = parts[:-1]

    # --- Linux ---
    linux_mods = [_DISPLAY_TO_LINUX_MOD.get(m, m) for m in mod_displays]
    if key_display in _LINUX_TITLECASE_KEYS:
        linux_key = key_display
    elif len(key_display) == 1 and key_display.isalpha():
        linux_key = key_display.lower()
    else:
        linux_key = key_display.lower()
    linux_binding = "".join(f"<{m}>" for m in linux_mods) + linux_key

    # --- macOS ---
    macos_mods = [_DISPLAY_TO_MACOS_MOD.get(m, m.lower()) for m in mod_displays]
    macos_key = key_display.lower()

    return {
        "linux": linux_binding,
        "macos": {"mods": macos_mods, "key": macos_key},
    }


# ---------------------------------------------------------------------------
# Load / save the action registry YAML
# ---------------------------------------------------------------------------


class _LiteralStr(str):
    """Marker for strings that should use YAML literal block style (|)."""


def _literal_representer(dumper: yaml.Dumper, data: _LiteralStr) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _literal_representer)


def load_action_registry(path: Path | None = None) -> list[dict]:
    """Load workstation_actions from the keyboard role defaults."""
    target = path or REGISTRY_PATH
    if not target.exists():
        return []
    with open(target) as f:
        data = yaml.safe_load(f)
    return data.get("workstation_actions", [])


def save_action_registry(
    actions: list[dict], path: Path | None = None
) -> None:
    """Write workstation_actions back to the keyboard role defaults."""
    target = path or REGISTRY_PATH

    # Tag multi-line lua strings for literal block style.
    for action in actions:
        impl = action.get("implementation", {})
        for platform in ("linux", "macos"):
            p_impl = impl.get(platform)
            if isinstance(p_impl, dict) and "lua" in p_impl:
                lua = p_impl["lua"]
                if "\n" in lua:
                    p_impl["lua"] = _LiteralStr(lua)

    body = yaml.dump(
        {"workstation_actions": actions},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    target.write_text(_HEADER + body)


def export_iterm2_plist(runner: ToolRunner) -> str:
    """Export iTerm2 preferences plist via the existing Make target."""
    result = runner.run(
        ["make", "iterm2-export"],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        msg = details or "make iterm2-export failed"
        raise RuntimeError(msg)
    return f"iTerm2 settings exported to {ITERM2_PLIST_PATH}"


# ---------------------------------------------------------------------------
# Import functions — mirror Ansible tasks for standalone re-import
# ---------------------------------------------------------------------------


def import_iterm2_settings(runner: ToolRunner) -> str:
    """Point iTerm2 at the stow-managed plist (mirrors iterm2.yml Ansible task).

    Runs two ``defaults write`` commands — non-interactive and idempotent.
    """
    runner.run(
        [
            "defaults", "write", "com.googlecode.iterm2",
            "PrefsCustomFolder", "-string", "~/.config/iterm2",
        ],
        check=True,
    )
    runner.run(
        [
            "defaults", "write", "com.googlecode.iterm2",
            "LoadPrefsFromCustomFolder", "-bool", "true",
        ],
        check=True,
    )
    return "iTerm2 configured to load settings from ~/.config/iterm2"


def import_raycast_settings(runner: ToolRunner) -> tuple[str, bool]:
    """Decrypt and open Raycast settings for import.

    Returns ``(message, needs_confirm)`` — when *needs_confirm* is True the
    caller should pause for the user to confirm the Raycast import dialog,
    then call :func:`cleanup_raycast_import`.
    """
    if not RAYCAST_CONFIG_AGE_PATH.exists():
        return (
            "No Raycast export found — skipping import. "
            "Configure manually, then run: make raycast-export",
            False,
        )
    RAYCAST_IMPORT_TMP.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-d",
            "-i", str(AGE_KEYS_PATH),
            "-o", str(RAYCAST_IMPORT_TMP),
            str(RAYCAST_CONFIG_AGE_PATH),
        ],
        check=True,
    )
    runner.run(["open", str(RAYCAST_IMPORT_TMP)], check=True)
    return (
        "Raycast import dialog opened — confirm the import in Raycast.",
        True,
    )


def cleanup_raycast_import() -> None:
    """Remove the temporary decrypted Raycast config."""
    RAYCAST_IMPORT_TMP.unlink(missing_ok=True)


def run_all_imports(
    runner: ToolRunner,
) -> tuple[list[str], bool]:
    """Orchestrate all settings imports.

    Returns ``(messages, needs_raycast_confirm)`` so screens can handle
    the suspend/confirm step for Raycast.
    """
    messages: list[str] = []
    needs_raycast_confirm = False

    # iTerm2
    try:
        msg = import_iterm2_settings(runner)
        messages.append(msg)
    except Exception as exc:
        messages.append(f"iTerm2 import failed: {exc}")

    # Raycast
    try:
        msg, needs_raycast_confirm = import_raycast_settings(runner)
        messages.append(msg)
    except Exception as exc:
        messages.append(f"Raycast import failed: {exc}")

    return messages, needs_raycast_confirm
