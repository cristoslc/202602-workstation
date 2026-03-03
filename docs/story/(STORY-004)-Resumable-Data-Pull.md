---
title: "STORY-004: Resumable Data Pull"
artifact: STORY-004
status: Ready
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
related:
  - JOURNEY-003
depends-on: []
---

# STORY-004: Resumable Data Pull

**As a** multi-machine developer, **I want** `make data-pull` to resume interrupted transfers from where they left off, **so that** I don't have to restart hours-long data migrations when the network drops or a machine sleeps.

## Context

JOURNEY-003 documents "large data transfers take hours with no resume-on-disconnect" as a Frustrated (score 2) pain point. The fix is straightforward: rsync's `--partial --partial-dir=.rsync-partial` flags retain partially transferred files, allowing seamless resume on reconnection.

## Acceptance Criteria

1. `scripts/data-pull.sh` uses `--partial --partial-dir=.rsync-partial` in its rsync invocation.
2. An interrupted `make data-pull` can be re-run and resumes from where it stopped, without re-transferring completed files.
3. The `.rsync-partial` directory is cleaned up automatically after a successful transfer.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | ad25d92 | Created from JOURNEY-003 pain point; skipped Draft (trivial scope) |
