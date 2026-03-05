---
title: "SPIKE-011: Cross-Platform CI Scope"
artifact: SPIKE-011
status: Complete
author: cristos
created: 2026-03-04
last-updated: 2026-03-05
question: "Which make check targets can run in CI without the age private key, and what does macOS GitHub Actions runner availability and cost look like?"
gate: Pre-implementation
risks-addressed:
  - STORY-011 CI scope — which checks are feasible without secrets, and macOS runner cost/availability
depends-on: []
linked-research:
  - EPIC-004
---

# SPIKE-011: Cross-Platform CI Scope

## Question

Two intertwined questions block STORY-011:

1. **Check scope:** Which `make check` targets (YAML lint, ansible-lint, variable resolution, role dependency validation) can run without the age private key? STORY-011 AC #4 requires no secrets in CI, so any check that touches SOPS-encrypted files must be excluded or stubbed.

2. **macOS runner cost:** GitHub Actions macOS runners are billed at a higher rate than Linux. Is the cost acceptable for this repo's push/PR frequency, or should macOS checks be limited to a weekly schedule or manual trigger?

## Go / No-Go Criteria

**Go (CI is feasible and affordable):**
- At least 3 of the 4 target checks (YAML syntax, ansible-lint, variable resolution, role deps) pass without secrets
- macOS runner cost at current push frequency is under $10/month (or free tier covers it)
- A working GitHub Actions workflow can be prototyped in under 2 hours

**No-Go (CI is not worth the cost/complexity):**
- Most meaningful checks require decrypted secrets (variable resolution fails on encrypted values)
- macOS runner costs exceed $20/month at current frequency
- The checks that can run without secrets are too shallow to catch real cross-platform issues

## Pivot Recommendation

If no-go on secrets scope: Create a `make check-ci` target that explicitly skips SOPS-dependent checks and validates only structure, syntax, and lint. Accept reduced coverage.

If no-go on macOS cost: Run macOS checks only on `workflow_dispatch` (manual trigger) or weekly schedule, not on every push. Linux checks run on every push.

## Findings

**Decision: GO — all 8 check targets work without secrets**

### Check-by-check analysis

| Target | Requires age key? | Why not? | CI dependencies |
|--------|------------------|----------|----------------|
| `shellcheck` | No | Pure static analysis | shellcheck |
| `yamllint` | No | Syntax-only validation | yamllint (pip) |
| `ansible-lint` | No | `ANSIBLE_VARS_ENABLED=host_group_vars` disables SOPS plugin | ansible-lint, ansible |
| `check-collisions` | No | Compares filenames, not contents | bash, find |
| `check-sync` | No | Diffs plaintext VSCode configs between platforms | bash, diff |
| `check-playbook` | No | `--syntax-check` + SOPS plugin disabled | ansible |
| `test-bats` | No | Tests use fake key files in temp dirs | bats-core |
| `test-python` | No | All SOPS/age operations mocked via `MagicMock` | uv, Python packages |

The codebase was engineered for secretless CI: `ANSIBLE_VARS_ENABLED=host_group_vars` is already baked into the Makefile, `scripts/lint.sh` documents the rationale, and the test suite mocks all crypto operations.

### macOS GitHub Actions runner cost

| Runner | Per-minute rate | Minute multiplier |
|--------|----------------|-------------------|
| Linux 2-core | $0.006/min | 1x |
| macOS 3-core (M1) | $0.062/min | 10x |

**Free tier:** GitHub Free plan includes 2,000 minutes/month. The 10x multiplier gives ~200 effective macOS minutes/month.

**Estimated usage at ~30 pushes/month:**
- Linux every push: 30 x 5 min = 150 quota minutes (free)
- macOS weekly: 4 x 5 min = 200 quota minutes (free)
- Total: 350 quota minutes — comfortably within free tier

If the repo is public, GitHub Actions is completely free with no minute limits.

### Recommended CI architecture

1. **Linux runner (every push/PR):** Full `make check` — all 8 targets. Free.
2. **macOS runner (weekly schedule + manual dispatch):** Same suite, catches platform-specific issues. Free within budget.
3. **No `make check-ci` target needed** — existing `make check` works unmodified in CI.

### Pivot not needed

The spike anticipated needing a `make check-ci` target to skip SOPS-dependent checks. This is unnecessary — no check depends on SOPS or the age key.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | ea363f7 | Unblocks STORY-011 design; attached to EPIC-004 |
| Complete | 2026-03-05 | 0f73e40 | GO — all 8 check targets work without secrets; Linux every push + macOS weekly |
