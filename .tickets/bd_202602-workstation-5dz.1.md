---
id: bd_202602-workstation-5dz.1
status: closed
deps: []
links: []
created: 2026-03-03T17:29:01Z
type: task
priority: 2
---
# Test Syncthing spoke behavior during hub outage

Investigate and test what happens to Syncthing spokes when the hub goes down: local change queuing, version vector behavior on reconnect, .sync-conflict-* file generation after extended outage, and autoAcceptFolders interaction with a new hub device ID.

## Notes

FINDINGS SUMMARY:
- Local change queuing: CONFIRMED — spokes fully queue changes in local index DB, no data lost during downtime
- Version vectors: no risk of rollback — delta index exchange on reconnect sends only new changes, clock-based versioning prevents silent overwrites
- Conflict generation: conflicts ARE more likely during outage IF two spokes edit the SAME file (concurrent vectors), but LOW risk for this project's sequential-machine usage pattern. Conflicts are detectable (.sync-conflict-* files), not silent
- autoAcceptFolders with new device ID: requires spoke reconfiguration (new device ID in group_vars + Ansible re-run). Preserving cert.pem/key.pem avoids this entirely
- Reconnection: spokes reconnect within 0-60 seconds (reconnectionIntervalS default 60s). No thundering herd at 2-3 spokes. syncthing-resume.sh forces immediate reconnect on Linux wake
- Data integrity: NO corruption risk — block-level SHA-256 verification, atomic writes via temp files, LevelDB crash recovery. In-flight transfers safely resumed
- KEY RISK: hub cert.pem and key.pem must be backed up for transparent replacement
- GO/NO-GO: PASS — automatic resume < 60s, no data loss, no corruption


