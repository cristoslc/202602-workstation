---
id: bd_202602-workstation-5dz.3
status: closed
deps: []
links: []
created: 2026-03-03T17:29:06Z
type: task
priority: 2
---
# Research hub data migration procedures

Determine migration procedures for: (1) Syncthing — can /srv/syncthing/ be rsync'd with same device ID by copying keys? (2) Unison — can /srv/code-sync/ be rsync'd, are there server-side state files? (3) Ansible — does syncthing-hub role handle reprovisioning idempotently?

## Notes

FINDINGS SUMMARY:
SYNCTHING:
- Same-ID migration: copy cert.pem, key.pem, config.xml from /home/syncthing/.local/state/syncthing/ + rsync /srv/syncthing/
- Database (index-v0.14.0.db or index-v2/) should NOT be copied — let it rebuild (minutes)
- Spokes auto-reconnect if device ID preserved; if ID changes, mutual device pairing needed on all spokes
- syncthing-hub role GAP: no mechanism to inject existing keys before first start (generates new ID on install)

UNISON:
- Hub is stateless — just an SSH-accessible directory at /srv/code-sync/
- rsync data trivially; no server-side Unison daemon
- Archive rebuild is fast (seconds to low minutes for code repos) and safe
- UNISONLOCALHOSTNAME can bridge hostname change for archives, but rebuild is simpler

ANSIBLE:
- syncthing-hub role: mostly idempotent but lacks key injection and spoke device registration
- unison hub role: fully idempotent (just creates /srv/code-sync/ directory)
- GAP: no hub-specific playbook or inventory entry point
- GAP: spoke device registration on hub not automated

DOWNTIME ESTIMATES:
- Same-ID with pre-staged rsync: 2-5 min cutover, zero data loss
- Fresh provision: 30+ min config + hours for Syncthing full re-sync
- Near-zero downtime achievable with two-phase migration (pre-rsync + brief cutover)


