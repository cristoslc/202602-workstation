---
title: "EPIC-004: Platform Developer Experience"
artifact: EPIC-004
status: Proposed
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-vision: VISION-001
success-criteria:
  - Bootstrap age key transfer requires zero coordination with another machine
  - Ansible provisioning failures are surfaced in a human-readable summary, not buried in scrollback
  - Adding a new role requires only a name — boilerplate is generated
  - Configuration changes propagate to other machines without manual pull + apply
  - Cross-platform regressions are caught before they reach another machine
depends-on: []
---

# EPIC-004: Platform Developer Experience

## Goal / Objective

Eliminate the highest-friction pain points identified across JOURNEY-001 (Fresh Machine Bootstrap) and JOURNEY-002 (Configuration Evolution). These two journeys document the core loops of using the workstation-as-code system — initial setup and ongoing iteration — and both have unaddressed "Frustrated" (score 2) pain points that erode the "single command" and "just works" promises of VISION-001.

## Scope Boundaries

**In scope:**
- Age key retrieval from 1Password (eliminating manual key transfer during bootstrap)
- Ansible failure summarization in the TUI (human-readable error panel)
- Role scaffolding generator (`make new-role`)
- Auto-propagation of config changes on login (pull-and-apply hook)
- Cross-platform CI (GitHub Actions lint + syntax on macOS + Linux)

**Out of scope:**
- Headless settings import (Raycast/Stream Deck) — owned by EPIC-003 (STORY-006)
- Data migration improvements — owned by EPIC-002 (STORY-004, STORY-005)
- Sync infrastructure — owned by EPIC-002
- TUI redesign beyond error summarization

## Child Stories

| ID | Title | Journey | Pain point |
|----|-------|---------|------------|
| STORY-007 | 1Password Age Key Retrieval | JOURNEY-001 | Age key transfer requires coordination |
| STORY-008 | Ansible Failure Summary Panel | JOURNEY-001 | Ansible errors are hard to parse in TUI |
| STORY-009 | Role Scaffolding Generator | JOURNEY-002 | Cross-platform authoring burden |
| STORY-010 | Auto-Propagation on Login | JOURNEY-002 | Manual pull + apply on each machine |
| STORY-011 | Cross-Platform CI | JOURNEY-002 | Blind-authored tasks untested until used |

## Research Spikes

| ID | Title | Question | Unblocks |
|----|-------|----------|----------|
| SPIKE-009 | [1Password Bootstrap Timing](../../research/Planned/(SPIKE-009)-1Password-Bootstrap-Timing/(SPIKE-009)-1Password-Bootstrap-Timing.md) | Can `op` retrieve the age key before SOPS decryption? | STORY-007 |
| SPIKE-010 | [Login-Hook Propagation Mechanism](../../research/Planned/(SPIKE-010)-Login-Hook-Propagation-Mechanism/(SPIKE-010)-Login-Hook-Propagation-Mechanism.md) | launchd vs shell hook vs systemd timer? | STORY-010 |
| SPIKE-011 | [Cross-Platform CI Scope](../../research/Planned/(SPIKE-011)-Cross-Platform-CI-Scope/(SPIKE-011)-Cross-Platform-CI-Scope.md) | Which checks work without secrets? macOS runner cost? | STORY-011 |

## Key Dependencies

None — this epic addresses platform DX gaps independent of the sync and backup epics.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-03 | ad25d92 | Created to own JOURNEY-001/002 pain points that had no parent epic |
