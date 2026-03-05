---
title: "STORY-008: Ansible Failure Summary Panel"
artifact: STORY-008
status: Implemented
author: cristos
created: 2026-03-03
last-updated: 2026-03-05
parent-epic: EPIC-004
related:
  - JOURNEY-001
depends-on: []
---

# STORY-008: Ansible Failure Summary Panel

**As a** multi-machine developer, **I want** the TUI to show a clear summary of failed Ansible tasks after provisioning, **so that** I can quickly identify and fix problems without scrolling through the full Ansible output.

## Context

JOURNEY-001 documents "Ansible error messages are hard to parse in the TUI" as a Frustrated (score 2) pain point. When a task fails mid-phase, the error is in Ansible's verbose output format, buried in scrollback. A post-run summary panel showing only failed tasks with their error messages and retry options would dramatically improve the error-handling experience.

## Acceptance Criteria

1. After Ansible provisioning completes (success or failure), the TUI displays a summary panel showing the count of ok/changed/failed/skipped tasks.
2. If any tasks failed, the summary lists each failed task with its role name, task name, and error message.
3. Failed tasks are displayed in a scannable format (not raw Ansible JSON output).
4. The summary includes a "Retry failed phases" option that re-runs only the phases containing failures.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | ad25d92 | Created from JOURNEY-001 pain point; scope is well-defined TUI enhancement |
| Implemented | 2026-03-05 | 19c087c | All ACs met by existing AnsibleOutputParser + _render_ansible_summary() + retry button |
