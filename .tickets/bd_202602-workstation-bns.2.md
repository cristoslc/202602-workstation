---
id: bd_202602-workstation-bns.2
status: closed
deps: []
links: []
created: 2026-03-03T19:39:55Z
type: task
priority: 2
---
# Write health-check script template

Create templates/sync-health-check.sh.j2. TCP check on port 22000 (Syncthing), SSH check (Unison). Failure counter with state file. Desktop notification (notify-send/osascript) + Shoutrrr on threshold breach. Follow backup-staleness-check.sh pattern.


