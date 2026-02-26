"""Post-install checklist: render HTML and open on the user's Desktop."""

from __future__ import annotations

import logging
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("setup")

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_NAME = "post_install.html.j2"


@dataclass
class ChecklistItem:
    """One manual post-install task."""

    text: str
    platforms: list[str] = field(default_factory=lambda: ["linux", "macos"])


# ── Checklist data (mirrors docs/post-install.md) ─────────────────────────

BOTH_PLATFORMS: list[ChecklistItem] = [
    ChecklistItem(
        "1Password: sign in and enable SSH agent in Settings → Developer"
    ),
    ChecklistItem(
        "1Password browser extension: install in Firefox "
        "(and optionally Brave/Chrome)"
    ),
    ChecklistItem("Firefox: sign in and sync profile"),
    ChecklistItem(
        "Git: verify SSH key works "
        "(<code>ssh -T git@github.com</code> — key served via 1Password agent)"
    ),
    ChecklistItem("Docker Hub: sign in (<code>docker login</code>)"),
    ChecklistItem(
        "Tailscale: sign in "
        "(<code>tailscale up</code> on Linux, or open app on macOS)"
    ),
    ChecklistItem("Surfshark: sign in to the app"),
    ChecklistItem("Slack: sign in to workspaces"),
    ChecklistItem("Signal: verify phone number"),
    ChecklistItem("Spotify: sign in"),
    ChecklistItem(
        "Stream Deck: open app, configure buttons/profiles, "
        "import backup if available"
    ),
]

LINUX_ITEMS: list[ChecklistItem] = [
    ChecklistItem(
        "Cinnamon desktop preferences (wallpaper, panel layout, theme)",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Vicinae: initial setup and configuration",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Verify Espanso is running (<code>espanso status</code>)",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Verify default browser is correct "
        "(<code>xdg-settings get default-web-browser</code>)",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Verify MIME associations: "
        "<code>xdg-mime query default x-scheme-handler/https</code>",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Select a screenshot tool (Flameshot or Shutter) "
        "and add to the <code>screenshots</code> role",
        platforms=["linux"],
    ),
    ChecklistItem(
        "Backblaze is macOS-only; verify Timeshift snapshots are running "
        "(<code>sudo timeshift --list</code>)",
        platforms=["linux"],
    ),
    ChecklistItem(
        "LinNote: launch, set master encryption password, "
        "and configure global hotkey",
        platforms=["linux"],
    ),
    ChecklistItem(
        "NormCap: launch and verify OCR screen capture works",
        platforms=["linux"],
    ),
]

MACOS_ITEMS: list[ChecklistItem] = [
    ChecklistItem(
        "Setapp: sign in and install Setapp-managed apps "
        "(Dato, BusyCal, CleanShot X, Downie, OpenIn, Paletro)",
        platforms=["macos"],
    ),
    ChecklistItem(
        "OpenIn: configure browser routing rules "
        "(work profile → Chrome, personal → Firefox, etc.)",
        platforms=["macos"],
    ),
    ChecklistItem(
        "CleanShot X: configure screenshot shortcuts (replace default ⌘⇧4)",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Dato: configure menu bar calendar display",
        platforms=["macos"],
    ),
    ChecklistItem(
        "BusyCal: sign in to calendar accounts",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Paletro: verify it's accessible via shortcut",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Raycast: set as default launcher, configure clipboard history, "
        "snippets, window management",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Raycast: export settings to <code>macos/dotfiles/raycast/</code> "
        "for future bootstraps",
        platforms=["macos"],
    ),
    ChecklistItem(
        "Sign into Mac App Store (required for <code>mas</code> installs)",
        platforms=["macos"],
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
    ),
    ChecklistItem(
        "Antinote: launch, configure global hotkey (Option+A), "
        "and enable iCloud sync with E2EE if desired",
        platforms=["macos"],
    ),
]


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


def items_for_platform(plat: str) -> dict[str, list[ChecklistItem]]:
    """Return checklist sections filtered for *plat* (``linux`` or ``macos``)."""
    sections: dict[str, list[ChecklistItem]] = {"Both Platforms": BOTH_PLATFORMS}
    if plat == "linux":
        sections["Linux"] = LINUX_ITEMS
    else:
        sections["macOS"] = MACOS_ITEMS
    return sections


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

    sections = items_for_platform(plat)
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
