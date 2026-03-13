---
id: bd_202602-workstation-4xe.4
status: closed
deps: []
links: []
created: 2026-03-12T05:44:22Z
type: task
priority: 2
---
# Fix propagation role playbook_dir path

playbook_dir resolves to macos/plays/ in imported plays, not macos/. Changed ../ to ../../.


