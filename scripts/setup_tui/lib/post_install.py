"""Post-install checklist: render HTML and open on the user's Desktop."""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("setup")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_NAME = "post_install.html.j2"
VERIFY_REGISTRY = Path(__file__).resolve().parent.parent.parent / "verify-registry.yml"


@dataclass
class ChecklistItem:
    """One manual post-install task."""

    text: str
    platforms: list[str] = field(default_factory=lambda: ["linux", "macos"])
    phase: str = ""
    tags: list[str] = field(default_factory=list)


# ── Checklist data (mirrors docs/post-install.md) ─────────────────────────

BOTH_PLATFORMS: list[ChecklistItem] = [
    ChecklistItem(
        "1Password: sign in and enable SSH agent in Settings → Developer",
        phase="security",
        tags=["onepassword"],
    ),
    ChecklistItem(
        "1Password browser extension: install in Firefox "
        "(and optionally Brave/Chrome)",
        phase="security",
        tags=["onepassword"],
    ),
    ChecklistItem(
        "Firefox: sign in and sync profile",
        phase="desktop",
        tags=["firefox"],
    ),
    ChecklistItem(
        "Git: verify SSH key works "
        "(<code>ssh -T git@github.com</code> — key served via 1Password agent)",
        phase="dev-tools",
        tags=["git"],
    ),
    ChecklistItem(
        "Docker Hub: sign in (<code>docker login</code>)",
        phase="dev-tools",
        tags=["docker"],
    ),
    ChecklistItem(
        "Tailscale: sign in "
        "(<code>tailscale up</code> on Linux, or open app on macOS)",
        phase="desktop",
        tags=["tailscale"],
    ),
    ChecklistItem(
        "Surfshark: sign in to the app",
        phase="desktop",
        tags=["surfshark"],
    ),
    ChecklistItem(
        "Slack: sign in to workspaces",
        phase="desktop",
        tags=["slack"],
    ),
    ChecklistItem(
        "Signal: verify phone number",
        phase="desktop",
        tags=["signal"],
    ),
    ChecklistItem(
        "Spotify: sign in",
        phase="desktop",
        tags=["spotify"],
    ),
    ChecklistItem(
        "Stream Deck: open app, configure buttons/profiles, "
        "import backup if available",
        phase="desktop",
        tags=["stream-deck"],
    ),
]

LINUX_ITEMS: list[ChecklistItem] = [
    ChecklistItem(
        "Cinnamon desktop preferences (wallpaper, panel layout, theme)",
        platforms=["linux"],
        phase="desktop",
        tags=["desktop-env"],
    ),
    ChecklistItem(
        "Vicinae: initial setup and configuration",
        platforms=["linux"],
        phase="desktop",
        tags=["vicinae"],
    ),
    ChecklistItem(
        "Verify Espanso is running (<code>espanso status</code>)",
        platforms=["linux"],
        phase="desktop",
        tags=["espanso"],
    ),
    ChecklistItem(
        "Verify default browser is correct "
        "(<code>xdg-settings get default-web-browser</code>)",
        platforms=["linux"],
        phase="desktop",
        tags=["browsers"],
    ),
    ChecklistItem(
        "Verify MIME associations: "
        "<code>xdg-mime query default x-scheme-handler/https</code>",
        platforms=["linux"],
        phase="desktop",
        tags=["link-handler"],
    ),
    ChecklistItem(
        "Select a screenshot tool (Flameshot or Shutter) "
        "and add to the <code>screenshots</code> role",
        platforms=["linux"],
        phase="desktop",
        tags=["screenshots"],
    ),
    ChecklistItem(
        "Backblaze is macOS-only; verify Timeshift snapshots are running "
        "(<code>sudo timeshift --list</code>)",
        platforms=["linux"],
        phase="desktop",
        tags=["timeshift"],
    ),
    ChecklistItem(
        "LinNote: launch, set master encryption password, "
        "and configure global hotkey",
        platforms=["linux"],
        phase="desktop",
        tags=["linnote"],
    ),
    ChecklistItem(
        "NormCap: launch and verify OCR screen capture works",
        platforms=["linux"],
        phase="desktop",
        tags=["normcap"],
    ),
]

# macOS items excluding Setapp — the Setapp item is built dynamically
# from verify-registry.yml at render time.
_MACOS_ITEMS_STATIC: list[ChecklistItem] = [
    ChecklistItem(
        "OpenIn: configure browser routing rules "
        "(work profile → Chrome, personal → Firefox, etc.)",
        platforms=["macos"],
        phase="desktop",
        tags=["openin"],
    ),
    ChecklistItem(
        "CleanShot X: configure screenshot shortcuts (replace default ⌘⇧4)",
        platforms=["macos"],
        phase="desktop",
        tags=["cleanshot"],
    ),
    ChecklistItem(
        "Dato: configure menu bar calendar display",
        platforms=["macos"],
        phase="desktop",
        tags=["dato"],
    ),
    ChecklistItem(
        "BusyCal: sign in to calendar accounts",
        platforms=["macos"],
        phase="desktop",
        tags=["busycal"],
    ),
    ChecklistItem(
        "Paletro: verify it's accessible via shortcut",
        platforms=["macos"],
        phase="desktop",
        tags=["paletro"],
    ),
    ChecklistItem(
        "Raycast: set as default launcher, configure clipboard history, "
        "snippets, window management",
        platforms=["macos"],
        phase="desktop",
        tags=["raycast"],
    ),
    ChecklistItem(
        "Raycast: export settings to <code>macos/dotfiles/raycast/</code> "
        "for future bootstraps",
        platforms=["macos"],
        phase="desktop",
        tags=["raycast"],
    ),
    ChecklistItem(
        "Sign into Mac App Store (required for <code>mas</code> installs)",
        platforms=["macos"],
        phase="desktop",
        tags=["mas"],
    ),
    ChecklistItem(
        "iCloud sign-in (if applicable)",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Backblaze: sign in and configure backup",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Set default browser in System Settings → Default web browser",
        platforms=["macos"],
        phase="desktop",
        tags=["browsers"],
    ),
    ChecklistItem(
        "Antinote: launch, configure global hotkey (Option+A), "
        "and enable iCloud sync with E2EE if desired",
        platforms=["macos"],
        phase="desktop",
        tags=["antinote"],
    ),
]


def _load_registry() -> dict:
    """Load and cache the verify-registry.yml data."""
    try:
        return yaml.safe_load(VERIFY_REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Could not read verify-registry.yml")
        return {}


def _setapp_apps(
    phases: list[str],
    skip_tags: list[str],
) -> list[str]:
    """Return names of Setapp-managed apps filtered by user selections."""
    data = _load_registry()
    names: list[str] = []
    for role_info in data.get("roles", {}).values():
        if not any(
            app.get("note", "").startswith("Install via Setapp")
            for app in role_info.get("apps", [])
        ):
            continue
        role_phase = role_info.get("phase", "")
        for app in role_info.get("apps", []):
            if not app.get("note", "").startswith("Install via Setapp"):
                continue
            if phases and role_phase and role_phase not in phases:
                continue
            app_tags = app.get("tags", [])
            if skip_tags and any(t in skip_tags for t in app_tags):
                continue
            names.append(app["name"])
    return sorted(set(names))


def _filter_items(
    items: list[ChecklistItem],
    phases: list[str],
    skip_tags: list[str],
) -> list[ChecklistItem]:
    """Return only the items whose phase/tags match user selections."""
    filtered: list[ChecklistItem] = []
    for item in items:
        if phases and item.phase and item.phase not in phases:
            continue
        if skip_tags and any(t in skip_tags for t in item.tags):
            continue
        filtered.append(item)
    return filtered


def items_for_platform(
    plat: str,
    phases: list[str] | None = None,
    skip_tags: list[str] | None = None,
) -> dict[str, list[ChecklistItem]]:
    """Return checklist sections filtered for *plat* and user selections."""
    ph = phases or []
    st = skip_tags or []

    sections: dict[str, list[ChecklistItem]] = {
        "Both Platforms": _filter_items(BOTH_PLATFORMS, ph, st),
    }
    if plat == "linux":
        sections["Linux"] = _filter_items(LINUX_ITEMS, ph, st)
    else:
        # Build the Setapp item dynamically from the registry.
        setapp_names = _setapp_apps(ph, st)
        macos_items: list[ChecklistItem] = []
        if setapp_names:
            macos_items.append(
                ChecklistItem(
                    f"Setapp: sign in and install Setapp-managed apps "
                    f"({', '.join(setapp_names)})",
                    platforms=["macos"],
                    phase="desktop",
                )
            )
        macos_items.extend(_filter_items(_MACOS_ITEMS_STATIC, ph, st))
        sections["macOS"] = macos_items

    # Drop empty sections (except Both Platforms — always show header).
    return {k: v for k, v in sections.items() if v or k == "Both Platforms"}


def _desktop_path() -> Path:
    """Return the user's Desktop directory."""
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DESKTOP"],
                capture_output=True,
                text=True,
                check=True,
            )
            return Path(result.stdout.strip())
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
    return Path.home() / "Desktop"


def render_html(
    *,
    plat: str,
    phases: list[str],
    skip_tags: list[str],
    log_path: str,
    templates_dir: Path | None = None,
) -> str:
    """Render the post-install checklist HTML from a Jinja template."""
    tpl_dir = templates_dir or TEMPLATES_DIR
    env = Environment(
        loader=FileSystemLoader(str(tpl_dir)),
        autoescape=True,
    )
    template = env.get_template(TEMPLATE_NAME)

    sections = items_for_platform(plat, phases, skip_tags)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return template.render(
        platform=plat,
        platform_label="Linux" if plat == "linux" else "macOS",
        timestamp=now,
        phases=phases,
        skip_tags=skip_tags,
        log_path=log_path,
        sections=sections,
    )


def generate_and_open(
    *,
    plat: str,
    phases: list[str],
    skip_tags: list[str],
    log_path: str,
) -> Path:
    """Write checklist HTML to Desktop and return the path (caller opens)."""
    html = render_html(
        plat=plat,
        phases=phases,
        skip_tags=skip_tags,
        log_path=log_path,
    )
    desktop = _desktop_path()
    desktop.mkdir(parents=True, exist_ok=True)
    doc_path = desktop / "post-install-checklist.html"
    doc_path.write_text(html, encoding="utf-8")
    logger.info("Post-install checklist written to %s", doc_path)
    return doc_path


def open_file(path: Path) -> None:
    """Open *path* with the platform-native viewer (non-blocking)."""
    opener = "open" if platform.system() == "Darwin" else "xdg-open"
    try:
        subprocess.Popen(
            [opener, str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.warning("Could not open %s: %s not found", path, opener)
