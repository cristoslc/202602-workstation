# Research / Spikes Lifecycle Index

## Active

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|

_None._

## Complete

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|
| SPIKE-001 | [Raycast Settings Export](./Complete/(SPIKE-001)-Raycast-Settings-Export/(SPIKE-001)-Raycast-Settings-Export.md) | 2026-02-25 | 20fb970 | .rayconfig export viable |
| SPIKE-003 | [Backup Solution Evaluation](./Complete/(SPIKE-003)-Backup-Solution-Evaluation/(SPIKE-003)-Backup-Solution-Evaluation.md) | 2026-03-02 | 411986d | Restic selected; findings feed EPIC-001 |
| SPIKE-002 | [Secrets Autodiscovery](./Complete/(SPIKE-002)-Secrets-Autodiscovery/(SPIKE-002)-Secrets-Autodiscovery.md) | 2026-02-27 | 19b2dd7 | @tui YAML annotations |
| SPIKE-004 | [Cross-Platform Action Bindings](./Complete/(SPIKE-004)-Cross-Platform-Action-Bindings/(SPIKE-004)-Cross-Platform-Action-Bindings.md) | 2026-03-02 | 39f786f | Hammerspoon on macOS confirmed; dconf on Mint untested |
| SPIKE-005 | [Sync App Settings](./Complete/(SPIKE-005)-Sync-App-Settings/(SPIKE-005)-Sync-App-Settings.md) | 2026-03-03 | f95ecc5 | Research concluded; findings feed EPIC-003 |
| SPIKE-006 | [Sync User Folders](./Complete/(SPIKE-006)-Sync-User-Folders/(SPIKE-006)-Sync-User-Folders.md) | 2026-03-03 | fda9b50 | Research concluded; findings feed EPIC-002 |
| SPIKE-007 | [Hub Server Failover and Migration](./Complete/(SPIKE-007)-Hub-Server-Failover-and-Migration/(SPIKE-007)-Hub-Server-Failover-and-Migration.md) | 2026-03-03 | 5595b38 | All go/no-go criteria pass; runbooks at docs/runbooks/hub-replacement.md; accept single-hub, defer dual-hub to VISION-002 |
| SPIKE-008 | [Sync Boundary Enforcement](./Complete/(SPIKE-008)-Sync-Boundary-Enforcement/(SPIKE-008)-Sync-Boundary-Enforcement.md) | 2026-03-03 | 52ee0c6 | Research concluded; recommends Approach D+ (Hybrid with real-time detection and journal); see ADR-006 |
| SPIKE-009 | [1Password Bootstrap Timing](./Complete/(SPIKE-009)-1Password-Bootstrap-Timing/(SPIKE-009)-1Password-Bootstrap-Timing.md) | 2026-03-05 | 0f73e40 | GO (conditional) — no circular dependency; one-time 1Password sign-in required on fresh machines |
| SPIKE-010 | [Login-Hook Propagation Mechanism](./Complete/(SPIKE-010)-Login-Hook-Propagation-Mechanism/(SPIKE-010)-Login-Hook-Propagation-Mechanism.md) | 2026-03-05 | 0f73e40 | GO — launchd user agent (macOS) + systemd user timer (Linux); pull-only + notify |
| SPIKE-011 | [Cross-Platform CI Scope](./Complete/(SPIKE-011)-Cross-Platform-CI-Scope/(SPIKE-011)-Cross-Platform-CI-Scope.md) | 2026-03-05 | 0f73e40 | GO — all 8 check targets work without secrets; Linux every push + macOS weekly |
| SPIKE-012 | [Steam Deck Desktop Mode Provisioning](./Complete/(SPIKE-012)-Steam-Deck-Desktop-Mode-Provisioning/(SPIKE-012)-Steam-Deck-Desktop-Mode-Provisioning.md) | 2026-03-06 | b407c2f | GO — Nix+Flatpak+Stow strategy viable; all go criteria met |
| SPIKE-013 | [Extended Desktop via Tablet](./Complete/(SPIKE-013)-Extended-Desktop-via-Tablet/(SPIKE-013)-Extended-Desktop-via-Tablet.md) | 2026-03-12 | — | GO — Sunshine+Moonlight+BetterDisplay; Weylus mirror-only |

## Planned

| ID | Title | Date | Commit | Notes |
|----|-------|------|--------|-------|

## Abandoned

_None._
