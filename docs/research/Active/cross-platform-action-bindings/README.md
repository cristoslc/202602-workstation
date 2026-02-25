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
│         macos: Ctrl+Opt+Space }                  │
└───────────────┬─────────────────────────────────┘
                │
    ┌───────────┴───────────┐
    │                       │
┌───▼───────────────┐  ┌───▼───────────────┐
│ Layer 2: Dispatcher│  │ Layer 2: Dispatcher│
│ Linux: dconf      │  │ macOS:            │
│ custom keybindings│  │ Hammerspoon       │
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
- **Dispatchers are platform-specific.** Linux uses dconf. macOS uses Hammerspoon.

---

## macOS Dispatcher Options

### Option A: Hammerspoon Only (Recommended)

Hammerspoon binds global hotkeys via `hs.hotkey.bind()` and executes shell commands, opens URLs, or launches apps.

**Config:** `~/.hammerspoon/init.lua` — Lua, fully Stow-able.
**Install:** `brew install --cask hammerspoon`

**Capabilities:**
- Bind arbitrary key combos to shell commands, URL schemes, app launches
- App-specific hotkeys via `hs.application.watcher`
- Can send keystrokes to apps via `hs.eventtap.keyStroke()`
- Built-in window management via `hs.window` (move, resize, tile, multi-monitor)
- Auto-reload on config change via `hs.pathwatcher`
- Bidirectional Raycast integration (`open raycast://...` and Raycast extension for Hammerspoon)

**Limitations:**
- `hs.hotkey.bind()` cannot intercept macOS system shortcuts (Cmd+Shift+4, Cmd+Space, etc.) — the OS grabs them first.
- `hs.eventtap` can intercept system shortcuts but with performance risk: if Lua stalls, all keyboard input freezes.
- Requires Accessibility permission (manual grant, cannot be automated).
- macOS only — no Linux equivalent.

**Why this is sufficient without Karabiner:** By choosing `Ctrl+Opt` as our action modifier namespace, we avoid all macOS system shortcut conflicts. macOS reserves `Cmd+key` (app shortcuts), `Cmd+Shift+key` (extended app shortcuts), `Cmd+Opt+key` (some system functions), and `Ctrl+key` (some Spaces/Mission Control). But `Ctrl+Opt+key` is essentially unused by macOS and applications. Hammerspoon's `hs.hotkey.bind({"ctrl", "alt"}, ...)` grabs these cleanly without needing Karabiner's low-level interception.

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
- Requires Input Monitoring + Driver Extension + Login Items permissions (all manual — three permission dialogs vs one for Hammerspoon).
- macOS upgrades historically break Karabiner until a patch ships (days, not weeks).
- Sequoia blocks native window tiling shortcuts when Karabiner is active.
- GUI modifications strip JSON comments.
- No state, no conditional logic, no window management — `shell_command` is fire-and-forget.

**Verdict:** Karabiner's main value is creating a Hyper key or intercepting system shortcuts. With `Ctrl+Opt` as our namespace, neither is needed.

### Option C: Karabiner + Hammerspoon (Hyper Key Pattern)

The established "Hyper key" pattern: Karabiner remaps Caps Lock to `Cmd+Ctrl+Opt+Shift` (the "Hyper" modifier), Hammerspoon listens for Hyper+key combos.

**Evaluated and rejected.** The Hyper key approach adds a second macOS tool (Karabiner) with its own permission grants, macOS upgrade risk, and Sequoia tiling conflicts. The `Ctrl+Opt` namespace provides equivalent conflict avoidance with Hammerspoon alone.

### Option D: Karabiner Only with shell_command

Skip Hammerspoon entirely — have Karabiner's `shell_command` call scripts directly.

**Evaluated and rejected.** Too limited for the full action registry — no state, no window management, no conditional logic.

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

## Modifier Namespace Strategy (Cross-Platform)

The key design decision is choosing modifier combos that don't collide with system or application shortcuts on either platform.

### macOS: `Ctrl+Opt` (Control+Option)

Why `Ctrl+Opt` is safe:
- macOS system shortcuts live in `Cmd+key`, `Cmd+Shift+key`, `Cmd+Opt+key`, and `Ctrl+key` (Spaces/Mission Control) namespaces.
- `Ctrl+Opt+key` is essentially unused by macOS and standard applications.
- Hammerspoon's `hs.hotkey.bind({"ctrl", "alt"}, key, fn)` grabs these at the application level — no low-level interception needed.
- Adding `Shift` gives a second tier: `Ctrl+Opt+Shift+key` for extended actions (screenshots, etc.).

### Linux: `Super` (existing)

- Super+key is already the standard namespace for custom actions on Linux DEs.
- Cinnamon reserves a few Super combos (Super alone opens the menu) but the letter/number space is wide open.
- Super+Shift+key provides the extended tier, matching the macOS pattern.

### Keybinding Namespace

| Modifier tier | macOS | Linux |
|---------------|-------|-------|
| Primary actions | Ctrl+Opt+key | Super+key |
| Extended actions (screenshots, etc.) | Ctrl+Opt+Shift+key | Super+Shift+key |
| Window management | Ctrl+Opt+Arrow/key | Super+Arrow/key (Cinnamon built-in) |

This gives us 26+ letter keys, 10 number keys, arrow keys, and function keys — more than enough for every action on both platforms.

---

## Proposed Action Registry Format

```yaml
# shared/group_vars/all.yml (or shared/vars/action-bindings.yml)
workstation_actions:

  # --- Launcher / Utility ---
  - action: open_launcher
    description: "Open app launcher / command palette"
    keybinding:
      linux: "<Super>space"
      macos: { mods: [ctrl, alt], key: space }
    implementation:
      linux: { type: dconf, command: "vicinae toggle" }
      macos: { type: hammerspoon, lua: 'hs.execute("open raycast://", true)' }

  - action: clipboard_history
    description: "Open clipboard history"
    keybinding:
      linux: "<Super>v"
      macos: { mods: [ctrl, alt], key: v }
    implementation:
      linux: { type: dconf, command: "xdg-open vicinae://extensions/vicinae/clipboard/history" }
      macos: { type: hammerspoon, lua: 'hs.execute("open raycast://extensions/raycast/clipboard-history/clipboard-history", true)' }

  - action: emoji_picker
    description: "Open emoji picker"
    keybinding:
      linux: "<Super>e"
      macos: { mods: [ctrl, alt], key: e }
    implementation:
      linux: { type: dconf, command: "xdg-open vicinae://extensions/vicinae/emoji" }
      macos: { type: hammerspoon, lua: 'hs.execute("open raycast://extensions/raycast/emoji-symbols/search-emoji-symbols", true)' }

  # --- Screenshots ---
  - action: screenshot_region
    description: "Capture screenshot of selected region"
    keybinding:
      linux: "<Super><Shift>4"
      macos: { mods: [ctrl, alt, shift], key: "4" }
    implementation:
      linux: { type: dconf, command: "flameshot gui" }
      macos: { type: hammerspoon, lua: 'hs.application.launchOrFocus("CleanShot X")' }

  - action: screenshot_full
    description: "Capture full-screen screenshot"
    keybinding:
      linux: "<Super><Shift>3"
      macos: { mods: [ctrl, alt, shift], key: "3" }
    implementation:
      linux: { type: dconf, command: "flameshot full --path ~/Screenshots" }
      macos: { type: hammerspoon, lua: 'hs.eventtap.keyStroke({"cmd", "shift"}, "3")' }

  # --- Window Management ---
  - action: window_left_half
    description: "Move window to left half of screen"
    keybinding:
      linux: "<Super>Left"
      macos: { mods: [ctrl, alt], key: left }
    implementation:
      linux: { type: dconf_wm }  # Cinnamon built-in, configured via dconf
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:moveToUnit(hs.layout.left50) end

  - action: window_right_half
    description: "Move window to right half of screen"
    keybinding:
      linux: "<Super>Right"
      macos: { mods: [ctrl, alt], key: right }
    implementation:
      linux: { type: dconf_wm }
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:moveToUnit(hs.layout.right50) end

  - action: window_maximize
    description: "Maximize window"
    keybinding:
      linux: "<Super>Up"
      macos: { mods: [ctrl, alt], key: up }
    implementation:
      linux: { type: dconf_wm }
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:maximize() end

  - action: window_restore
    description: "Restore / un-maximize window"
    keybinding:
      linux: "<Super>Down"
      macos: { mods: [ctrl, alt], key: down }
    implementation:
      linux: { type: dconf_wm }
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:moveToUnit({x=0.1, y=0.1, w=0.8, h=0.8}) end

  - action: window_next_monitor
    description: "Move window to next monitor"
    keybinding:
      linux: "<Super><Shift>Right"
      macos: { mods: [ctrl, alt, shift], key: right }
    implementation:
      linux: { type: dconf_wm }
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:moveToScreen(win:screen():next()) end

  - action: window_prev_monitor
    description: "Move window to previous monitor"
    keybinding:
      linux: "<Super><Shift>Left"
      macos: { mods: [ctrl, alt, shift], key: left }
    implementation:
      linux: { type: dconf_wm }
      macos:
        type: hammerspoon
        lua: |
          local win = hs.window.focusedWindow()
          if win then win:moveToScreen(win:screen():previous()) end
```

### How Ansible Consumes This

**Linux role** (`desktop-env/tasks/debian.yml`):
- Filters `workstation_actions` for entries with `implementation.linux.type == "dconf_custom_keybinding"`
- Loops to generate dconf custom keybinding tasks (replacing current hardcoded tasks)
- Builds the `custom-list` array dynamically

**macOS role** (new `keyboard/tasks/darwin.yml`):
- Installs Hammerspoon via `homebrew_cask`
- Generates `~/.hammerspoon/actions.lua` from the registry via Ansible template
- Deploys base `init.lua` via Stow (loads `actions.lua` + any manual Hammerspoon modules)

---

## Initial Capture Problem

Separate from the action binding architecture, there is the question of how settings get INTO the repo for the first time. The existing sync-app-settings ADR describes a manual workflow. For the tools in this research:

### Hammerspoon
- Config at `~/.hammerspoon/` — Stow-friendly
- `actions.lua` is *generated* from the action registry by Ansible template (not captured)
- `init.lua` and any additional modules (utilities, etc.) are manually authored Lua files committed to the Stow package
- Window management is part of `actions.lua` — no separate tool needed

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

### Karabiner-Elements Hyper Key Pattern
Remap Caps Lock to Cmd+Ctrl+Opt+Shift via Karabiner, dispatch via Hammerspoon.
**Rejected:** Adds a second macOS tool with three permission grants, macOS upgrade breakage risk, and Sequoia tiling conflicts. The `Ctrl+Opt` namespace achieves the same conflict avoidance with Hammerspoon alone.

### sxhkd for Both Platforms (Linux) + Hammerspoon (macOS)
Skip dconf, use sxhkd on Linux.
**Rejected for Linux:** sxhkd requires managing key conflicts with Cinnamon. The native dconf approach is simpler and integrated. sxhkd/swhkd is the fallback if Cinnamon Wayland breaks dconf keybindings.

### Karabiner-Elements shell_command Only
Skip Hammerspoon entirely — have Karabiner's `shell_command` call scripts directly.
**Rejected:** Karabiner's shell_command has a minimal environment, no state management, no conditional logic, no window management. Hammerspoon is needed for rich action dispatch.

---

## Open Questions

1. **Per-device keybindings?** Karabiner supports per-device rules (built-in vs external keyboard). If Karabiner is ever added for key remapping, should the action registry support device-specific bindings? For now, Hammerspoon bindings are device-agnostic.

2. **How to handle actions that are only on one platform?** (e.g., Cinnamon-specific DE shortcuts, macOS-specific Setapp app triggers). The registry format supports omitting a platform key — the question is whether the Ansible templates should warn or silently skip.

3. **Cinnamon window management keybindings.** Cinnamon's built-in tiling (Super+Arrow) is already configured by default. The `dconf_wm` implementation type signals "use the DE built-in" — should the Ansible role explicitly set these dconf keys for consistency, or trust the DE defaults?

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hammerspoon Accessibility permission lost | Low | High (macOS hotkeys stop) | Document re-grant in post-install; Ansible can detect and warn |
| macOS upgrade breaks Hammerspoon | Low (user-space, no drivers) | Medium (hotkeys stop until update) | Hammerspoon is pure user-space; historically stable across macOS upgrades |
| Cinnamon Wayland breaks dconf keybindings | Low (dconf is display-independent) | Medium | swhkd fallback ready |
| Complexity of action registry YAML | Low | Low | Start small — migrate existing 3 Vicinae bindings first |
| Config drift between platforms | Medium | Low | Single source of truth in shared vars; CI could validate |
