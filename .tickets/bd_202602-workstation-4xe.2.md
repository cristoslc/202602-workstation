---
id: bd_202602-workstation-4xe.2
status: closed
deps: []
links: []
created: 2026-03-12T05:44:17Z
type: task
priority: 2
---
# Fix git-repo-scanner role path and handler

role_path traversal was off by one level (../../ instead of ../../../). Handler used unsupported block syntax — replaced with shell command.


