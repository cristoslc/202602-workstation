# PRD-001: Raycast Sync

**Status:** Draft
**Author:** cristos
**Created:** 2026-02-25
**Last Updated:** 2026-02-25
**Research:** [(SPIKE-001) Raycast Settings Export](../../../research/Planned/(SPIKE-001)-Raycast-Settings-Export/README.md)
**ADR:** [Sync App Settings](../../../adr/Proposed/sync-app-settings.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-02-25 | 03eb670 | Initial creation |

---

## Problem

Raycast is installed by the `launchers` role via `brew install --cask raycast`, but all configuration is left manual (see `raycast.yml` line 17–23). On a fresh machine, the user must re-configure:

- Extensions (clipboard history, emoji picker, window management, snippets, calculator, etc.)
- Hotkeys for each extension command
- Quicklinks and script commands
- Snippets
- General preferences (theme, startup behavior, default actions)

This contradicts the workstation goal of idempotent, single-command provisioning.

## Goal

After `make apply`, Raycast launches with the user's full extension set, hotkeys, snippets, and preferences — no manual steps beyond granting macOS permissions.

## Scope

### In scope

- Capture current Raycast settings from the source machine
- Store settings in the repo (stow package or Ansible task)
- Deploy settings during bootstrap on new machines
- Handle the Raycast ↔ cross-platform-action-bindings interaction (hotkeys defined in the action registry must not conflict with Raycast's own hotkey assignments)

### Out of scope

- Raycast Pro cloud sync evaluation (that's a user account decision, not a provisioning concern)
- Extension marketplace management (extensions are synced as part of the settings blob)
- Linux equivalent (Raycast is macOS-only; Linux uses Vicinae via the `desktop-env` role)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Raycast settings format is opaque/binary | Can't produce readable git diffs | SPIKE-001 determines format; XML conversion if plist-based |
| Settings include auth tokens or API keys | Secret leakage to git | Audit export for embedded secrets; SOPS-encrypt if needed |
| Raycast updates break settings schema | Import fails on new version | Pin known-good format; test on upgrade |
| Hotkey conflicts with Hammerspoon action bindings | Double-fire or dead keys | Define Raycast as a target _of_ the action registry, not a parallel hotkey source |

## Research

| ID | Question | Status | Blocks |
|----|----------|--------|--------|
| SPIKE-001 | How to export, store, and import Raycast settings programmatically? | Planned | Implementation |

## Success Criteria

1. `make apply` on a clean macOS machine produces a Raycast instance matching the source machine's configuration (extensions, hotkeys, snippets, preferences).
2. Settings diff in git is human-reviewable (not binary blobs).
3. No embedded secrets in the committed settings file.
4. Hotkeys are consistent with the cross-platform action registry (no conflicts, no duplication).
