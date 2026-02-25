#!/usr/bin/env python3
"""Apply sane defaults to the iTerm2 default profile.

Modifies the default profile in ~/Library/Preferences/com.googlecode.iterm2.plist
with a dark color scheme, proper font, and sensible terminal settings.

Usage:
    python3 iterm2-profile-defaults.py [--check]

Exit codes:
    0 - changes applied (or --check found changes needed)
    1 - error
    2 - --check: no changes needed
"""

import plistlib
import subprocess
import sys
from pathlib import Path


def color(r, g, b, a=1.0):
    """Create an iTerm2 color dict from 0-255 RGB values."""
    return {
        "Red Component": r / 255.0,
        "Green Component": g / 255.0,
        "Blue Component": b / 255.0,
        "Alpha Component": float(a),
        "Color Space": "sRGB",
    }


# Catppuccin Mocha palette
COLORS = {
    "Background Color": color(30, 30, 46),
    "Foreground Color": color(205, 214, 244),
    "Bold Color": color(205, 214, 244),
    "Cursor Color": color(245, 224, 220),
    "Cursor Text Color": color(30, 30, 46),
    "Cursor Guide Color": color(69, 71, 90, 0.25),
    "Selection Color": color(69, 71, 90),
    "Selected Text Color": color(205, 214, 244),
    "Badge Color": color(203, 166, 247, 0.5),
    "Link Color": color(137, 180, 250),
    # ANSI colors
    "Ansi 0 Color": color(69, 71, 90),       # Black
    "Ansi 1 Color": color(243, 139, 168),     # Red
    "Ansi 2 Color": color(166, 227, 161),     # Green
    "Ansi 3 Color": color(249, 226, 175),     # Yellow
    "Ansi 4 Color": color(137, 180, 250),     # Blue
    "Ansi 5 Color": color(245, 194, 231),     # Magenta
    "Ansi 6 Color": color(148, 226, 213),     # Cyan
    "Ansi 7 Color": color(186, 194, 222),     # White
    "Ansi 8 Color": color(88, 91, 112),       # Bright Black
    "Ansi 9 Color": color(243, 139, 168),     # Bright Red
    "Ansi 10 Color": color(166, 227, 161),    # Bright Green
    "Ansi 11 Color": color(249, 226, 175),    # Bright Yellow
    "Ansi 12 Color": color(137, 180, 250),    # Bright Blue
    "Ansi 13 Color": color(245, 194, 231),    # Bright Magenta
    "Ansi 14 Color": color(148, 226, 213),    # Bright Cyan
    "Ansi 15 Color": color(166, 173, 200),    # Bright White
}

# Profile settings (non-color)
PROFILE_SETTINGS = {
    "Normal Font": "JetBrainsMonoNF-Regular 13",
    "Non Ascii Font": "JetBrainsMonoNF-Regular 13",
    "Use Non-ASCII Font": False,
    "Columns": 120,
    "Rows": 35,
    "Scrollback Lines": 10000,
    "Option Key Sends": 2,            # Esc+
    "Right Option Key Sends": 0,      # Normal
    "Transparency": 0.0,
    "Blur": False,
    "Minimum Contrast": 0.0,
    "Unicode Version": 9,
    "Terminal Type": "xterm-256color",
    "Mouse Reporting": True,
    "Cursor Type": 1,                 # Vertical bar
    "Flashing Bell": False,
    "Visual Bell": True,
    "BM Growl": False,                # No notification on bell
    "Silence Bell": False,
    "Character Encoding": 4,          # UTF-8
    "Use Bold Font": True,
    "Use Bright Bold": True,
    "Use Italic Font": True,
    "Thin Strokes": 4,                # Retina only
    "ASCII Anti Aliased": True,
    "Non-ASCII Anti Aliased": True,
    "Unlimited Scrollback": False,
    "Send Code When Idle": False,
    "Close Sessions On End": True,
    "Prompt Before Closing 2": 0,     # Don't prompt
}


def read_plist():
    """Read the current iTerm2 plist."""
    result = subprocess.run(
        ["defaults", "export", "com.googlecode.iterm2", "-"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"Error reading iTerm2 plist: {result.stderr.decode()}", file=sys.stderr)
        sys.exit(1)
    return plistlib.loads(result.stdout)


def write_plist(plist):
    """Write the iTerm2 plist back."""
    data = plistlib.dumps(plist, fmt=plistlib.FMT_XML)
    result = subprocess.run(
        ["defaults", "import", "com.googlecode.iterm2", "-"],
        input=data,
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"Error writing iTerm2 plist: {result.stderr.decode()}", file=sys.stderr)
        sys.exit(1)


def color_matches(existing, desired):
    """Check if two color dicts match within tolerance."""
    for key in ("Red Component", "Green Component", "Blue Component", "Alpha Component"):
        if abs(existing.get(key, 0) - desired.get(key, 0)) > 0.01:
            return False
    return True


def needs_changes(profile):
    """Check if the profile needs any changes."""
    # Check colors
    for key, desired in COLORS.items():
        existing = profile.get(key, {})
        if not color_matches(existing, desired):
            return True

    # Check other settings
    for key, desired in PROFILE_SETTINGS.items():
        if profile.get(key) != desired:
            return True

    return False


def apply_defaults(profile):
    """Apply sane defaults to a profile dict."""
    profile.update(COLORS)
    profile.update(PROFILE_SETTINGS)
    return profile


def main():
    check_mode = "--check" in sys.argv

    plist = read_plist()
    profiles = plist.get("New Bookmarks", [])

    if not profiles:
        print("No profiles found in iTerm2 plist", file=sys.stderr)
        sys.exit(1)

    profile = profiles[0]

    if not needs_changes(profile):
        if check_mode:
            sys.exit(2)
        print("No changes needed")
        sys.exit(2)

    if check_mode:
        print("Changes needed")
        sys.exit(0)

    apply_defaults(profile)
    profiles[0] = profile
    plist["New Bookmarks"] = profiles

    write_plist(plist)
    print("Applied sane defaults to iTerm2 default profile")


if __name__ == "__main__":
    main()
