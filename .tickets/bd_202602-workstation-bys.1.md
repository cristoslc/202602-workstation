---
id: bd_202602-workstation-bys.1
status: closed
deps: []
links: []
created: 2026-03-03T16:07:20Z
type: task
priority: 2
---
# Create git-repo-scanner Ansible role

Create shared/roles/git-repo-scanner/ with: tasks/main.yml, tasks/debian.yml (install fswatch, deploy systemd units), tasks/darwin.yml (install fswatch via Homebrew, deploy launchd agents), files/ for scanner script and service units.


