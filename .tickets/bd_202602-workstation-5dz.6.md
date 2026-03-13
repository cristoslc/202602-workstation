---
id: bd_202602-workstation-5dz.6
status: closed
deps: []
links: []
created: 2026-03-03T17:29:14Z
type: task
priority: 2
---
# Evaluate dual-hub and spoke-to-spoke fallback options

If single-hub proves too fragile, investigate pivot options: (1) Dual-hub topology — both Syncthing and Unison connect to two hubs (home server + VPS), Unison dual-hub viability (round-robin or active-passive). (2) Spoke-to-spoke fallback for Syncthing when hub is unreachable.

## Notes

FINDINGS SUMMARY:
Option 1 - Syncthing Dual-Hub: DEFER
  - Technically proven, endorsed by Syncthing devs
  - Requires VPS that doesn't exist yet (VISION-002 in Draft)
  - Medium complexity (Ansible scalar-to-list refactor)
  - Revisit when VPS provisioned for other reasons

Option 2 - Unison Dual-Hub: SKIP
  - Unison's pairwise model makes it awkward (separate archives per pair)
  - High complexity, no community pattern
  - git push/pull is acceptable manual fallback for code sync

Option 3 - Syncthing Spoke-to-Spoke Fallback: SKIP
  - Custom failover automation with no precedent
  - High complexity (health-check daemon, REST API topology changes)
  - Rare failure mode at this scale

Option 4 - Do Nothing: ACCEPT
  - Correct for 2-3 workstations, single user
  - Local queuing + auto-resume + fast same-ID migration covers practical failures
  - No complexity creep

RECOMMENDATION: Accept single-hub. Tag Syncthing dual-hub as future enhancement gated on VISION-002 VPS.


