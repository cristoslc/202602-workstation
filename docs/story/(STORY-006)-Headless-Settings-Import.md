---
title: "STORY-006: Headless Settings Import"
artifact: STORY-006
status: Draft
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-003
related:
  - JOURNEY-001
depends-on: []
---

# STORY-006: Headless Settings Import

**As a** multi-machine developer, **I want** Raycast and Stream Deck settings to import without interactive GUI confirmation dialogs, **so that** the entire bootstrap flow can run unattended.

## Context

JOURNEY-001 documents "Raycast and Stream Deck require interactive confirmation dialogs" as a Frustrated (score 2) pain point. iTerm2 already uses a headless approach (pointing preferences at a plist). If similar CLI or plist-manipulation approaches exist for Raycast and Stream Deck, the entire settings import stage could be non-interactive.

## Acceptance Criteria

1. Raycast settings are imported without requiring the user to switch to the Raycast app and click a confirmation dialog.
2. Stream Deck settings are restored without requiring the user to switch to the Stream Deck app and click a confirmation dialog.
3. The TUI's Import Settings screen completes all imports in sequence without user interaction.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-03 | ad25d92 | Created from JOURNEY-001 pain point; feasibility of headless import needs investigation |
