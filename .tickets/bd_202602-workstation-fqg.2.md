---
id: bd_202602-workstation-fqg.2
status: closed
deps: []
links: []
created: 2026-03-03T13:06:17Z
type: task
priority: 2
assignee: Cristos L-C
---
# Create Syncthing hub-server Ansible role

New role shared/roles/syncthing-hub/ (or extend existing syncthing role with hub mode). Installs Syncthing on hub, initializes config, exposes device ID as Ansible fact, pre-creates folder IDs for user data folders. Hub runs headless.


