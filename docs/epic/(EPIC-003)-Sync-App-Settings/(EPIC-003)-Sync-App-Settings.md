---
title: "EPIC-003: Sync App Settings"
artifact: EPIC-003
status: Active
author: cristos
created: 2026-03-02
last-updated: 2026-03-03
parent-vision: VISION-001
success-criteria:
  - "`make apply` reproduces all captured app configurations on a fresh machine"
  - "Classification audit complete — every role categorized as managed, cloud-synced, or out-of-scope"
  - "~25 Stow packages with no collisions (`stow --simulate` clean on all targets)"
  - "All secrets encrypted at rest via SOPS/age — no plaintext credentials in git"
---

# EPIC-003: Sync App Settings

## Goal / Objective

Systematically extend the existing Stow + Ansible primitives so that every role with capturable settings is fully managed. After `make apply`, a fresh macOS or Linux workstation launches with app configurations matching the source machine — no manual reconfiguration. Cloud-synced apps are explicitly classified as out-of-scope; opaque/binary formats are documented and excluded.

## Scope Boundaries

### In scope

- Audit all 35+ roles against SPIKE-005's coverage matrix
- Migrate P1-P3 gaps into Stow packages or Ansible tasks (per ADR-004's classification framework)
- VS Code `keybindings.json` + `snippets/` capture
- iTerm2 plist export (XML-converted, age-encrypted)
- `.npmrc`, `uv.toml`, Docker `config.json` Stow packages
- VLC preferences (platform-specific Stow packages)
- Raycast settings export/import workflow (SPEC-001)
- SOPS/age encryption for any config containing tokens or credentials
- Stow conflict resolution for new packages on existing machines

### Out of scope

- Cloud-synced apps (1Password, Slack, MS 365, Spotify, Steam, Tailscale, Surfshark) — vendor sync handles these
- Browser profiles (Firefox, Chrome, Brave) — too large/binary, use browser-native sync
- Stream Deck profiles — vendor database format, manual export/import only
- Per-project configs (`.shellcheckrc`, `.yamllint`) — belong in project repos
- Lint-tools role configs — project-level, not per-machine

## Child Specs

| ID | Title | Status | Notes |
|----|-------|--------|-------|
| [SPEC-001](../../spec/(SPEC-001)-Raycast-Sync/(SPEC-001)-Raycast-Sync.md) | Raycast Sync | Draft | Export/import workflow with age encryption |

_Planned (to be created from SPIKE-005 gap list):_
- VS Code keybindings + snippets capture
- iTerm2 plist export and Stow integration
- npm/uv/Docker config Stow packages
- VLC preferences (cross-platform)
- Keka preferences (macOS defaults)

## Key Dependencies

| Dependency | Type | Status | Notes |
|------------|------|--------|-------|
| [SPIKE-005](../../research/Complete/(SPIKE-005)-Sync-App-Settings/(SPIKE-005)-Sync-App-Settings.md) | Research | Complete | Coverage audit and classification framework |
| [ADR-004](../../adr/Adopted/(ADR-004)-Sync-App-Settings.md) | Decision | Adopted | Expanded Stow + Ansible pattern (no new tools) |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Stow conflicts on existing machines | Symlink collisions block `make apply` | `stow --simulate` dry-run before each new package; existing conflict resolution in `stow-packages.yml` |
| Binary plist diffs are noisy | Hard to review git history | Convert to XML with `plutil -convert xml1`; accept some noise for plists |
| App updates change config format | Stow package becomes stale | Pin app versions where practical; test after updates |
| Secret leakage in config files | Credentials committed to git | Audit every new file for tokens before committing; SOPS-encrypt anything sensitive |
| Scope creep from 35+ roles | Epic never completes | Strict P1-P3 prioritization from SPIKE-005; cloud-synced apps are explicitly excluded |

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Vision | [VISION-001](../../vision/(VISION-001)-Workstation-as-Code/(VISION-001)-Workstation-as-Code.md) | Workstation as Code |
| Spike | [SPIKE-005](../../research/Complete/(SPIKE-005)-Sync-App-Settings/(SPIKE-005)-Sync-App-Settings.md) | App Settings Sync Across Machines |
| ADR | [ADR-004](../../adr/Adopted/(ADR-004)-Sync-App-Settings.md) | Sync App Settings via Expanded Stow + Ansible |
| Spec | [SPEC-001](../../spec/(SPEC-001)-Raycast-Sync/(SPEC-001)-Raycast-Sync.md) | Raycast Sync |
| ADR | [ADR-002](../../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) | Encryption at Rest for Personal Files |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-02 | f99e8fa | Created to parent SPEC-001 and coordinate SPIKE-005/ADR-004 work |
| Active | 2026-03-03 | cff3f69 | Dependencies resolved; beginning settings capture work |
