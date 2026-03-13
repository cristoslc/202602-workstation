---
id: bd_202602-workstation-4xe.1
status: closed
deps: []
links: []
created: 2026-03-12T05:44:17Z
type: task
priority: 2
---
# Fix sync-monitor Jinja2 template escape

The {# in ${#ERRORS[@]} was interpreted as Jinja2 comment start. Fixed by escaping with {{ '{#ERRORS[@]}' }}.


