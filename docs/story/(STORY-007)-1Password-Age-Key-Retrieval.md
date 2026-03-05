---
title: "STORY-007: 1Password Age Key Retrieval"
artifact: STORY-007
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
related:
  - JOURNEY-001
depends-on: []
---

# STORY-007: 1Password Age Key Retrieval

**As a** multi-machine developer, **I want** `setup.sh` to retrieve the age decryption key from 1Password automatically, **so that** bootstrapping a fresh machine doesn't require coordinating a key transfer from another device.

## Context

JOURNEY-001 documents "age key transfer requires coordination with another machine" as the single highest-friction step (score 2) in the entire bootstrap flow. The current options (Magic Wormhole, passphrase-encrypted export, manual SCP) all require another machine to be online or a passphrase to be remembered. Since 1Password is installed during Phase 1 (Homebrew), the CLI (`op`) could retrieve the key from a vault after the user authenticates once.

## Acceptance Criteria

1. `setup.sh` detects whether `op` (1Password CLI) is available after Phase 1 completes.
2. If `op` is available and the age key is not yet present, the script offers to retrieve it from 1Password.
3. The key is stored at `~/.config/sops/age/keys.txt` with correct permissions (600).
4. The existing key transfer methods (wormhole, export, SCP) remain available as fallbacks.
5. No plaintext key is ever written to a world-readable location.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | ad25d92 | Created from JOURNEY-001 pain point; requires 1Password CLI integration and chicken-and-egg timing investigation |
