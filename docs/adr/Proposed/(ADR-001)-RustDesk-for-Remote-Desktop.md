# ADR-001: RustDesk for Remote Desktop

**Status:** Proposed
**Date:** 2026-02-26
**PRD:** [(PRD-002) Remote Desktop Bootstrap](../../prd/Draft/(PRD-002)-Remote-Desktop/(PRD-002)-Remote-Desktop.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-02-26 | d627b5b | Initial creation |

---

## Context

The workstation has no provisioned remote desktop tooling. The previous tool of choice, **Remotix**, was acquired by Acronis in 2021 and rebranded as Acronis Cyber Protect Connect. Perpetual licenses were discontinued at end-of-2022, the free tier was capped at 15-minute sessions, pricing is no longer publicly listed, and Acronis itself was acquired by EQT in 2025. Remotix is no longer viable.

Remote desktop goes in two directions:

1. **Outbound** — controlling other machines (VNC/RDP client)
2. **Inbound** — making this machine controllable (VNC/RDP server, remote agent)

The workstation needs a replacement that covers both directions, works cross-platform (Linux + macOS), is self-hostable, and won't get rug-pulled by an acquisition.

## Decision

**Adopt RustDesk as the remote desktop client and server.**

Key properties:

- **Open source (AGPL-3.0)** — forkable, no license rug-pull risk.
- **Cross-platform** — native .deb on Linux, native DMG/Homebrew cask on macOS.
- **Client AND server in one binary** — install once, and the machine can both control and be controlled. No separate "agent" or "server" package.
- **Self-hosted relay** — run a relay server (`hbbs` + `hbbr`) on your own infrastructure. No dependency on a third-party cloud. In the interim, direct connections via Tailscale work without any relay.
- **Works alongside Tailscale** — Tailscale provides the network mesh; RustDesk provides the screen-sharing layer on top.

### Limitations accepted

- **RustDesk uses its own protocol** — it cannot connect to standard VNC/RDP servers. If raw VNC/RDP access is needed in the future, Remmina can be added on Linux; macOS has built-in Screen Sharing (VNC) and Microsoft Remote Desktop (RDP).
- **macOS permissions are manual** — Screen Recording and Accessibility must be granted via System Settings. Ansible cannot automate this (same limitation as Hammerspoon).
- **RustDesk .deb comes from GitHub releases** — not from an apt repository, so updates require re-running the role or a separate update mechanism.

## Consequences

### Positive

- **Both directions covered** — one tool for controlling remote machines and being controlled.
- **Self-hosted, open source** — no acquisition risk, no subscription, no cloud dependency.
- **Cross-platform parity** — same tool on Linux and macOS, same protocol, same relay.
- **Complements existing stack** — Tailscale for networking, RustDesk for screen sharing. Clean separation of concerns.
- **Automatable** — .deb install, config file templating, systemd service — all standard Ansible patterns.

### Negative

- **Own-protocol only** — no VNC/RDP interop out of the box.
- **macOS permissions are manual** — cannot be fully automated.
- **New infrastructure dependency** — full unattended access benefits from deploying a relay server, which is outside workstation provisioning scope.
- **GitHub-release-based install** — no apt repo means no automatic security updates.

### Neutral

- Remotix / Acronis Cyber Protect Connect is fully dropped. No migration needed — it was manually installed with no config in the repo.

## Alternatives Considered

### Remotix / Acronis Cyber Protect Connect — Rejected

Acquired by Acronis (2021), rebranded, perpetual licenses killed (2022), free tier capped at 15 minutes, pricing hidden behind sales contact, Acronis itself acquired by EQT (2025). Not suitable for automated provisioning of a personal workstation.

### RealVNC Connect — Rejected

Free "Lite" tier limited to 3 devices, 1 concurrent connection, non-commercial only. The old fully-free Home plan was discontinued in 2024. Paid plans start at ~$99/year. Proprietary. Not self-hostable.

### Remmina — Rejected as primary, available as future add-on

Excellent open-source multi-protocol client (VNC/RDP/SSH/X2Go) on Linux. However: no real macOS support (requires XQuartz), client-only (no inbound access), and RustDesk covers the primary use case. Can be added later if raw VNC/RDP client access is needed on Linux.

### Apache Guacamole — Rejected for workstation role

Clientless browser-based gateway — great for server infrastructure, but overkill for a desktop workstation. Better suited as infrastructure than as a workstation-provisioned tool.

### TigerVNC / TurboVNC — Rejected as primary

Open-source VNC server/client. Solid for pure VNC, but doesn't provide the integrated client+server+relay architecture that RustDesk offers. Would require assembling separate server and client components.
