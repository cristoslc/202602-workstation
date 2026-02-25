# Research: Cross-Platform Action Bindings

**Status:** Active
**Started:** 2026-02-25
**Goal:** Define a semantic action layer that maps user-intent actions (take screenshot, open launcher, clipboard history) to per-platform keybindings and implementations, deployed by bootstrap.

---

## Problem Statement

The workstation provisioning system has 35+ roles across macOS and Linux. Keybinding management is currently **app-coupled and platform-scattered**:

- On Linux, three Vicinae shortcuts (launcher, clipboard, emoji) are hardcoded as Cinnamon dconf custom keybindings in `linux/roles/desktop-env/tasks/main.yml`.
- On macOS, equivalent actions (Raycast launcher, clipboard, etc.) are uncaptured — `post-install.md` says "configure manually."
- Screenshot keybindings are unmanaged on both platforms.
- There is no shared vocabulary for "the same action on different OSes using different apps."

The result: when provisioning a new machine, the user must manually recreate keybindings for common actions, and there is no guarantee of cross-platform consistency.

### What Exists Today

| Action | Linux | macOS |
|--------|-------|-------|
| Open launcher | `Super+Space` → Vicinae (dconf) | Unmanaged — Raycast sets its own hotkey |
| Clipboard history | `Super+V` → Vicinae deeplink (dconf) | Unmanaged — Raycast sets its own hotkey |
| Emoji picker | `Super+E` → Vicinae deeplink (dconf) | Unmanaged — macOS default `Ctrl+Cmd+Space` |
| Screenshot (region) | Unmanaged — `post-install.md` says "select a tool" | Unmanaged — `post-install.md` says "configure CleanShot X" |
| Screenshot (full) | Unmanaged | Unmanaged |
| Window management | Unmanaged | Unmanaged |

---

## Desired Architecture

A three-layer model:

```
┌─────────────────────────────────────────────────┐
│  Layer 1: Action Registry (shared vars)         │
│  Semantic actions with per-platform keybindings  │
│  e.g., open_launcher: { linux: Super+Space,     │
│         macos: Hyper+Space }                     │
└───────────────┬─────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
┌───▼───────────────┐  ┌───▼───────────────┐
│ Layer 2: Dispatcher│  │ Layer 2: Dispatcher│
│ Linux: dconf      │  │ macOS: Karabiner + │
│ custom keybindings│  │ Hammerspoon        │
└───────┬───────────┘  └───────┬───────────┘
        │                      │
┌───────▼───────────┐  ┌──────▼────────────┐
│ Layer 3: App      │  │ Layer 3: App      │
│ vicinae, flameshot│  │ Raycast, CleanShot│
│ (replaceable)     │  │ (replaceable)     │
└───────────────────┘  └───────────────────┘
```

Key properties:
- **Actions are the stable abstraction.** Apps come and go (Vicinae could be swapped for Ulauncher; CleanShot X for the macOS screenshot tool). Keybindings should survive app changes.
- **Keybindings are defined once in shared vars.** Each platform reads from the same action registry.
- **Dispatchers are platform-specific.** Linux uses dconf or sxhkd. macOS uses Karabiner-Elements + Hammerspoon.

---

## macOS Dispatcher Options

### Option A: Hammerspoon Only

Hammerspoon binds global hotkeys via `hs.hotkey.bind()` and executes shell commands, opens URLs, or launches apps.

**Config:** `~/.hammerspoon/init.lua` — Lua, fully Stow-able.
**Install:** `brew install --cask hammerspoon`

**Capabilities:**
- Bind arbitrary key combos to shell commands, URL schemes, app launches
- App-specific hotkeys via `hs.application.watcher`
- Can send keystrokes to apps via `hs.eventtap.keyStroke()`
- Auto-reload on config change via `hs.pathwatcher`
- Bidirectional Raycast integration (`open raycast://...` and Raycast extension for Hammerspoon)

**Limitations:**
- `hs.hotkey.bind()` cannot intercept macOS system shortcuts (Cmd+Shift+4, Cmd+Space, etc.) — the OS grabs them first.
- `hs.eventtap` can intercept system shortcuts but with performance risk: if Lua stalls, all keyboard input freezes.
- Requires Accessibility permission (manual grant, cannot be automated).
- macOS only — no Linux equivalent.

### Option B: Karabiner-Elements Only

Karabiner intercepts raw hardware keyboard events via a DriverKit virtual keyboard, transforms them, and replays them. Complex modifications can trigger `shell_command` actions.

**Config:** `~/.config/karabiner/karabiner.json` + `~/.config/karabiner/assets/complex_modifications/*.json` — JSON, fully Stow-able.
**Install:** `brew install --cask karabiner-elements`

**Capabilities:**
- Intercepts at the lowest level — before macOS, before Hammerspoon, before any app
- Can remap any key, including system shortcuts
- `shell_command` can execute arbitrary commands (including `open` for URL schemes)
- `software_function.open_application` can launch/focus apps by bundle ID
- Per-device rules (built-in vs external keyboard)
- JSON config is Ansible-templatable via Jinja2

**Limitations:**
- `shell_command` gets a minimal environment (`$HOME`, `$UID`, `$USER` only) — must use full paths.
- Requires Input Monitoring + Driver Extension + Login Items permissions (all manual).
- macOS upgrades historically break Karabiner until a patch ships (days, not weeks).
- Sequoia blocks native window tiling shortcuts when Karabiner is active.
- GUI modifications strip JSON comments.

### Option C: Karabiner + Hammerspoon (Recommended)

The established "Hyper key" pattern combines both tools:

1. **Karabiner** remaps Caps Lock to `Cmd+Ctrl+Opt+Shift` (the "Hyper" modifier) — or to `F18`/`F19`.
2. **Hammerspoon** listens for Hyper+key combos and dispatches actions.

**Why this is better than either alone:**

| Concern | Karabiner alone | Hammerspoon alone | Both |
|---------|----------------|-------------------|------|
| Intercept system shortcuts | Yes | No (without eventtap risk) | Yes (Karabiner handles) |
| Rich action dispatch | Limited (shell_command) | Full Lua scripting | Full Lua scripting |
| Hyper key creation | Yes | No (can't remap hardware) | Yes (Karabiner creates it) |
| Config format | JSON | Lua | JSON + Lua (both Stow-able) |
| Key conflict avoidance | Good (low-level) | Moderate | Excellent (Hyper namespace is unused) |

**The Hyper key is the critical insight.** By creating a modifier combo that no system or application uses (Cmd+Ctrl+Opt+Shift), we get an entire namespace of hotkeys with zero conflicts. Karabiner is the only tool that can create this mapping because it operates below the OS.

### Option D: Karabiner Only with shell_command

Skip Hammerspoon entirely — have Karabiner's `shell_command` call scripts directly.

**Viable for simple bindings** (launch app, open URL). Falls apart for anything requiring:
- State (e.g., toggle behavior)
- Chained actions (e.g., focus app then send keystroke)
- Conditional logic (e.g., different action based on frontmost app)
- Feedback (e.g., on-screen notification)

**Verdict:** Too limited for the full action registry. Use Karabiner + Hammerspoon.

---

## Linux Dispatcher Options

### Option A: Cinnamon dconf Custom Keybindings (Current Approach)

Already implemented in `linux/roles/desktop-env/tasks/main.yml`. Uses `community.general.dconf` to set `/org/cinnamon/desktop/keybindings/custom-keybindings/`.

**Strengths:**
- Native to the DE — shortcuts appear in Cinnamon Settings GUI
- Single authority — no key grab conflicts
- Already working for 3 Vicinae bindings
- `community.general.dconf` Ansible module handles it idiomatically

**Weaknesses:**
- GVariant syntax is fiddly
- Cinnamon restart needed after CLI changes (can be handled by Ansible handler)
- D-Bus session required (works when user has active desktop session)
- Tied to Cinnamon — must rewrite if switching DEs

### Option B: sxhkd (Simple X Hotkey Daemon)

DE-agnostic X11 hotkey daemon. Config file at `~/.config/sxhkd/sxhkdrc`.

**Strengths:**
- Plain text config — perfect for Stow
- Instant reload via SIGUSR1
- No D-Bus dependency
- Works alongside any DE on X11

**Weaknesses:**
- X11 only — breaks on Wayland
- Must unbind conflicting shortcuts in Cinnamon first
- Shortcuts not visible in Cinnamon Settings GUI
- Extra daemon to manage and autostart

### Option C: swhkd (Wayland-Forward)

Rust rewrite of sxhkd. Works on Wayland, X11, and TTY. Config format is sxhkd-compatible.

**Strengths:**
- Future-proof for Wayland transition
- Config compatible with sxhkd
- Display-server-independent

**Weaknesses:**
- Younger project, less battle-tested
- Requires root (reads from kernel uinput)
- Same GUI visibility issue as sxhkd

### Recommendation for Linux

**Stay with dconf for Cinnamon** (Option A). It is already implemented, native, and the single authority for keybindings. The only change needed is to make it **data-driven** — read action definitions from shared vars instead of hardcoding per-binding tasks.

**Prepare for Wayland** by keeping the action registry platform-agnostic. When Cinnamon Wayland becomes the default (~2026), test whether dconf custom keybindings still work (likely, since dconf is display-server-independent). If not, swhkd is the fallback.

---

## The Hyper Key Pattern (Cross-Platform)

The Hyper key pattern solves the fundamental problem of keybinding conflicts:

### macOS
- **Karabiner** remaps Caps Lock → Hyper (Cmd+Ctrl+Opt+Shift)
- Tapping Caps Lock alone → Escape (via `to_if_alone`)
- Hyper+key combos are dispatched by **Hammerspoon**

### Linux
- Cinnamon (or sxhkd/swhkd) can bind `<Super>` combos directly — Linux doesn't have the same system shortcut collision problem as macOS
- Alternatively, `xmodmap` or `keyd` can remap Caps Lock → Hyper on Linux too
- The action registry can use different modifier names per platform

### Keybinding Namespace

| Modifier | macOS | Linux |
|----------|-------|-------|
| Primary action modifier | Hyper (Caps Lock via Karabiner) | Super |
| With Shift | Hyper+Shift | Super+Shift |

This gives us 26+ letter keys, 10 number keys, and function keys — more than enough for every action.

---

## Proposed Action Registry Format

```yaml
# shared/group_vars/all.yml (or shared/vars/action-bindings.yml)
workstation_actions:
  - action: open_launcher
    description: "Open app launcher / command palette"
    keybinding:
      linux: "<Super>space"
      macos: ["command", "control", "option", "shift", "space"]
    implementation:
      linux:
        type: dconf_custom_keybinding
        command: "vicinae toggle"
      macos:
        type: hammerspoon
        lua: 'hs.execute("open raycast://", true)'

  - action: clipboard_history
    description: "Open clipboard history"
    keybinding:
      linux: "<Super>v"
      macos: ["command", "control", "option", "shift", "v"]
    implementation:
      linux:
        type: dconf_custom_keybinding
        command: "xdg-open vicinae://extensions/vicinae/clipboard/history"
      macos:
        type: hammerspoon
        lua: 'hs.execute("open raycast://extensions/raycast/clipboard-history/clipboard-history", true)'

  - action: emoji_picker
    description: "Open emoji picker"
    keybinding:
      linux: "<Super>e"
      macos: ["command", "control", "option", "shift", "e"]
    implementation:
      linux:
        type: dconf_custom_keybinding
        command: "xdg-open vicinae://extensions/vicinae/emoji"
      macos:
        type: hammerspoon
        lua: 'hs.execute("open raycast://extensions/raycast/emoji-symbols/search-emoji-symbols", true)'

  - action: screenshot_region
    description: "Capture screenshot of selected region"
    keybinding:
      linux: "<Super><Shift>4"
      macos: ["command", "control", "option", "shift", "4"]
    implementation:
      linux:
        type: dconf_custom_keybinding
        command: "flameshot gui"
      macos:
        type: hammerspoon
        lua: 'hs.application.launchOrFocus("CleanShot X")'

  - action: screenshot_full
    description: "Capture full-screen screenshot"
    keybinding:
      linux: "<Super><Shift>3"
      macos: ["command", "control", "option", "shift", "3"]
    implementation:
      linux:
        type: dconf_custom_keybinding
        command: "flameshot full --path ~/Screenshots"
      macos:
        type: hammerspoon
        lua: |
          hs.eventtap.keyStroke({"cmd", "shift"}, "3")
```

### How Ansible Consumes This

**Linux role** (`desktop-env/tasks/debian.yml`):
- Filters `workstation_actions` for entries with `implementation.linux.type == "dconf_custom_keybinding"`
- Loops to generate dconf custom keybinding tasks (replacing current hardcoded tasks)
- Builds the `custom-list` array dynamically

**macOS role** (new `keyboard/tasks/darwin.yml`):
- Generates `~/.hammerspoon/actions.lua` from the registry via Ansible template
- Generates Karabiner complex modification JSON for the Hyper key mapping
- Both files are either Ansible-templated or Stow-managed

---

## Initial Capture Problem

Separate from the action binding architecture, there is the question of how settings get INTO the repo for the first time. The existing sync-app-settings ADR describes a manual workflow. For the tools in this research:

### Karabiner-Elements
- Config at `~/.config/karabiner/` is already XDG-compliant
- After manual configuration, copy the directory into a Stow package
- Or: Ansible-template the JSON from the action registry vars

### Hammerspoon
- Config at `~/.hammerspoon/` — Stow-friendly
- For action bindings, the config is *generated* from the action registry, not captured
- Any additional Hammerspoon modules (window management, etc.) are manually authored Lua files committed to git

### Cinnamon Keybindings
- Already captured as Ansible dconf tasks
- With the action registry, these become data-driven instead of hardcoded

---

## Alternatives Considered

### macOS Shortcuts.app
Apple's automation framework. Can bind keyboard shortcuts to automations.
**Rejected:** Limited scripting capability, hard to export/import programmatically, does not integrate with the Ansible/Stow model.

### BetterTouchTool
Commercial macOS automation tool with extensive hotkey, gesture, and shortcut support.
**Rejected:** Paid license, proprietary config format, overlaps with Karabiner + Hammerspoon.

### sxhkd for Both Platforms (Linux) + Hammerspoon (macOS)
Skip Karabiner, use sxhkd on Linux.
**Rejected for Linux:** sxhkd requires managing key conflicts with Cinnamon. The native dconf approach is simpler and integrated. sxhkd/swhkd is the fallback if Cinnamon Wayland breaks dconf keybindings.

### Single-Tool Approach (Karabiner shell_command for everything)
**Rejected:** Karabiner's shell_command has a minimal environment, no state management, no conditional logic. Hammerspoon is needed for rich action dispatch.

---

## Open Questions

1. **Should window management actions be in the registry?** (e.g., move window left half, maximize, etc.) These are currently unmanaged on both platforms. Hammerspoon has strong window management; Cinnamon has built-in tiling.

2. **Hyper key on Linux — is it needed?** Linux's Super key is already a free modifier namespace (unlike macOS where Cmd is heavily used by the OS). We may not need a Hyper key on Linux at all.

3. **Per-device keybindings?** Karabiner supports per-device rules (built-in vs external keyboard). Should the action registry support this?

4. **How to handle actions that are only on one platform?** (e.g., Cinnamon-specific DE shortcuts, macOS-specific Setapp app triggers)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| macOS upgrade breaks Karabiner | Medium (historically happens) | High (all hotkeys stop) | Pin macOS upgrades; Karabiner patches ship within days |
| Hammerspoon Accessibility permission lost | Low | High (hotkeys stop) | Document re-grant in post-install; Ansible can detect and warn |
| Cinnamon Wayland breaks dconf keybindings | Low (dconf is display-independent) | Medium | swhkd fallback ready |
| Complexity of action registry YAML | Low | Low | Start small — migrate existing 3 Vicinae bindings first |
| Config drift between platforms | Medium | Low | Single source of truth in shared vars; CI could validate |
