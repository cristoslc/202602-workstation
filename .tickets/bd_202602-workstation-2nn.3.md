---
id: bd_202602-workstation-2nn.3
status: closed
deps: []
links: []
created: 2026-03-06T05:42:07Z
type: task
priority: 2
---
# Implement dirty repo transfer via rsync

For repos with uncommitted changes or stashes, use rsync to transfer the entire working tree preserving state. Use --partial for resumability.


