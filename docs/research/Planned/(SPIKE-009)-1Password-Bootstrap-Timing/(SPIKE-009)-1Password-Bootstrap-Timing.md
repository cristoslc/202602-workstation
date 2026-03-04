---
title: "SPIKE-009: 1Password Bootstrap Timing"
artifact: SPIKE-009
status: Planned
author: cristos
created: 2026-03-04
last-updated: 2026-03-04
question: "Can the 1Password CLI retrieve the age decryption key early enough in setup.sh to unblock SOPS secret decryption, or does a two-pass bootstrap flow need to be designed?"
gate: Pre-implementation
risks-addressed:
  - STORY-007 chicken-and-egg timing — op CLI installed in Phase 1 but secrets needed before Phase 1 completes
depends-on: []
linked-research:
  - EPIC-004
---

# SPIKE-009: 1Password Bootstrap Timing

## Question

Can the 1Password CLI (`op`) retrieve the age decryption key early enough in `setup.sh` to unblock SOPS secret decryption, or does a two-pass bootstrap flow need to be designed?

The current bootstrap sequence is:
1. Phase 0: Xcode CLT + Homebrew
2. Phase 1: Homebrew packages (including `op` and `age`)
3. Phase 2: Secrets decryption (requires age key)
4. Phase 3+: Ansible provisioning

STORY-007 assumes `op` is available after Phase 1, but the question is whether secrets decryption (Phase 2) can simply wait for Phase 1 to finish, or whether there are earlier dependencies on decrypted secrets that create a circular dependency.

## Go / No-Go Criteria

**Go (proceed with STORY-007 as designed):**
- `op` and `age` are both available after Phase 1 completes, before any SOPS decryption is attempted
- No Phase 0 or Phase 1 task requires a decrypted secret
- `op signin` can complete non-interactively (or with a single biometric prompt) on a fresh machine with 1Password installed

**No-Go (STORY-007 needs redesign):**
- Any Phase 0/1 task depends on a decrypted SOPS secret (circular dependency)
- `op signin` on a fresh machine requires a manual setup step that negates the automation benefit
- 1Password account setup on a new device requires access to another device (shifting, not eliminating, the coordination problem)

## Pivot Recommendation

If no-go: Design a two-pass bootstrap where Phase 1 completes without secrets, the user is prompted once for key transfer (existing methods), and Phase 2+ proceeds. 1Password retrieval becomes an optional convenience for subsequent re-bootstraps rather than the primary path.

## Findings

_Pending investigation._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | ea363f7 | Unblocks STORY-007 design; attached to EPIC-004 |
