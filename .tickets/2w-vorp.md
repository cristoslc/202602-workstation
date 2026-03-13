---
id: 2w-vorp
status: closed
deps: []
links: []
created: 2026-03-13T05:06:58Z
type: task
priority: 2
assignee: cristos
parent: 2w-wkka
tags: [spec:SPEC-006]
---
# Add SteamOS detection to Makefile

Detect SteamOS via /etc/os-release ID=steamos; set PLATFORM_DIR=steamos.


## Notes

**2026-03-13T05:08:26Z**

Added SteamOS detection: IS_STEAMOS=, sets PLATFORM_DIR=steamos before linux fallback.
