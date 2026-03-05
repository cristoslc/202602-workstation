---
title: "SPIKE-009: 1Password Bootstrap Timing"
artifact: SPIKE-009
status: Complete
author: cristos
created: 2026-03-04
last-updated: 2026-03-05
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

**Decision: GO (conditional)**

### No circular dependency exists

The bootstrap dependency chain is strictly linear:

1. **Prereqs** — Install Homebrew, `age`, `sops` (no secrets needed)
2. **Ansible Phase 0** — Homebrew role only (no secrets needed)
3. **Ansible Phase 1** — `secrets-manager` role:
   - Installs 1Password CLI via `homebrew_cask` (`onepassword.yml`)
   - Checks for age key on disk
   - Tries `op read "op://Private/age-key/private-key"` (non-fatal on failure)
   - Decrypts SOPS trees (`decrypt-tree.yml`)
4. **Phases 2-3** — Dev tools, Desktop (no secrets consumed)
5. **Phase 4** — `stow` role consumes `.decrypted/` dotfiles (guards with conditional, skips if absent)

Confirmed via grep: zero references to `.decrypted/` or `SOPS_AGE` in Phases 0-3 play files.

### The code already supports this flow

`secrets-manager/tasks/sops.yml` (lines 56-71) checks `op --version` before attempting `op read`, and treats failure as non-fatal. The TUI prereqs step (`scripts/setup_tui/lib/prereqs.py`, line 105) installs `sops`, `age`, `stow`, `rsync` but does **not** currently install `1password-cli`. The `shared/lib/wizard.sh` (line 129) checks `command -v op` and silently falls through when absent.

### op authentication on fresh machines

Three authentication methods exist:

| Method | Interactive? | Private vault access? | Viable? |
|--------|-------------|----------------------|---------|
| Desktop app integration (biometric) | One sign-in, then Touch ID | Yes | **Yes** |
| `op account add` + `op signin` | Fully interactive (email, secret key, password) | Yes | No — too manual |
| Service account (`OP_SERVICE_ACCOUNT_TOKEN`) | Non-interactive | **No** — cannot access Private vaults | No |

**Conditional:** On a truly fresh machine, user must sign into the 1Password desktop app once before `op read` works. This is unavoidable (1Password security model) but is a major improvement — no second machine needed, just sign into 1Password (something the user would do anyway).

### Recommended implementation for STORY-007

1. **Add `1password-cli` to TUI prereqs step** — gives the pre-Ansible "Resolve age key" screen the ability to offer `op read` earlier.
2. **No two-pass bootstrap needed** — existing single-pass with graceful fallback is sufficient.
3. **Do not use service accounts** — they cannot access the Private vault.
4. **Accept the one-time manual sign-in** — document it in the bootstrap guide.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | ea363f7 | Unblocks STORY-007 design; attached to EPIC-004 |
