---
title: "STORY-009: Role Scaffolding Generator"
artifact: STORY-009
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
related:
  - JOURNEY-002
depends-on: []
---

# STORY-009: Role Scaffolding Generator

**As a** multi-machine developer, **I want** `make new-role NAME=<name>` to generate a complete role skeleton with cross-platform structure, **so that** adding a new tool doesn't require remembering the boilerplate layout for defaults, tasks, platform includes, and verification.

## Context

JOURNEY-002 documents "cross-platform authoring requires knowing both platforms' install mechanisms" as a Frustrated (score 2) pain point. While the install mechanisms differ per-tool, the structural boilerplate is identical. A scaffolding generator would eliminate the friction of creating `defaults/main.yml`, `tasks/main.yml`, `tasks/darwin.yml`, `tasks/debian.yml`, and the verification task.

## Acceptance Criteria

1. `make new-role NAME=<name>` creates `shared/roles/<name>/` with the standard directory structure.
2. Generated files include: `defaults/main.yml`, `tasks/main.yml` (with platform dispatch), `tasks/darwin.yml`, `tasks/debian.yml`, and a verification task stub.
3. The generated `defaults/main.yml` includes the role enable toggle pattern (`<name>_enabled: true`).
4. Running the generator for an already-existing role name fails with a clear error (no overwrite).

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | ad25d92 | Created from JOURNEY-002 pain point; well-defined scope |
| Implemented | 2026-03-05 | _pending_ | scripts/new-role.sh + Makefile target; all 4 ACs verified |
