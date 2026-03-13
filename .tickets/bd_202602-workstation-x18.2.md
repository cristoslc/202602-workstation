---
id: bd_202602-workstation-x18.2
status: closed
deps: []
links: []
created: 2026-03-11T17:16:13Z
type: task
priority: 2
---
# Consolidate bat/cat alias with conditional

Replace duplicated cat aliases in macos.zsh (bat) and linux.zsh (batcat) with a single shared alias using conditional: if bat exists use bat, elif batcat exists use batcat. Remove from platform files.


