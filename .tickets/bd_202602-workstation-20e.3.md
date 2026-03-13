---
id: bd_202602-workstation-20e.3
status: closed
deps: []
links: []
created: 2026-03-05T03:01:30Z
type: task
priority: 2
---
# Add tests for parametric date/time conversion

Add test cases to tests/python/test_raycast_to_espanso.py covering: parametric {date format="yyyy-MM-dd"}, {date format="yyyy-MM-dd HHmm"}, {date format="'GMT'Z"}, mixed parametric + simple placeholders, format strings with literal text in quotes, and edge cases (unknown tokens pass through). Verify Espanso YAML output includes correct date extension vars.


