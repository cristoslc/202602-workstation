---
id: bd_202602-workstation-4iq.1
status: closed
deps: []
links: []
created: 2026-03-06T04:22:54Z
type: task
priority: 2
assignee: Cristos L-C
---
# Investigate SwiftBar launch mechanism

Determine how SwiftBar should be configured to start on login — Login Items via System Settings, a LaunchAgent plist, or the app's own preferences. Check if the Ansible backups role already handles this.

## Notes

Findings: SwiftBar IS in macOS Login Items and running. No defaults-based LaunchAtLogin key — SwiftBar uses macOS SMAppService (modern login item API). The app auto-registers as a login item when first opened. Fix: add 'open -a SwiftBar' task to the Ansible backups role (same pattern as Syncthing/Ollama/Hammerspoon) so fresh bootstraps trigger the registration.


