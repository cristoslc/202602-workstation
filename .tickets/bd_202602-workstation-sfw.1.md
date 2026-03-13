---
id: bd_202602-workstation-sfw.1
status: closed
deps: []
links: []
created: 2026-03-03T19:40:01Z
type: task
priority: 2
---
# Create hub-migrate.sh script

Script implementing 3-phase migration: pre-stage rsync, interactive cutover gate, final delta + key copy + verification. Follow data-pull.sh conventions. Support --dry-run flag.


