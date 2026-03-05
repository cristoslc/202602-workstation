---
title: "STORY-010: Auto-Propagation on Login"
artifact: STORY-010
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
related:
  - JOURNEY-002
depends-on: []
---

# STORY-010: Auto-Propagation on Login

**As a** multi-machine developer, **I want** configuration changes to propagate to other machines on login via an automatic pull-and-apply hook, **so that** I don't have to remember to manually `git pull && make apply` on each machine.

## Context

JOURNEY-002 documents "no push-based propagation; must manually pull + apply on each machine" as a Frustrated (score 2) pain point. A shell login hook or launchd/systemd timer that runs `git pull --ff-only && make apply` on the workstation repo would automate propagation. Design considerations include: handling merge conflicts gracefully, avoiding long apply runs blocking login, and running only when the repo has upstream changes.

## Acceptance Criteria

1. A login hook (shell profile or launchd/systemd agent) checks for upstream changes to the workstation repo.
2. If fast-forward changes are available, the hook pulls and runs `make apply` in the background.
3. The hook does not block interactive login — it runs asynchronously and notifies on completion.
4. If `git pull --ff-only` fails (diverged branches), the hook logs a warning and skips the apply.
5. The hook is deployed via an Ansible role and can be disabled per-machine.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | ad25d92 | Created from JOURNEY-002 pain point; design requires careful handling of async execution and failure modes |
| Implemented | 2026-03-05 | e47a69e | propagate.sh + launchd/systemd templates + propagation Ansible role |
