---
id: bd_202602-workstation-e6d.1
status: closed
deps: []
links: []
created: 2026-03-03T16:07:51Z
type: task
priority: 1
---
# Expand wsync_discover_repos() for multi-directory

Modify wsync to: 1) Read ~/.config/wsync/detected-repos journal, 2) Read WSYNC_EXTRA_DIRS or ~/.config/wsync/extra-dirs, 3) Deduplicate, 4) Return repos with qualified names.


