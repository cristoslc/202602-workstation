---
id: bd_202602-workstation-5dz.5
status: closed
deps: []
links: []
created: 2026-03-03T17:29:10Z
type: task
priority: 2
---
# Design automation for hub failover and migration

Evaluate automation opportunities: (1) make hub-migrate SOURCE=old DEST=new scripted migration, (2) Ansible playbook for hub failover (provision, update group_vars, re-run spoke configure), (3) Monitoring heartbeat check that alerts before users notice.

## Notes

FINDINGS SUMMARY:
Three automation components designed, all recommended to build:

1. make hub-migrate (scripts/hub-migrate.sh) - MEDIUM effort (3-4h)
   - Pre-stage rsync, interactive cutover gate, final delta, key copy, verification
   - Makefile targets: hub-migrate, hub-migrate-dry, hub-backup-keys
   - Age-encrypt hub keys to repo for disaster recovery

2. Ansible hub playbook (infra/hub/) - MEDIUM effort (3-4h)
   - New hub inventory, playbook, ansible.cfg
   - Key injection tasks for same-ID migration (-e syncthing_hub_inject_keys=true)
   - Makefile targets: hub-provision, hub-restore
   - Spoke re-config via existing make apply ROLE=syncthing/unison

3. Hub monitoring (shared/roles/sync-monitor/) - SMALL-MEDIUM effort (2-3h)
   - Follows backup staleness-watcher pattern exactly
   - Checks: Syncthing TCP, SSH connectivity
   - Debounce: 3 consecutive failures (30 min) before alerting
   - Desktop notification + Shoutrrr alerts
   - Deployed via sync phase, runs on spokes

BUILD ORDER: monitoring first (simplest, immediate value) -> Ansible playbook -> migration script
TOTAL: 8-11 hours


