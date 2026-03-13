---
id: bd_202602-workstation-5dz.2
status: closed
deps: []
links: []
created: 2026-03-03T17:29:03Z
type: task
priority: 2
---
# Test Unison/wsync behavior during hub outage

Investigate Unison behavior when hub is unreachable: wsync retry/error handling, archive file validity after hub replacement, hostname change impact on profiles, and whether profile regeneration is needed vs a config update.

## Notes

FINDINGS SUMMARY:
- wsync fails gracefully during outage, retries every 5 min via timer (no backoff, no crash loop)
- Archive files in ~/.unison/ on both spoke and hub (ar*, fp*, sc*, tm*, lk*)
- Hub replacement: archives invalidated (keyed to hostname+path hash), full rescan on first sync, automatic, no manual spoke intervention
- Hostname change: config update needed (WSYNC_HUB_HOST), profile regen NOT needed, archives invalidated (one-time rescan), rootalias can bridge
- Concurrent spoke edits: detected as conflict, prefer=newer auto-resolves by mtime, losing version preserved in backup
- Recovery time: 0-5 min (timer-driven only, no event-driven reconnection)
- Data integrity: no corruption risk — atomic-rename transfers, fingerprint verification, crash-resilient archives
- Key risk: concurrent edits on same file while hub is down → auto-resolved by mtime but could silently pick wrong version (MEDIUM risk)


