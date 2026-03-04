---
title: "SPIKE-011: Cross-Platform CI Scope"
artifact: SPIKE-011
status: Planned
author: cristos
created: 2026-03-04
last-updated: 2026-03-04
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

_Pending investigation._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-04 | _pending_ | Unblocks STORY-011 design; attached to EPIC-004 |
