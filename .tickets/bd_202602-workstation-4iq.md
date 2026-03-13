---
id: bd_202602-workstation-4iq
status: closed
deps: []
links: []
created: 2026-03-06T04:22:49Z
type: bug
priority: 2
external-ref: BUG-001
---
# Fix BUG-001: SwiftBar start on login

SwiftBar is not configured to launch on login. The backup staleness watcher widget only appears when SwiftBar is manually started. Need to add SwiftBar to login items (launchd plist or macOS Login Items).


