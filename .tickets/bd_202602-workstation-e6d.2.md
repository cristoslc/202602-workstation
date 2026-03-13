---
id: bd_202602-workstation-e6d.2
status: closed
deps: []
links: []
created: 2026-03-03T16:07:53Z
type: task
priority: 1
---
# Implement qualified naming scheme for hub directories

Repos from WSYNC_CODE_DIR use basename as-is. Other repos use parent--basename format (e.g., documents--HouseOps). Update wsync_get_repo_name() and hub path computation.


