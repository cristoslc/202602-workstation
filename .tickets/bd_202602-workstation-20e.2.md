---
id: bd_202602-workstation-20e.2
status: closed
deps: []
links: []
created: 2026-03-05T03:01:27Z
type: task
priority: 2
---
# Parse parametric {date format="..."} placeholders

Add regex-based parsing in _convert_text() to match parametric Raycast date placeholders like {date format="yyyy-MM-dd"} and {time format="HH:mm"}. Extract the format string, translate it via the ICU-to-strftime translator, and emit Espanso date extension vars. Must coexist with existing simple-form ({date}, {time}) handling.


