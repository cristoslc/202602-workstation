# ADR: Cross-Platform Action Bindings via Hammerspoon + dconf

**Status:** Proposed
**Date:** 2026-02-25
**Research:** [cross-platform-action-bindings](../../research/Active/cross-platform-action-bindings/README.md)

## Context

The workstation provisioning system has keybindings that are app-coupled and platform-scattered. On Linux, three Vicinae shortcuts are hardcoded as Cinnamon dconf tasks. On macOS, equivalent actions (Raycast launcher, clipboard history, screenshots) are left to manual configuration. Window management is unmanaged on both platforms. There is no shared vocabulary for "the same user action on different platforms using different apps."

Users expect consistent muscle memory across machines. When apps change (Vicinae swapped for Ulauncher, CleanShot X replaced by macOS built-in), keybindings should survive because they are bound to **actions**, not apps.

## Decision

### 1. Define a shared action registry in Ansible vars

A single YAML data structure in `shared/vars/action-bindings.yml` declares every user action with per-platform keybindings and implementations:

```yaml
workstation_actions:
  - action: open_launcher
    description: "Open app launcher"
    keybinding:
      linux: "<Super>space"
      macos: { mods: [ctrl, alt], key: space }
    implementation:
      linux: { type: dconf, command: "vicinae toggle" }
      macos: { type: hammerspoon, lua: 'hs.execute("open raycast://", true)' }
```

Actions are the stable abstraction. Apps and dispatchers are implementation details.

### 2. macOS: Hammerspoon as sole dispatcher

**Hammerspoon** binds global hotkeys and dispatches actions. It provides:
- Global hotkey binding via `hs.hotkey.bind()`
- Shell command execution, URL scheme launches, app focus
- Built-in window management via `hs.window` (tile, move, resize, multi-monitor)
- Auto-reload on config file change
- A single Lua config at `~/.hammerspoon/` — fully Stow-able

**Modifier namespace** is defined in the role's user defaults (`shared/roles/keyboard/defaults/main.yml`). The chosen modifiers should avoid conflicts with macOS system shortcuts and common application keybindings. Adding `Shift` provides a second tier for extended actions.

The Lua config lives in a Stow package at `macos/dotfiles/hammerspoon/.hammerspoon/`. An Ansible template generates `actions.lua` from the action registry.

**New role:**
- `shared/roles/keyboard/` — cross-platform role with `darwin.yml` (Hammerspoon install + config) and `debian.yml` (data-driven dconf keybindings).

### 3. Linux: Data-driven dconf custom keybindings

The existing `desktop-env` role's hardcoded dconf tasks are replaced by a loop that reads from the action registry. The same `community.general.dconf` module is used, but the binding data comes from `workstation_actions` instead of being inlined per-task.

```yaml
# Dynamically generate custom keybindings from action registry
- name: "Set {{ item.action }} keybinding"
  community.general.dconf:
    key: "/org/cinnamon/desktop/keybindings/custom-keybindings/custom{{ idx }}/binding"
    value: "['{{ item.keybinding.linux }}']"
    state: present
  loop: "{{ workstation_actions | selectattr('implementation.linux.type', 'equalto', 'dconf') | list }}"
  loop_control:
    index_var: idx
    label: "{{ item.action }}"
```

Window management on Linux uses Cinnamon's built-in tiling (Super+Arrow), configured via dconf window management keys for consistency.

### 4. Initial action set

The canonical action list with current keybindings lives in `shared/roles/keyboard/defaults/main.yml`. The following table summarizes the action categories and per-platform dispatchers:

| Category | Actions | Linux dispatcher | macOS dispatcher |
|----------|---------|-----------------|-----------------|
| Launchers | open_launcher, clipboard_history, emoji_picker | dconf custom keybinding | Hammerspoon → URL scheme |
| Screenshots | screenshot_region, screenshot_full | dconf → Flameshot | Hammerspoon → CleanShot X / built-in |
| Window tiling | left/right half, maximize, restore, thirds, two-thirds | Cinnamon WM dconf keys | Hammerspoon `hs.window` |
| Window movement | next/prev monitor, hide, fullscreen | Cinnamon WM dconf keys | Hammerspoon `hs.window` |

## Consequences

### Positive

- **Consistent muscle memory** — same keybindings across machines, surviving app changes.
- **Single source of truth** — action registry in git defines all keybindings for all platforms.
- **Apps are swappable** — change the `implementation` entry without touching keybindings.
- **No more manual post-install** — screenshot, launcher, and window management shortcuts are deployed by bootstrap.
- **Stow-managed config** — Hammerspoon Lua is a dotfile like everything else.
- **Configurable modifier namespace** — keybindings are defined in role defaults, easy to change without touching dispatch logic.
- **Window management included** — Hammerspoon replaces the need for Rectangle/Magnet on macOS; Cinnamon's built-in tiling is configured consistently on Linux.
- **One macOS tool, one permission** — only Hammerspoon (Accessibility). No Karabiner means no Input Monitoring, no Driver Extension, no Login Items, no macOS upgrade breakage risk.

### Negative

- **One new macOS tool** — Hammerspoon requires manual Accessibility permission grant that Ansible cannot automate.
- **Learning curve** — Hammerspoon Lua is a new config format to maintain.
- **Increased complexity** — the action registry YAML, Jinja2 template, and dispatch mechanism are more moving parts than the current hardcoded dconf tasks.
- **Cannot intercept system shortcuts** — Hammerspoon's `hs.hotkey.bind()` cannot override macOS system shortcuts (Cmd+Shift+4, Cmd+Space, etc.). Modifier choices should avoid those; this means we cannot remap existing system shortcuts if desired in the future.

### Neutral

- The Linux side stays with the existing dconf approach — this ADR adds structure (data-driven loop) but does not change the underlying mechanism.
- Karabiner-Elements remains available as a future add-on if hardware-level key remapping is ever needed (e.g., Caps Lock → Escape). It is not required for the action binding system.

## Implementation Plan

### Phase 1: Hammerspoon bootstrap (macOS only)

1. Create `shared/roles/keyboard/` with `tasks/darwin.yml`:
   - Install Hammerspoon via `homebrew_cask`
   - Deploy Hammerspoon base config via Stow
   - Add `debug` note about required Accessibility permission
2. Create Stow package:
   - `macos/dotfiles/hammerspoon/.hammerspoon/` — `init.lua` + `actions.lua`

### Phase 2: Action registry + data-driven keybindings

3. Create `shared/vars/action-bindings.yml` with the initial action set (launcher, clipboard, emoji, screenshots, window management).
4. Refactor `linux/roles/desktop-env/tasks/main.yml` to loop over the registry instead of hardcoding per-binding tasks.
5. Create Ansible template for `actions.lua` that generates Hammerspoon bindings from the registry.
6. Add the `keyboard` role to both platform playbooks (`03-desktop.yml`).

### Phase 3: Expand and harden

7. Confirm CleanShot X URL scheme for screenshot region capture.
8. Configure Cinnamon window management dconf keys explicitly for consistency.
9. Add Ansible handler for Cinnamon restart after keybinding changes.
10. Update `post-install.md` to remove items that are now automated.

## Alternatives Considered

See [research doc](../../research/Active/cross-platform-action-bindings/README.md#alternatives-considered) for detailed evaluation of:
- Karabiner-Elements Hyper key pattern (unnecessary complexity — a well-chosen modifier avoids conflicts without a second tool)
- Karabiner only (too limited for rich action dispatch and window management)
- sxhkd on Linux (conflicts with Cinnamon, not integrated)
- macOS Shortcuts.app (not programmable enough)
- BetterTouchTool (paid, proprietary)
