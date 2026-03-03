---
title: "STORY-005: Code Repo Migration Tool"
artifact: STORY-005
status: Ready
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
related:
  - JOURNEY-003
depends-on: []
---

# STORY-005: Code Repo Migration Tool

**As a** multi-machine developer, **I want** a `make code-pull SOURCE=<host>` command that discovers repos on the source machine and transfers them preserving uncommitted state, **so that** I don't have to manually identify and handle each repo during machine migration.

## Context

JOURNEY-003 documents "no unified way to transfer repos with uncommitted work" as a Frustrated (score 2) pain point. SPEC-002/003 partially addressed this for repos in user data folders (auto-detected and synced via wsync), but there's still no single command for initial migration of repos from `~/code/` with dirty working trees. The tool should discover repos, detect which have uncommitted changes, and use git clone for clean repos / rsync or Unison for dirty ones.

## Acceptance Criteria

1. `scripts/code-pull.sh` exists and discovers git repos on the source machine via SSH.
2. Clean repos (no uncommitted changes, no stashes) are cloned fresh via `git clone`.
3. Dirty repos (uncommitted changes or stashes) are transferred preserving working tree state via rsync or Unison.
4. `make code-pull SOURCE=<host>` target invokes the script.
5. A summary report shows which repos were cloned vs. transferred and their status.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | — | Created from JOURNEY-003 pain point; partially addressed by SPEC-002/003 for user-data repos |
