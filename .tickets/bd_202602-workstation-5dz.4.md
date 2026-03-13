---
id: bd_202602-workstation-5dz.4
status: closed
deps: []
links: []
created: 2026-03-03T17:29:08Z
type: task
priority: 2
---
# Document hub replacement runbook

Write a step-by-step runbook for permanent hub replacement: provision new hub, re-pair all spokes, verify sync. Target: spoke re-pairing < 30 minutes for 3 devices. Must cover both Syncthing and Unison.

## Notes

RUNBOOK COMPLETE - Three variants:

Runbook A: Planned Migration (same device ID, pre-staged)
  - Pre-rsync while old hub running, interactive cutover gate
  - Copy cert.pem + key.pem, final delta rsync, start new hub
  - Spoke re-pairing: 0 min (same device ID = auto-reconnect)
  - Total downtime: 5-15 min
  - Rollback: stop new hub, start old hub

Runbook B: Emergency Replacement (keys from backup)
  - Provision new hub via Ansible, restore keys from backup
  - Reconfigure via REST API, trigger spoke reconnection
  - Total: 35-60 min (hub online), data re-sync in background
  - Requires hub key backup (currently NOT backed up)

Runbook C: Emergency Replacement (keys lost)
  - Provision new hub (new device ID generated)
  - Update syncthing_hub_device_id + address in SOPS secrets
  - Re-run make apply ROLE=syncthing on all spokes
  - Total: 45-70 min, data re-sync in background

KEY GAPS IDENTIFIED:
1. Hub keys not backed up (highest priority)
2. No hub-specific playbook
3. No key injection in syncthing-hub role
4. WSYNC_HUB_HOST not templated by Ansible


