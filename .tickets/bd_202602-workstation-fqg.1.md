---
id: bd_202602-workstation-fqg.1
status: closed
deps: []
links: []
created: 2026-03-03T13:06:17Z
type: task
priority: 2
---
# Automate Syncthing device pairing via REST API

Replace manual GUI device-pairing steps in syncthing/tasks/configure.yml with Ansible uri module calls to Syncthing REST API. Must: add hub device, share folders, accept on hub, set Send & Receive. Requires API key from Syncthing config.xml.


