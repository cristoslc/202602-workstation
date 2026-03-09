"""Editable defaults — action registry keybinding load/save and format conversion.

The action registry lives in shared/roles/keyboard/defaults/main.yml.
macOS Cmd and Linux Super are the same physical key, so the TUI presents
a single canonical binding per action (e.g. "Meta+Shift+V") and derives
both platform formats on save.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from .runner import REPO_ROOT, ToolRunner

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

REGISTRY_PATH = (
    REPO_ROOT / "shared" / "roles" / "keyboard" / "defaults" / "main.yml"
)
ITERM2_PLIST_PATH = (
    REPO_ROOT / "macos" / "dotfiles" / "iterm2" / ".config" / "iterm2"
    / "com.googlecode.iterm2.plist"
)
ITERM2_PLIST_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "iterm2" / "iterm2.plist.age"
)
RAYCAST_CONFIG_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "raycast" / "raycast.rayconfig.age"
)
RAYCAST_IMPORT_TMP = Path.home() / ".cache" / "workstation" / "raycast-import.rayconfig"
STREAMDECK_BACKUP_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "stream-deck" / "streamdeck.backup.age"
)
STREAMDECK_BACKUP_DIR = (
    Path.home() / "Library" / "Application Support"
    / "com.elgato.StreamDeck" / "BackupV3"
)
STREAMDECK_PLUGINS_DIR = (
    Path.home() / "Library" / "Application Support"
    / "com.elgato.StreamDeck" / "Plugins"
)
STREAMDECK_PLUGINS_JSON = (
    REPO_ROOT / "macos" / "files" / "stream-deck" / "plugins.json"
)
STREAMDECK_PLUGINS_HTML = (
    REPO_ROOT / "macos" / "files" / "stream-deck" / "streamdeck-plugins.html"
)
STREAMDECK_PLUGINS_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "stream-deck" / "plugins.json.age"
)
STREAMDECK_IMPORT_TMP = (
    Path.home() / ".cache" / "workstation"
    / "streamdeck-import.streamDeckProfilesBackup"
)
STREAMDECK_PROFILES_DIR = (
    Path.home() / "Library" / "Application Support"
    / "com.elgato.StreamDeck" / "ProfilesV3"
)
OPENIN_APP_PATH = Path("/Applications/Setapp/OpenIn.app")
OPENIN_PLIST_PATH = (
    REPO_ROOT / "macos" / "files" / "openin" / "openin.plist"
)
OPENIN_PLIST_AGE_PATH = (
    REPO_ROOT / "macos" / "files" / "openin" / "openin.plist.age"
)
AGE_KEYS_PATH = Path.home() / ".config" / "sops" / "age" / "keys.txt"
TYPORA_THEMES_REPO_DIR = REPO_ROOT / "shared" / "files" / "typora-themes"
# Bundled themes shipped with Typora — excluded from export.
_TYPORA_BUNDLED_THEMES = {
    "github.css", "newsprint.css", "night.css", "pixyll.css", "whitey.css",
}
_TYPORA_BUNDLED_DIRS = {
    "github", "newsprint", "night", "pixyll", "whitey", "old-themes",
}

# ---------------------------------------------------------------------------
# Export registry — shared by Makefile (export-all) and TUI checklist
# ---------------------------------------------------------------------------
# Each entry declares an export's identity and how to run it.
#   - Non-interactive items have ``export_fn`` (called directly by the TUI worker).
#   - Interactive items have ``make_target`` (TUI suspends and runs ``make <target>``).

IMPORT_ITEMS: list[dict] = [
    {
        "id": "iterm2",
        "label": "iTerm2 preferences",
        "import_fn": "import_iterm2_settings",
        "interactive": False,
    },
    {
        "id": "raycast",
        "label": "Raycast settings",
        "import_fn": "import_raycast_settings",
        "interactive": True,
        "cleanup_fn": "cleanup_raycast_import",
        "confirm_prompt": "Confirm the import in the Raycast dialog",
    },
    {
        "id": "streamdeck",
        "label": "Stream Deck profiles",
        "import_fn": "import_streamdeck_profiles",
        "interactive": False,
    },
    {
        "id": "openin",
        "label": "OpenIn browser rules",
        "import_fn": "import_openin_settings",
        "interactive": False,
    },
]


def get_import_fn(item: dict) -> callable:
    """Resolve an import item's ``import_fn`` string to the actual callable."""
    return globals()[item["import_fn"]]


def get_cleanup_fn(item: dict) -> callable:
    """Resolve an import item's ``cleanup_fn`` string to the actual callable."""
    return globals()[item["cleanup_fn"]]


EXPORT_ITEMS: list[dict] = [
    {
        "id": "iterm2",
        "label": "iTerm2 preferences",
        "interactive": False,
        "export_fn": "export_iterm2_plist",
    },
    {
        "id": "streamdeck",
        "label": "Stream Deck profiles",
        "interactive": False,
        "export_fn": "export_streamdeck_profiles",
    },
    {
        "id": "raycast",
        "label": "Raycast settings",
        "interactive": True,
        "make_target": "export-raycast",
    },
    {
        "id": "openin",
        "label": "OpenIn browser rules",
        "interactive": False,
        "export_fn": "export_openin_settings",
    },
    {
        "id": "typora-themes",
        "label": "Typora themes",
        "interactive": False,
        "export_fn": "export_typora_themes",
    },
]


def get_export_fn(item: dict) -> callable:
    """Resolve an export item's ``export_fn`` string to the actual callable."""
    return globals()[item["export_fn"]]


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

# ---------------------------------------------------------------------------
# Modifier / key normalization — fix hand-edited or TUI-entered macOS-isms
# ---------------------------------------------------------------------------

# Canonical Linux dconf modifier names (title-case, inside angle brackets)
_NORMALIZE_LINUX_MOD = {
    "super": "Super", "meta": "Super", "cmd": "Super", "command": "Super", "win": "Super",
    "shift": "Shift",
    "ctrl": "Ctrl", "control": "Ctrl",
    "alt": "Alt", "opt": "Alt", "option": "Alt",
}

# Canonical macOS Hammerspoon modifier names (lowercase)
_NORMALIZE_MACOS_MOD = {
    "cmd": "cmd", "command": "cmd", "meta": "cmd", "super": "cmd", "win": "cmd",
    "shift": "shift",
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "opt": "alt", "option": "alt",
}

# Punctuation key names for Linux dconf (bare char → X11 keysym)
_NORMALIZE_LINUX_KEY = {
    ".": "period", ",": "comma", ";": "semicolon", "'": "apostrophe",
    "/": "slash", "\\": "backslash", "[": "bracketleft", "]": "bracketright",
    "-": "minus", "=": "equal", "`": "grave",
}


def _normalize_keybinding(kb: dict) -> None:
    """Normalize modifier and key names in a keybinding dict, in place.

    Fixes common macOS-isms (Opt → Alt, Command → Super/cmd, etc.) and
    converts bare punctuation chars to X11 keysym names for Linux dconf.

    Raises ``ValueError`` for unrecognised modifier names.
    """
    # --- Linux string: "<Ctrl><Opt>Left" → "<Ctrl><Alt>Left" ---
    linux = kb.get("linux")
    if isinstance(linux, str):
        mods, key = _parse_linux_binding(linux)
        normed_mods = []
        for m in mods:
            canon = _NORMALIZE_LINUX_MOD.get(m.lower())
            if canon is None:
                raise ValueError(f"Unknown Linux modifier: {m!r}")
            normed_mods.append(canon)
        key = _NORMALIZE_LINUX_KEY.get(key, key)
        kb["linux"] = "".join(f"<{m}>" for m in normed_mods) + key

    # --- macOS dict: {mods: ["opt"], key: "v"} → {mods: ["alt"], key: "v"} ---
    macos = kb.get("macos")
    if isinstance(macos, dict):
        normed_mods = []
        for m in macos.get("mods", []):
            canon = _NORMALIZE_MACOS_MOD.get(m.lower())
            if canon is None:
                raise ValueError(f"Unknown macOS modifier: {m!r}")
            normed_mods.append(canon)
        macos["mods"] = normed_mods


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

    # Normalize modifier / key names so hand-edited macOS-isms don't
    # silently break dconf or Hammerspoon at runtime.
    for action in actions:
        kb = action.get("keybinding")
        if kb:
            _normalize_keybinding(kb)

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


def _age_pubkey() -> str:
    """Extract the age public key from ``.sops.yaml``."""
    sops_yaml = REPO_ROOT / ".sops.yaml"
    with open(sops_yaml) as f:
        for line in f:
            m = re.search(r"(age1[a-z0-9]+)", line)
            if m:
                return m.group(1)
    raise RuntimeError("Could not find age public key in .sops.yaml")


def export_iterm2_plist(runner: ToolRunner) -> str:
    """Export iTerm2 preferences plist and age-encrypt for the repo.

    Writes the plaintext plist to the stow package (for local use) and
    an age-encrypted copy to ``macos/files/iterm2/`` (for the repo).
    """
    result = runner.run(
        ["make", "export-iterm2"],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        msg = details or "make export-iterm2 failed"
        raise RuntimeError(msg)

    # Age-encrypt for the repo (plaintext stays locally, gitignored)
    pubkey = _age_pubkey()
    ITERM2_PLIST_AGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-r", pubkey,
            "-o", str(ITERM2_PLIST_AGE_PATH),
            str(ITERM2_PLIST_PATH),
        ],
        check=True,
    )
    return f"iTerm2 settings exported and encrypted to {ITERM2_PLIST_AGE_PATH}"


def export_openin_settings(runner: ToolRunner) -> str:
    """Export OpenIn preferences plist and age-encrypt for the repo.

    Writes the plaintext plist to ``macos/files/openin/`` (gitignored) and
    an age-encrypted copy alongside it (for the repo).
    """
    result = runner.run(
        ["make", "export-openin"],
        cwd=REPO_ROOT,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "").strip()
        msg = details or "make export-openin failed"
        raise RuntimeError(msg)

    # Age-encrypt for the repo (plaintext stays locally, gitignored)
    pubkey = _age_pubkey()
    OPENIN_PLIST_AGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-r", pubkey,
            "-o", str(OPENIN_PLIST_AGE_PATH),
            str(OPENIN_PLIST_PATH),
        ],
        check=True,
    )
    return f"OpenIn settings exported and encrypted to {OPENIN_PLIST_AGE_PATH}"


# ---------------------------------------------------------------------------
# Import functions — mirror Ansible tasks for standalone re-import
# ---------------------------------------------------------------------------


def _typora_themes_dir() -> Path:
    """Return the platform-specific Typora user themes directory."""
    import platform as _plat

    if _plat.system() == "Darwin":
        return (
            Path.home() / "Library" / "Application Support"
            / "abnerworks.Typora" / "themes"
        )
    return Path.home() / ".config" / "Typora" / "themes"


def export_typora_themes(runner: ToolRunner) -> str:
    """Copy non-bundled Typora themes from the local install into the repo."""
    src = _typora_themes_dir()
    if not src.is_dir():
        raise RuntimeError(f"Typora themes directory not found: {src}")

    TYPORA_THEMES_REPO_DIR.mkdir(parents=True, exist_ok=True)
    count = 0

    # Copy CSS files (excluding bundled)
    for css in sorted(src.glob("*.css")):
        if css.name in _TYPORA_BUNDLED_THEMES:
            continue
        shutil.copy2(css, TYPORA_THEMES_REPO_DIR / css.name)
        count += 1

    # Copy theme asset directories (excluding bundled)
    for d in sorted(src.iterdir()):
        if not d.is_dir() or d.name in _TYPORA_BUNDLED_DIRS:
            continue
        dest = TYPORA_THEMES_REPO_DIR / d.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(d, dest)
        count += 1

    return f"Typora themes exported ({count} items) to {TYPORA_THEMES_REPO_DIR}"


def import_iterm2_settings(runner: ToolRunner) -> str:
    """Decrypt plist and point iTerm2 at the stow-managed copy.

    If an age-encrypted plist exists in the repo, decrypt it to the stow
    source directory so stow can symlink it.  Then run two ``defaults write``
    commands to tell iTerm2 to use the custom folder.
    """
    if ITERM2_PLIST_AGE_PATH.exists():
        ITERM2_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        runner.run(
            [
                "age", "-d",
                "-i", str(AGE_KEYS_PATH),
                "-o", str(ITERM2_PLIST_PATH),
                str(ITERM2_PLIST_AGE_PATH),
            ],
            check=True,
        )
    # Stow the iterm2 package so the plist is symlinked into ~/.config/iterm2
    stow_dir = REPO_ROOT / "macos" / "dotfiles"
    runner.run(
        ["stow", "--no-folding", "--restow", "-d", str(stow_dir), "-t",
         str(Path.home()), "iterm2"],
        check=True,
    )
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


def import_openin_settings(runner: ToolRunner) -> str:
    """Decrypt OpenIn plist and load it via ``defaults import``.

    Reads the bundle identifier from the installed app so the import
    targets the correct domain even if the vendor changes it between
    versions.
    """
    if not OPENIN_PLIST_AGE_PATH.exists():
        return (
            "No OpenIn export found — skipping import. "
            "Configure manually, then run: make export-openin"
        )
    if not OPENIN_APP_PATH.exists():
        return (
            "OpenIn is not installed — skipping import. "
            "Install via Setapp first, then run: make export-openin"
        )
    # Resolve the real bundle identifier from the installed app.
    bundle_id_result = runner.run(
        [
            "/usr/libexec/PlistBuddy", "-c", "Print :CFBundleIdentifier",
            str(OPENIN_APP_PATH / "Contents" / "Info.plist"),
        ],
        check=True,
    )
    bundle_id = bundle_id_result.stdout.strip()

    OPENIN_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-d",
            "-i", str(AGE_KEYS_PATH),
            "-o", str(OPENIN_PLIST_PATH),
            str(OPENIN_PLIST_AGE_PATH),
        ],
        check=True,
    )
    runner.run(
        ["defaults", "import", bundle_id, str(OPENIN_PLIST_PATH)],
        check=True,
    )
    return f"OpenIn settings imported (domain: {bundle_id})"


def import_raycast_settings(runner: ToolRunner) -> tuple[str, bool]:
    """Decrypt and open Raycast settings for import.

    Returns ``(message, needs_confirm)`` — when *needs_confirm* is True the
    caller should pause for the user to confirm the Raycast import dialog,
    then call :func:`cleanup_raycast_import`.
    """
    if not RAYCAST_CONFIG_AGE_PATH.exists():
        return (
            "No Raycast export found — skipping import. "
            "Configure manually, then run: make export-raycast",
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


_STREAMDECK_BUILTIN_PREFIXES = (
    "com.elgato.streamdeck.system.",
    "com.elgato.streamdeck.profile.",
)


def scan_streamdeck_plugins(
    plugins_dir: Path | None = None,
) -> list[dict]:
    """Scan installed Stream Deck plugins and return metadata dicts.

    Each dict has keys: ``name``, ``uuid``, ``url``, ``version``.
    """
    target = plugins_dir or STREAMDECK_PLUGINS_DIR
    if not target.is_dir():
        return []

    plugins: list[dict] = []
    for sd_dir in sorted(target.glob("*.sdPlugin")):
        manifest = sd_dir / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            continue
        uuid = data.get("UUID", sd_dir.stem)
        url = data.get("URL", "").strip()
        if not url:
            url = f"https://marketplace.elgato.com/stream-deck/plugins?search={uuid}"
        plugins.append({
            "name": data.get("Name", sd_dir.stem),
            "uuid": uuid,
            "url": url,
            "version": data.get("Version", "unknown"),
        })
    return plugins


def scan_streamdeck_backup_plugins(backup_path: Path) -> list[dict]:
    """Extract plugin UUIDs referenced in a Stream Deck backup zip.

    Returns minimal plugin dicts (name derived from UUID, no version/URL)
    for plugins that are referenced in profile JSON files.  Built-in
    system actions (hotkey, multimedia, open-app, profile navigation)
    are excluded.
    """
    if not backup_path.is_file():
        return []

    plugins_map: dict[str, dict] = {}
    with zipfile.ZipFile(str(backup_path), "r") as zf:
        for member in zf.infolist():
            if not member.filename.endswith(".json"):
                continue
            try:
                data = zf.read(member.filename).decode("utf-8", errors="replace")
            except OSError:
                continue
            for match in re.findall(
                r'"(?:UUID|Plugin)"\s*:\s*"([^"]+)"', data
            ):
                if "." not in match:
                    continue
                if any(match.startswith(p) for p in _STREAMDECK_BUILTIN_PREFIXES):
                    continue
                # Normalize to base UUID — strip action suffixes like
                # .toggle, .action, .history, etc.  Heuristic: keep first
                # 3 dotted segments for 4+ segment UUIDs.
                parts = match.split(".")
                base = ".".join(parts[:3]) if len(parts) > 3 else match
                if base not in plugins_map:
                    # Derive a human-readable name from the last segment
                    short = base.rsplit(".", 1)[-1]
                    name = short.replace("-", " ").replace("_", " ").title()
                    plugins_map[base] = {
                        "name": name,
                        "uuid": base,
                        "url": f"https://marketplace.elgato.com/product/{base}",
                        "version": "unknown",
                    }
    return sorted(plugins_map.values(), key=lambda p: p["name"])


def _merge_plugin_lists(*sources: list[dict]) -> list[dict]:
    """Union multiple plugin lists, preferring entries with richer metadata.

    When the same UUID appears in multiple sources, the entry with more
    complete data (real URL, version, name) wins.  This lets installed-
    plugin scans (which read manifest.json) take precedence over
    backup-extracted entries (which only have the UUID).
    """
    merged: dict[str, dict] = {}
    for plugins in sources:
        for p in plugins:
            uuid = p["uuid"]
            existing = merged.get(uuid)
            if existing is None:
                merged[uuid] = dict(p)
                continue
            # Prefer entry with a real version over "unknown"
            if existing.get("version") == "unknown" and p.get("version") != "unknown":
                merged[uuid] = dict(p)
            # Prefer entry whose URL doesn't look auto-generated
            elif (
                "?search=" in existing["url"]
                and "?search=" not in p["url"]
            ):
                merged[uuid] = dict(p)
    return sorted(merged.values(), key=lambda p: p["name"])


def export_streamdeck_plugin_list(
    plugins_dir: Path | None = None,
    json_path: Path | None = None,
    html_path: Path | None = None,
    templates_dir: Path | None = None,
    backup_path: Path | None = None,
) -> str:
    """Scan plugins and write ``plugins.json`` + ``streamdeck-plugins.html``.

    Unions plugins found from installed manifests and from the backup
    archive so that the exported list is complete even when some plugins
    are only referenced in profiles.
    """
    installed = scan_streamdeck_plugins(plugins_dir)
    backup_plugins: list[dict] = []
    if backup_path is None:
        # Try to find the newest backup automatically
        if STREAMDECK_BACKUP_DIR.is_dir():
            backups = sorted(
                STREAMDECK_BACKUP_DIR.glob("*.streamDeckProfilesBackup"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if backups:
                backup_path = backups[0]
    if backup_path is not None:
        backup_plugins = scan_streamdeck_backup_plugins(backup_path)

    plugins = _merge_plugin_lists(installed, backup_plugins)

    out_json = json_path or STREAMDECK_PLUGINS_JSON
    out_html = html_path or STREAMDECK_PLUGINS_HTML
    tpl_dir = templates_dir or TEMPLATES_DIR

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(plugins, indent=2) + "\n")

    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=True,
    )
    template = env.get_template("streamdeck_plugins.html.j2")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = template.render(plugins=plugins, timestamp=now)
    out_html.write_text(html)

    return f"Plugin list exported ({len(plugins)} plugins)"


def export_streamdeck_profiles(runner: ToolRunner) -> str:
    """Export the newest Stream Deck backup, age-encrypted, into the repo.

    Looks in ``BackupV3/`` for the most recent ``.streamDeckProfilesBackup``
    file and encrypts it with the age public key from ``.sops.yaml``.
    Also exports and encrypts the installed plugin list.
    """
    if not STREAMDECK_BACKUP_DIR.is_dir():
        raise RuntimeError(
            f"Stream Deck backup directory not found: {STREAMDECK_BACKUP_DIR}"
        )

    backups = sorted(
        STREAMDECK_BACKUP_DIR.glob("*.streamDeckProfilesBackup"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        raise RuntimeError(
            "No .streamDeckProfilesBackup files found in BackupV3/"
        )

    newest = backups[0]
    pubkey = _age_pubkey()

    STREAMDECK_BACKUP_AGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-r", pubkey,
            "-o", str(STREAMDECK_BACKUP_AGE_PATH),
            str(newest),
        ],
        check=True,
    )
    msg = f"Stream Deck profiles exported from {newest.name}"

    # Also export + encrypt plugin list (best-effort)
    try:
        plugin_msg = export_streamdeck_plugin_list(backup_path=newest)
        runner.run(
            [
                "age", "-r", pubkey,
                "-o", str(STREAMDECK_PLUGINS_AGE_PATH),
                str(STREAMDECK_PLUGINS_JSON),
            ],
            check=True,
        )
        msg = f"{msg}\n{plugin_msg}"
    except Exception:
        pass

    return msg


def import_streamdeck_profiles(runner: ToolRunner) -> tuple[str, bool]:
    """Decrypt and restore Stream Deck profiles without GUI interaction.

    Extracts the backup zip's ``Profiles/`` directory directly into the
    Stream Deck ``ProfilesV3/`` folder, restarting the app if running.
    """
    if not STREAMDECK_BACKUP_AGE_PATH.exists():
        return (
            "No Stream Deck export found — skipping import. "
            "Configure manually, then run: make export-streamdeck",
            False,
        )
    STREAMDECK_IMPORT_TMP.parent.mkdir(parents=True, exist_ok=True)
    runner.run(
        [
            "age", "-d",
            "-i", str(AGE_KEYS_PATH),
            "-o", str(STREAMDECK_IMPORT_TMP),
            str(STREAMDECK_BACKUP_AGE_PATH),
        ],
        check=True,
    )
    # Quit Stream Deck if running so we can overwrite profiles safely
    subprocess.run(
        ["osascript", "-e", 'tell application "Elgato Stream Deck" to quit'],
        capture_output=True,
    )
    # Extract Profiles/ from backup zip into ProfilesV3/
    STREAMDECK_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(STREAMDECK_IMPORT_TMP), "r") as zf:
        for member in zf.infolist():
            if not member.filename.startswith("Profiles/"):
                continue
            # Strip "Profiles/" prefix to get the relative path
            rel = member.filename[len("Profiles/"):]
            if not rel:
                continue
            dest = STREAMDECK_PROFILES_DIR / rel
            if member.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(zf.read(member.filename))
    # Scan the backup for referenced plugins before cleaning up
    backup_plugins = scan_streamdeck_backup_plugins(STREAMDECK_IMPORT_TMP)
    # Clean up temp file
    STREAMDECK_IMPORT_TMP.unlink(missing_ok=True)
    # Restart Stream Deck
    subprocess.run(
        ["open", "-a", "Elgato Stream Deck"],
        capture_output=True,
    )
    # Build plugin list from backup + encrypted plugin list, then render HTML
    try:
        sources: list[list[dict]] = [backup_plugins]
        # Also load the pre-exported plugin list if available (has richer
        # metadata like real marketplace URLs and versions)
        if STREAMDECK_PLUGINS_AGE_PATH.exists():
            runner.run(
                [
                    "age", "-d",
                    "-i", str(AGE_KEYS_PATH),
                    "-o", str(STREAMDECK_PLUGINS_JSON),
                    str(STREAMDECK_PLUGINS_AGE_PATH),
                ],
                check=True,
            )
            sources.append(
                json.loads(STREAMDECK_PLUGINS_JSON.read_text())
            )
        # Union installed plugins too (may already have some on this machine)
        sources.append(scan_streamdeck_plugins())
        plugins = _merge_plugin_lists(*sources)
        if plugins:
            STREAMDECK_PLUGINS_JSON.parent.mkdir(parents=True, exist_ok=True)
            STREAMDECK_PLUGINS_JSON.write_text(
                json.dumps(plugins, indent=2) + "\n"
            )
            env = Environment(
                loader=FileSystemLoader(str(TEMPLATES_DIR)),
                autoescape=True,
            )
            template = env.get_template("streamdeck_plugins.html.j2")
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            STREAMDECK_PLUGINS_HTML.write_text(
                template.render(plugins=plugins, timestamp=now)
            )
            runner.run(
                ["open", str(STREAMDECK_PLUGINS_HTML)], check=False
            )
    except Exception:
        pass  # Plugin list is nice-to-have, don't fail restore
    return "Stream Deck profiles restored (headless)", False


def cleanup_streamdeck_import() -> None:
    """No-op — headless restore cleans up inline."""


def run_all_imports(
    runner: ToolRunner,
) -> tuple[list[str], list[tuple[str, callable]]]:
    """Orchestrate all settings imports.

    Returns ``(messages, confirmations)`` where *confirmations* is a list of
    ``(prompt, cleanup_fn)`` tuples for imports that need interactive user
    confirmation (e.g. Raycast import dialog, Stream Deck restore dialog).
    """
    messages: list[str] = []
    confirmations: list[tuple[str, callable]] = []

    # iTerm2
    try:
        msg = import_iterm2_settings(runner)
        messages.append(msg)
    except Exception as exc:
        messages.append(f"iTerm2 import failed: {exc}")

    # OpenIn
    try:
        msg = import_openin_settings(runner)
        messages.append(msg)
    except Exception as exc:
        messages.append(f"OpenIn import failed: {exc}")

    # Raycast
    try:
        msg, needs_confirm = import_raycast_settings(runner)
        messages.append(msg)
        if needs_confirm:
            confirmations.append((
                "Confirm the import in the Raycast dialog",
                cleanup_raycast_import,
            ))
    except Exception as exc:
        messages.append(f"Raycast import failed: {exc}")

    # Stream Deck
    try:
        msg, needs_confirm = import_streamdeck_profiles(runner)
        messages.append(msg)
        if needs_confirm:
            confirmations.append((
                "Confirm the restore in the Stream Deck app",
                cleanup_streamdeck_import,
            ))
    except Exception as exc:
        messages.append(f"Stream Deck import failed: {exc}")

    return messages, confirmations
