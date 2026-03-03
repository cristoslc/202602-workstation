---
title: "STORY-002: Hub Sync Monitor"
artifact: STORY-002
status: Ready
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
parent-epic: EPIC-002
related:
  - JOURNEY-004
depends-on: []
---

# STORY-002: Hub Sync Monitor

**As a** multi-machine developer, **I want** spoke-side monitoring that alerts me when the hub is unreachable, **so that** I discover sync outages before they cause problems rather than after I notice missing files.

## Context

SPIKE-007 identified "no hub monitoring" as a medium-severity gap. The design follows the existing backup staleness-watcher pattern (`shared/roles/backups/tasks/staleness-watcher.yml`): heartbeat file, threshold checking, desktop notification + Shoutrrr alerting, cross-platform timer deployment.

## Acceptance Criteria

1. A `sync-monitor` Ansible role exists at `shared/roles/sync-monitor/` that deploys a health-check script and timer (systemd on Linux, launchd on macOS).
2. The health check probes Syncthing TCP connectivity (port 22000) and SSH connectivity (for Unison) every 10 minutes.
3. Alerts fire only after 3 consecutive failures (30-minute debounce) to avoid noise from transient blips.
4. Alerts use desktop notification (notify-send / osascript) and optionally Shoutrrr (reusing `restic_shoutrrr_url` if configured).
5. `make apply ROLE=sync-monitor` deploys the monitor on a spoke.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Ready | 2026-03-03 | 52cf8b1 | Created from SPIKE-007 recommendations; skipped Draft (design completed during research) |
