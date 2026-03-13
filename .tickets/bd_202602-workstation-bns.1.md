---
id: bd_202602-workstation-bns.1
status: closed
deps: []
links: []
created: 2026-03-03T19:39:55Z
type: task
priority: 2
---
# Create sync-monitor role structure

Create shared/roles/sync-monitor/ with defaults/main.yml, tasks/main.yml, templates/, handlers/main.yml. Defaults: hub address from syncthing_hub_address, SSH from unison_hub_host, 10-min interval, 3-failure threshold, 60-min staleness.


