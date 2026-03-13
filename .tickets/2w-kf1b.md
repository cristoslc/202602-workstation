---
id: 2w-kf1b
status: closed
deps: []
links: []
created: 2026-03-13T05:06:35Z
type: epic
priority: 2
assignee: cristos
external-ref: SPEC-008
---
# Implement SPEC-008: SteamOS Flatpak App Role

Declarative GUI app installation via Flatpak on SteamOS. Depends on SPEC-006.


## Notes

**2026-03-13T05:10:01Z**

steamos-flatpak role created: Flathub remote (user scope), install loop, remove loop. Uses community.general.flatpak (already in requirements.yml).

**2026-03-13T05:13:53Z**

SPEC-008 implemented in commit 91fcac1: steamos-flatpak role with Flathub remote, install/remove loops, platform guard.
