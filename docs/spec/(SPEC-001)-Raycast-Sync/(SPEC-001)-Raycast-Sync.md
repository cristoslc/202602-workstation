---
title: "SPEC-001: Raycast Sync"
artifact: SPEC-001
status: Draft
author: cristos
created: 2026-03-01
last-updated: 2026-03-01
parent-epic: _none (orphan — no matching Epic for app settings sync yet)_
linked-research:
  - SPIKE-001
linked-adrs:
  - ADR-004
---

# SPEC-001: Raycast Sync

## Problem Statement

Raycast is installed by the `launchers` role but all configuration is left manual. On a fresh machine, the user must re-configure extensions, hotkeys, snippets, quicklinks, and preferences — contradicting the workstation goal of idempotent single-command provisioning.

## External Behavior

**Inputs:**
- Existing Raycast configuration on a source machine
- `make export-raycast` to capture settings

**Outputs:**
- Age-encrypted `.rayconfig` file at `macos/files/raycast/raycast.rayconfig.age`
- On bootstrap: decrypted `.rayconfig` triggers Raycast import dialog

**Preconditions:**
- Raycast is installed (handled by `launchers` role)
- Age key is available on the target machine

**Postconditions:**
- Raycast launches with full extension set, hotkeys, snippets, and preferences matching the source machine
- No plaintext secrets committed to git

## Acceptance Criteria

1. `make apply` on a clean macOS machine + confirming the import dialog produces a Raycast instance matching the source machine's configuration.
2. `.rayconfig` is age-encrypted at rest in the repo — no plaintext secrets committed.
3. `make export-raycast` opens the Raycast export UI, age-encrypts the result, and places it in the repo.
4. Bootstrap decrypts, opens the `.rayconfig`, pauses for user confirmation, then cleans up the plaintext.
5. Hotkeys are consistent with the cross-platform action registry (no conflicts, no duplication).

## Scope & Constraints

### In scope

- `.rayconfig` export, age-encrypt, and import workflow
- `make export-raycast` convenience target
- Hotkey conflict avoidance with the action registry (ADR-003)

### Out of scope

- Raycast Pro cloud sync (vendor account decision)
- Extension marketplace management (synced as part of settings blob)
- Linux equivalent (Raycast is macOS-only)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Raycast settings format is opaque/binary | No readable git diffs | Age-encrypted in git regardless; accept binary commit |
| Settings may include auth tokens | Secret leakage | Age-encryption protects at rest; audit before first commit |
| Hotkey conflicts with Hammerspoon | Double-fire or dead keys | Raycast is a target of the action registry, not a parallel source |

## Implementation Approach

1. Add `make export-raycast` target that opens Raycast deeplink export, then age-encrypts the resulting file
2. Extend the `launchers` role with an import task: decrypt `.rayconfig.age`, `open` the file (triggers Raycast import dialog), clean up plaintext
3. Wire import into the TUI's Import Settings screen

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Spike | [SPIKE-001](../../research/Complete/(SPIKE-001)-Raycast-Settings-Export/(SPIKE-001)-Raycast-Settings-Export.md) | Raycast Settings Export |
| ADR | [ADR-004](../../adr/Proposed/(ADR-004)-Sync-App-Settings.md) | Sync App Settings |
| Legacy | [PRD-001](../../prd/Abandoned/(PRD-001)-Raycast-Sync/(PRD-001)-Raycast-Sync.md) | Raycast Sync (migrated from PRD) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-01 | 028b2ad | Migrated from PRD-001 |
