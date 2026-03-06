---
title: "BUG-001: SwiftBar Should Start on Login"
artifact: BUG-001
status: Verified
author: cristos
created: 2026-03-05
last-updated: 2026-03-06
severity: low
affected-artifacts:
  - EPIC-001
discovered-in: "Manual observation — SwiftBar backup staleness widget not running after reboot"
fix-ref: "bd_202602-workstation-4iq"
---

# BUG-001: SwiftBar Should Start on Login

## Description

SwiftBar is not configured to launch automatically on login. The backup staleness watcher widget only appears when SwiftBar is manually started, defeating the purpose of background monitoring.

## Reproduction Steps

1. Reboot or log out and back in
2. Check menu bar for SwiftBar backup status widget
3. Widget is absent — SwiftBar is not running

## Expected Behavior

SwiftBar launches automatically on login and displays the backup staleness widget in the menu bar.

## Actual Behavior

SwiftBar does not start on login. The backup staleness widget is only available after manually launching SwiftBar.

## Impact

Backup staleness alerts are invisible until SwiftBar is manually started, which undermines the "zero manual configuration" goal of EPIC-001. Low severity because backups still run — only the monitoring widget is affected.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Reported | 2026-03-05 | 10eac63 | Initial report |
| Fixed | 2026-03-05 | fbdddc4 | Added open -a SwiftBar to Ansible backups role |
