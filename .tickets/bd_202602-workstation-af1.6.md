---
id: bd_202602-workstation-af1.6
status: closed
deps: []
links: []
created: 2026-03-06T05:41:39Z
type: task
priority: 2
---
# Update Ansible raycast.yml for headless import

Update shared/roles/launchers/tasks/raycast.yml to use the headless import approach instead of open + pause. Remove the interactive_imports guard and pause task.


