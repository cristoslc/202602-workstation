---
title: "STORY-003: Hub Migration Automation"
artifact: STORY-003
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
related:
  - JOURNEY-003
depends-on:
  - STORY-001
---

# STORY-003: Hub Migration Automation

**As a** multi-machine developer, **I want** scripted hub migration and an Ansible hub playbook with key injection, **so that** I can migrate or restore the hub server with a single command instead of following a multi-page manual runbook.

## Context

SPIKE-007 designed two automation components: a `make hub-migrate` script for planned migrations (pre-stage rsync, interactive cutover gate, verification) and an Ansible hub playbook (`infra/hub/`) with key injection support for same-ID emergency recovery. Together they reduce planned migration to ~15 minutes operator time and emergency recovery to a single command.

## Acceptance Criteria

1. `scripts/hub-migrate.sh` exists and implements the three-phase migration: pre-stage rsync, interactive cutover gate, final delta + key copy + verification.
2. `make hub-migrate SOURCE=<old> DEST=<new>` and `make hub-migrate-dry SOURCE=<old> DEST=<new>` targets invoke the script.
3. An Ansible hub playbook at `infra/hub/hub.yml` with inventory and config provisions a hub from scratch, optionally injecting existing keys via `-e syncthing_hub_inject_keys=true -e syncthing_hub_key_source=<path>`.
4. `make hub-provision HUB_HOST=<host>` and `make hub-restore HUB_HOST=<host> KEY_DIR=<path>` targets invoke the playbook.
5. Key injection stops Syncthing before replacing keys and restarts after, preserving the device ID.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | 52cf8b1 | Created from SPIKE-007 recommendations; skipped Draft (design completed during research). Depends on STORY-001 (key backup) for the restore flow. |
| Implemented | 2026-03-03 | 3301fe2 | hub-migrate.sh, infra/hub/ Ansible structure, inject-keys.yml, Makefile targets |
