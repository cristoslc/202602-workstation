# ADR: Cross-Platform Action Bindings via Karabiner + Hammerspoon + dconf

**Status:** Proposed
**Date:** 2026-02-25
**Research:** [cross-platform-action-bindings](../../research/Active/cross-platform-action-bindings/README.md)

## Context

The workstation provisioning system has keybindings that are app-coupled and platform-scattered. On Linux, three Vicinae shortcuts are hardcoded as Cinnamon dconf tasks. On macOS, equivalent actions (Raycast launcher, clipboard history, screenshots) are left to manual configuration. There is no shared vocabulary for "the same user action on different platforms using different apps."

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
      macos: { mods: [command, control, option, shift], key: space }
    implementation:
      linux: { type: dconf, command: "vicinae toggle" }
      macos: { type: hammerspoon, lua: 'hs.execute("open raycast://", true)' }
```

Actions are the stable abstraction. Apps and dispatchers are implementation details.

### 2. macOS: Karabiner-Elements + Hammerspoon

**Karabiner-Elements** creates the Hyper key (Caps Lock → Cmd+Ctrl+Opt+Shift) and handles low-level key remapping. Its JSON config lives in a Stow package at `macos/dotfiles/karabiner/.config/karabiner/`.

**Hammerspoon** dispatches Hyper+key combos to actions. Its Lua config lives in a Stow package at `macos/dotfiles/hammerspoon/.hammerspoon/`. An Ansible template generates `actions.lua` from the action registry.

The Hyper key pattern avoids all system and application shortcut conflicts by using a modifier combination (Cmd+Ctrl+Opt+Shift) that nothing else claims.

**New roles:**
- `shared/roles/keyboard/` — cross-platform role with `darwin.yml` (Karabiner + Hammerspoon install and config deployment) and `debian.yml` (data-driven dconf keybindings).

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

### 4. Caps Lock → Escape (tap) / Hyper (hold) on both platforms

| Platform | Mechanism |
|----------|-----------|
| macOS | Karabiner `to_if_alone: escape`, `to: [command, control, option, shift]` |
| Linux | Future: `keyd` or `interception-tools` (not required for initial implementation — Super key is sufficient) |

### 5. Initial action set

Start with the actions already half-implemented, plus the most painful gaps:

| Action | Linux binding | macOS binding | Linux app | macOS app |
|--------|-------------|---------------|-----------|-----------|
| `open_launcher` | Super+Space | Hyper+Space | Vicinae | Raycast |
| `clipboard_history` | Super+V | Hyper+V | Vicinae | Raycast |
| `emoji_picker` | Super+E | Hyper+E | Vicinae | Raycast |
| `screenshot_region` | Super+Shift+4 | Hyper+Shift+4 | Flameshot | CleanShot X |
| `screenshot_full` | Super+Shift+3 | Hyper+Shift+3 | Flameshot | macOS built-in |

Additional actions (window management, app switching, media controls) can be added incrementally.

## Consequences

### Positive

- **Consistent muscle memory** — same keybindings across machines, surviving app changes.
- **Single source of truth** — action registry in git defines all keybindings for all platforms.
- **Apps are swappable** — change the `implementation` entry without touching keybindings. The `docs/fallback.md` Vicinae-to-Ulauncher swap becomes a one-line change.
- **No more manual post-install** — screenshot and launcher shortcuts are deployed by bootstrap, removing items from `post-install.md`.
- **Stow-managed configs** — Karabiner JSON and Hammerspoon Lua are dotfiles like everything else.
- **Hyper key avoids conflicts** — the Cmd+Ctrl+Opt+Shift namespace has zero system or app collisions on macOS.

### Negative

- **Two new macOS tools** — Karabiner-Elements and Hammerspoon must be installed, and both require manual permission grants (Input Monitoring, Accessibility) that Ansible cannot automate.
- **macOS upgrade risk** — Karabiner historically breaks on major macOS updates until a patch ships. Mitigation: patches ship within days; pin OS upgrades.
- **Learning curve** — Karabiner JSON and Hammerspoon Lua are new config formats to maintain.
- **Increased complexity** — the action registry YAML, Jinja2 templates, and two dispatch mechanisms are more moving parts than the current hardcoded dconf tasks.

### Neutral

- The Linux side stays with the existing dconf approach — this ADR adds structure (data-driven loop) but does not change the underlying mechanism.
- The Hyper key on Linux is not required initially. Super is already a free modifier namespace on Cinnamon. A Linux Hyper key can be added later if needed.
- Karabiner and Hammerspoon are both mature, widely-used open-source tools (14.5k and ~14.5k GitHub stars respectively), MIT-licensed, actively maintained.

## Implementation Plan

### Phase 1: Karabiner + Hammerspoon bootstrap (macOS only)

1. Create `shared/roles/keyboard/` with `tasks/darwin.yml`:
   - Install Karabiner-Elements via `homebrew_cask`
   - Install Hammerspoon via `homebrew_cask`
   - Deploy Karabiner Hyper key config (Stow or Ansible template)
   - Deploy Hammerspoon base config (Stow)
   - Add `debug` note about required permissions
2. Create Stow packages:
   - `macos/dotfiles/karabiner/.config/karabiner/` — Hyper key rule + asset files
   - `macos/dotfiles/hammerspoon/.hammerspoon/` — `init.lua` + `actions.lua`

### Phase 2: Action registry + data-driven keybindings

3. Create `shared/vars/action-bindings.yml` with the initial 5 actions.
4. Refactor `linux/roles/desktop-env/tasks/main.yml` to loop over the registry instead of hardcoding per-binding tasks.
5. Create Ansible template for `actions.lua` that generates Hammerspoon bindings from the registry.
6. Add the `keyboard` role to both platform playbooks (`03-desktop.yml`).

### Phase 3: Expand and harden

7. Add screenshot actions (requires choosing Flameshot for Linux, confirming CleanShot X URL scheme).
8. Add window management actions if desired.
9. Add Ansible handler for Cinnamon restart after keybinding changes.
10. Update `post-install.md` to remove items that are now automated (Raycast shortcuts, screenshot tool shortcuts).

## Alternatives Considered

See [research doc](../../research/Active/cross-platform-action-bindings/README.md#alternatives-considered) for detailed evaluation of:
- Hammerspoon only (can't intercept system shortcuts or create Hyper key)
- Karabiner only (too limited for rich action dispatch)
- sxhkd on Linux (conflicts with Cinnamon, not integrated)
- macOS Shortcuts.app (not programmable enough)
- BetterTouchTool (paid, proprietary)
