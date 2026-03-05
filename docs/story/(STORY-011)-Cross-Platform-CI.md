---
title: "STORY-011: Cross-Platform CI"
artifact: STORY-011
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
related:
  - JOURNEY-002
depends-on: []
---

# STORY-011: Cross-Platform CI

**As a** multi-machine developer, **I want** a GitHub Actions workflow that runs lint and syntax checks on both macOS and Linux, **so that** I catch cross-platform regressions before they reach another machine.

## Context

JOURNEY-002 documents "blind-authored tasks for the other platform aren't tested until used" as a Frustrated (score 2) pain point. When the developer writes Linux tasks on a macOS machine (or vice versa), issues aren't discovered until the next use of the other platform. A CI workflow running `make check` on both platforms would catch YAML syntax errors, missing variables, and platform-specific task failures early. Design considerations include: macOS runner availability and cost, which checks to run (full apply is too expensive; lint + syntax + variable resolution is feasible), and handling encrypted secrets in CI.

## Acceptance Criteria

1. A GitHub Actions workflow runs on push to main and on pull requests.
2. The workflow runs on both macOS and Linux runners.
3. At minimum, the workflow validates: YAML syntax, Ansible lint, variable resolution (no undefined variables), and role dependency correctness.
4. The workflow does not require access to the age private key or SOPS secrets.
5. CI results are visible in the GitHub PR interface.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | ad25d92 | Created from JOURNEY-002 pain point; macOS runner cost and check scope need investigation |
| Implemented | 2026-03-05 | a17a7d2 | macOS + Linux matrix CI with schedule/dispatch triggers, all lint/syntax/test checks |
