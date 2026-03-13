---
id: bd_202602-workstation-20e.1
status: closed
deps: []
links: []
created: 2026-03-05T03:01:24Z
type: task
priority: 2
---
# Add ICU-to-strftime format translator

Implement a function that translates Raycast/ICU/Java date format tokens (yyyy, MM, dd, HH, mm, etc.) to Python strftime codes (%Y, %m, %d, %H, %M). Must handle: longest-match token replacement (MMMM before MMM before MM), literal text in single quotes (e.g., 'GMT'), and pass-through of non-token characters (hyphens, spaces, colons).


