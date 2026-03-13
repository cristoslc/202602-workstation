---
id: bd_202602-workstation-fqg.5
status: closed
deps: []
links: []
created: 2026-03-03T13:06:17Z
type: task
priority: 2
assignee: Cristos L-C
---
# Add explicit Syncthing wake-from-suspend trigger

Syncthing currently relies on passive reconnect after wake. Add explicit wake handler: systemd-sleep hook on Linux, sleepwatcher/launchd on macOS to restart Syncthing or trigger rescan.


