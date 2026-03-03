---
title: "SPIKE-007: Hub Server Failover and Migration"
artifact: SPIKE-007
status: Planned
author: cristos
created: 2026-03-03
last-updated: 2026-03-03
question: "What operational procedures are needed to handle hub server outages (temporary and permanent) and planned migrations, and can these be automated?"
gate: Pre-MVP
risks-addressed:
  - "Single point of failure in hub-and-spoke topology (EPIC-002 risk table)"
  - "Hub server unavailable = no Syncthing sync, no Unison code sync"
depends-on:
  - SPIKE-006
---

# SPIKE-007: Hub Server Failover and Migration

## Question

The hub-and-spoke topology for both Syncthing and Unison creates a single point of failure. SPIKE-006 identified this risk and briefly mentioned dual-hub as a mitigation, but did not explore the operational procedures. This spike investigates:

1. **Temporary outage:** What happens to in-flight syncs when the hub goes down? How do spokes behave? How does reconnection and catch-up work? Is any data at risk?

2. **Permanent outage / hub replacement:** If the hub is lost, what's the procedure to provision a new one and re-pair all spokes? Can this be fully automated with the existing `syncthing-hub` role, or does it require manual intervention (device ID redistribution, folder re-sharing)?

3. **Planned migration:** Moving the hub to a new server (e.g., VPS provider change, hardware upgrade). What's the zero-downtime procedure? Can Syncthing and Unison data be migrated, or must spokes do a full re-sync?

## Go / No-Go Criteria

| Criterion | Pass | Fail |
|-----------|------|------|
| Temporary outage recovery | Syncthing and Unison resume automatically within 5 minutes of hub return; no data loss or corruption | Manual intervention required on spokes after hub returns |
| Hub replacement procedure | Documented runbook exists; spoke re-pairing takes < 30 minutes for 3 devices | Re-pairing requires manual GUI work on each spoke |
| Planned migration | Data can be moved to new hub without full re-sync; procedure is scripted | Full re-sync required (multi-day for large data sets) |

## Pivot Recommendation

If single-hub proves too fragile:
- **Dual-hub topology:** Both Syncthing and Unison connect to two hubs (home server + VPS). SPIKE-006 already noted this is viable for Syncthing. Investigate Unison dual-hub (round-robin or active-passive).
- **Spoke-to-spoke fallback:** For Syncthing, temporarily enable direct spoke connections when hub is unreachable. Adds conflict risk but eliminates downtime.

## Areas to Investigate

### Syncthing behavior during hub outage
- Do spokes queue changes locally? (Yes per Syncthing design, but verify)
- What happens to version vectors when hub reconnects?
- Are `.sync-conflict-*` files more likely after extended outage?
- How does `autoAcceptFolders` interact with a new hub device ID?

### Unison behavior during hub outage
- wsync currently logs errors and retries on next timer tick — is that sufficient?
- Are Unison archive files (`.unison/*.prf`, fingerprint caches) invalidated by hub replacement?
- Does changing the hub hostname require profile regeneration or just a config update?

### Hub data migration
- Syncthing: Can `/srv/syncthing/` be rsync'd to a new server and Syncthing started with the same device ID (by copying keys)?
- Unison: Can `/srv/code-sync/` be rsync'd? Are there server-side state files that need migration?
- Ansible: Does the `syncthing-hub` role handle reprovisioning idempotently?

### Automation opportunities
- `make hub-migrate SOURCE=old-hub DEST=new-hub` — scripted migration
- Ansible playbook for hub failover (provision new hub, update spoke group_vars, re-run spoke configure)
- Monitoring: heartbeat check that alerts before users notice

## Findings

_To be populated during Active phase._

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-03 | 3dccece | Initial creation |
