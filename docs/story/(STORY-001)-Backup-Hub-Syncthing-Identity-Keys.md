---
title: "STORY-001: Backup Hub Syncthing Identity Keys"
artifact: STORY-001
status: Ready
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
related:
  - JOURNEY-003
depends-on: []
---

# STORY-001: Backup Hub Syncthing Identity Keys

**As a** multi-machine developer, **I want** hub Syncthing identity keys (`cert.pem`, `key.pem`) backed up and version-controlled, **so that** I can restore the hub with the same device ID and avoid reconfiguring all spokes after a hub failure.

## Context

SPIKE-007 identified hub key backup as the highest-priority gap. Without preserved keys, hub replacement requires Runbook C (45-70 min, all spokes reconfigured). With preserved keys, Runbook B applies (35-60 min, zero spoke reconfiguration). The keys follow the ADR-002 encryption-at-rest pattern.

## Acceptance Criteria

1. `cert.pem` and `key.pem` are age-encrypted and stored at `shared/secrets/syncthing-hub-keys/{cert.pem.age,key.pem.age}`.
2. A `make hub-backup-keys HUB_HOST=<host>` target exists that SSHs to the hub, downloads the keys, age-encrypts them using the public key from `.sops.yaml`, and stores them in the repo.
3. Plaintext key files are gitignored; only `.age` files are committed.
4. The hub replacement runbook (`docs/runbooks/hub-replacement.md`) Runbook B references the encrypted key location.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | 52cf8b1 | Created from SPIKE-007 recommendations; skipped Draft (criteria defined during research) |
