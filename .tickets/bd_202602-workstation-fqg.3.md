---
id: bd_202602-workstation-fqg.3
status: closed
deps: []
links: []
created: 2026-03-03T13:06:17Z
type: task
priority: 2
---
# Wire hub config variables into TUI and group_vars

Populate syncthing_hub_device_id, syncthing_hub_address, and unison_hub_host from TUI prompts or group_vars. Currently empty placeholders in defaults/main.yml for both roles. Must be set before bootstrap can configure spoke-to-hub connections.


