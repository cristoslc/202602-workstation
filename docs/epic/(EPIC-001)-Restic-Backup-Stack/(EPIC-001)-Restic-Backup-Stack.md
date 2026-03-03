---
title: "EPIC-001: Restic Backup Stack"
artifact: EPIC-001
status: Active
author: cristos
created: 2026-03-01
last-updated: 2026-03-03
parent-vision: VISION-001
success-criteria:
  - "`make apply ROLE=backups` configures Restic + Backrest on both macOS and Linux"
  - "365-day deduplicated encrypted file history on Backblaze B2"
  - "Per-workstation snapshot isolation by hostname"
  - "Background staleness watcher with desktop + email alerts"
  - "Zero manual backup configuration after bootstrap"
---

# EPIC-001: Restic Backup Stack

## Goal / Objective

After `make apply ROLE=backups`, both macOS and Linux workstations are automatically configured to back up `$HOME` to Backblaze B2 via Restic, with Backrest as the scheduling/monitoring layer, 365+ day retention, per-workstation isolation, and error-only notifications. No manual backup configuration after bootstrap.

## Scope Boundaries

### In scope

- Restic binary installation (cross-platform, pinned version)
- Backrest installation and configuration (systemd/launchd background service)
- Exclude patterns template for OS noise, build artifacts, IDE state, macOS Library carve-outs
- SOPS-encrypted secrets (repo password, B2 credentials)
- Error-only notifications (desktop + SMTP email via Shoutrrr)
- Staleness watcher (heartbeat file + background check)
- Make targets: `backup-status`, `backup-browse`
- Playbook tag updates (`restic`, `backrest`)

### Out of scope

- Replacing Backblaze Personal on macOS (complementary, not competitive)
- Replacing Timeshift on Linux (system snapshots remain separate from file backup)
- Cloud storage provider abstraction (B2 is the target; rclone/multi-cloud is future work)

## Child Specs

_To be created. Likely decomposition:_
- Restic + Backrest installation and service configuration
- Exclude patterns and retention policy
- Notification pipeline (desktop + email + staleness watcher)

## Key Dependencies

- [SPIKE-003](../../research/Complete/(SPIKE-003)-Backup-Solution-Evaluation/(SPIKE-003)-Backup-Solution-Evaluation.md) — Backup Solution Evaluation (Complete)
- [ADR-002](../../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) — Encryption at Rest (secrets storage pattern)
- Backblaze B2 Terraform infrastructure (`infra/b2-backup/`)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| B2 egress costs on large restores | Unexpected bills | Document cost model; test partial restore first |
| Backrest update breaks config schema | Service fails to start | Pin Backrest version; test upgrades |
| Exclude patterns miss important files | Data loss on restore | Test restore of representative file set after first backup |

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Vision | [VISION-001](../../vision/(VISION-001)-Workstation-as-Code/(VISION-001)-Workstation-as-Code.md) | Workstation as Code |
| Spike | [SPIKE-003](../../research/Complete/(SPIKE-003)-Backup-Solution-Evaluation/(SPIKE-003)-Backup-Solution-Evaluation.md) | Backup Solution Evaluation |
| ADR | [ADR-002](../../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) | Encryption at Rest |
| Legacy | [PRD-002](../../prd/Abandoned/(PRD-002)-Restic-Backup-Stack/(PRD-002)-Restic-Backup-Stack.md) | Restic Backup Stack (migrated from PRD) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-01 | 028b2ad | Migrated from PRD-002 |
| Active | 2026-03-03 | 007be42 | Implementation exists; moving to Active for bootstrap validation |
