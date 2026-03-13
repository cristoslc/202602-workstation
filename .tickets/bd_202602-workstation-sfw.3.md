---
id: bd_202602-workstation-sfw.3
status: closed
deps: []
links: []
created: 2026-03-03T19:40:02Z
type: task
priority: 2
---
# Add key injection tasks to syncthing-hub role

Create shared/roles/syncthing-hub/tasks/inject-keys.yml. Stops Syncthing, copies cert.pem+key.pem from syncthing_hub_key_source, fixes ownership/perms, restarts. Conditional on syncthing_hub_inject_keys=true.


