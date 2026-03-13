---
title: "BUG-003: LinNote Build Fails — libkf6windowsystem-dev Unavailable"
artifact: BUG-003
status: Fixed
author: cristos
created: 2026-03-13
last-updated: 2026-03-13
severity: high
affected-artifacts: []
discovered-in: "Ansible bootstrap failure — shared/roles/notes/tasks/linnote.yml:14, 2026-03-13"
fix-ref: ""
---

# BUG-003: LinNote Build Fails — libkf6windowsystem-dev Unavailable

## Description

The LinNote build dependency task in `shared/roles/notes/tasks/linnote.yml` fails because `libkf6windowsystem-dev` (KDE Framework 6) is not available in the package repositories on Linux Mint 22.3 (Ubuntu 24.04 / Noble base). Only KF5 packages (`libkf5windowsystem-dev`) are available. This is a fatal failure that aborts the entire bootstrap playbook.

## Reproduction Steps

1. Run `./bootstrap.sh` on a Linux Mint 22.3 (or Ubuntu 24.04) system
2. The playbook reaches `notes : Install LinNote build dependencies`
3. `apt` fails with: `No package matching 'libkf6windowsystem-dev' is available`
4. Bootstrap aborts — 206 tasks pass, 1 fatal failure

## Expected Behavior

LinNote build dependencies install successfully using packages available in the distro's repositories.

## Actual Behavior

Fatal error at `linnote.yml:14` — the KF6 package does not exist in Ubuntu 24.04 / Mint 22.3 repos. The entire bootstrap run is aborted.

## Impact

High severity — this is a hard failure that prevents the bootstrap playbook from completing. All tasks after the notes role are skipped. The fix is straightforward (use KF5 equivalent), but the blast radius is the entire provisioning run.

## Root Cause

Ubuntu 24.04 (Noble) ships KDE Frameworks 5, not KDE Frameworks 6. The `libkf6windowsystem-dev` package requires KF6 repos which are not available by default. The KF5 equivalent (`libkf5windowsystem-dev`) provides the same `KWindowSystem` library and is available in the standard repos.

## Fix

Replace `libkf6windowsystem-dev` with `libkf5windowsystem-dev` in `shared/roles/notes/tasks/linnote.yml`.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Reported | 2026-03-13 | _pending_ | Initial report from bootstrap.log failure |
| Fixed | 2026-03-13 | _pending_ | Replaced libkf6windowsystem-dev with libkf5windowsystem-dev |
