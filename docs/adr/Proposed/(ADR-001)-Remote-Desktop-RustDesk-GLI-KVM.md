# ADR-001: Remote Desktop via RustDesk + GLI KVM

**Status:** Proposed
**Date:** 2026-02-26
**PRD:** [(PRD-002) Remote Desktop Bootstrap](../../prd/Draft/(PRD-002)-Remote-Desktop/(PRD-002)-Remote-Desktop.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-02-26 | d627b5b | Initial creation |

---

## Context

The workstation provisioning system has no remote desktop role. Remote access is handled ad-hoc:

- **Remotix** (now Acronis Cyber Protect Connect) was used as a VNC/RDP client, but the acquisition killed it for personal use: perpetual licenses discontinued end-of-2022, free tier capped at 15-minute sessions, pricing not publicly listed, and Acronis itself was acquired by EQT in 2025.
- **GL.iNet GLKVM** (Comet) provides hardware KVM-over-IP for BIOS-level access to headless machines. A native macOS app exists. On Linux, GL.iNet recommends browser-based access via the device's Tailscale IP or glkvm.com cloud.
- **Inbound access** (letting other machines control this workstation) is completely unmanaged — no VNC/RDP server is provisioned.

Remote desktop goes in two directions:

1. **Outbound** — controlling other machines (VNC/RDP client, KVM viewer)
2. **Inbound** — making this machine controllable (VNC/RDP server, remote agent)

The workstation needs a solution that covers both directions, works cross-platform, is self-hostable, and won't get rug-pulled by an acquisition.

## Decision

### 1. Replace Remotix with RustDesk

**RustDesk** is the remote desktop tool for both directions:

- **Open source (AGPL-3.0)** — forkable, no license rug-pull risk.
- **Cross-platform** — native .deb on Linux, native DMG/Homebrew cask on macOS.
- **Client AND server in one binary** — install once, and the machine can both control and be controlled. No separate "agent" or "server" package.
- **Self-hosted relay** — run a relay server on your own infrastructure (Docker, VPS, or LAN). No dependency on a third-party cloud.
- **Protocol support** — uses its own protocol (optimized for low latency), but the key point is it replaces both the Remotix client and the missing inbound access.
- **Works alongside Tailscale** — Tailscale provides the network mesh; RustDesk provides the screen-sharing layer on top.

RustDesk does NOT replace standard VNC/RDP clients (it uses its own protocol). If raw VNC/RDP client access is needed in the future (e.g., connecting to a Windows RDP server), Remmina can be added to the role as a Linux sub-task. On macOS, the built-in Screen Sharing handles VNC, and Microsoft Remote Desktop handles RDP.

### 2. Keep GLI KVM for hardware-level access

RustDesk operates at the OS level — it requires a running OS with the RustDesk service. The GL.iNet Comet KVM operates at the hardware level — it captures HDMI output and injects USB HID input regardless of OS state. These are complementary:

| Scenario | Tool |
|----------|------|
| Remote desktop to a running machine | RustDesk |
| BIOS setup, OS install, boot troubleshooting | GLI KVM (Comet) |
| Machine is powered off or hung | GLI KVM (Comet) via wake-on-LAN |

GLI KVM stays in the same role because it's conceptually "remote desktop" — you're viewing and controlling a remote screen.

### 3. Create a single `remote-desktop` role

Following the `vpn` role pattern (Tailscale + Surfshark in one role with sub-task files):

```
shared/roles/remote-desktop/
├── tasks/
│   ├── main.yml          # OS dispatch
│   ├── debian.yml         # includes rustdesk.yml, gli-kvm.yml
│   ├── darwin.yml         # includes rustdesk.yml, gli-kvm.yml
│   ├── rustdesk.yml       # RustDesk install + relay config (cross-platform with when: guards)
│   └── gli-kvm.yml        # macOS: install app; Linux: debug message
└── defaults/
    └── main.yml           # rustdesk_relay_host, rustdesk_relay_key, etc.
```

Tags: `remote-desktop`, `rustdesk`, `gli-kvm`, `desktop`

The role goes in `03-desktop.yml` on both platforms, alongside `vpn`, `communication`, and other connectivity roles.

### 4. Installation strategy

**RustDesk on Linux (Debian/Mint):**
- Download `.deb` from GitHub releases via `ansible.builtin.get_url`
- Install via `ansible.builtin.apt: deb=<path>`
- Enable systemd service for unattended inbound access
- Configure relay server address via RustDesk config file

**RustDesk on macOS:**
- Install via `homebrew_cask: rustdesk` (if cask exists) or download DMG
- Configure relay server address
- Note: macOS requires granting Accessibility + Screen Recording permissions manually (same pattern as Hammerspoon)

**GLI KVM on macOS:**
- Install via `homebrew_cask` if available, otherwise `ansible.builtin.get_url` for DMG
- No configuration needed — connects to Comet device via network

**GLI KVM on Linux:**
- `ansible.builtin.debug` message: "GLI KVM has no Linux app. Access your Comet at https://<tailscale-ip> or https://glkvm.com"
- Zero packages to install

### 5. Relay server is out of scope for workstation provisioning

The RustDesk relay server (`hbbs` + `hbbr`) runs on infrastructure (a VPS or always-on LAN machine), not on the workstation being provisioned. The workstation role only configures the relay address, not deploys the relay itself.

In the interim, direct connections via Tailscale work without any relay.

## Consequences

### Positive

- **Both directions covered** — one tool for controlling remote machines and being controlled.
- **Self-hosted, open source** — no acquisition risk, no subscription, no cloud dependency.
- **Cross-platform parity** — same tool on Linux and macOS, same protocol, same relay.
- **Complements existing stack** — Tailscale for networking, RustDesk for screen sharing, GLI KVM for hardware access. Clean separation of concerns.
- **Follows existing patterns** — single role with sub-task files, same as `vpn` role.
- **Automatable** — .deb install, config file templating, systemd service — all standard Ansible patterns.

### Negative

- **RustDesk uses its own protocol** — cannot connect to standard VNC/RDP servers. If that's needed, a separate VNC/RDP client (Remmina on Linux, built-in tools on macOS) must be added.
- **macOS permissions are manual** — Screen Recording and Accessibility must be granted via System Settings. Ansible cannot automate this (same limitation as Hammerspoon).
- **New infrastructure dependency** — full unattended access requires deploying a relay server, which is outside this role's scope.
- **RustDesk .deb from GitHub releases** — not from an apt repo, so updates require re-running the role or a separate update mechanism.

### Neutral

- Remotix / Acronis Cyber Protect Connect is fully dropped. No migration needed — there's nothing to migrate (it was manually installed, no config in the repo).
- The `adding-tools.md` table gets a new entry for `remote-desktop`.

## Alternatives Considered

### Remotix / Acronis Cyber Protect Connect — Rejected

Acquired by Acronis (2021), rebranded, perpetual licenses killed (2022), free tier capped at 15 minutes, pricing hidden behind sales contact, Acronis itself acquired by EQT (2025). Not suitable for automated provisioning of a personal workstation.

### RealVNC Connect — Rejected

Free "Lite" tier limited to 3 devices, 1 concurrent connection, non-commercial only. The old fully-free Home plan was discontinued in 2024. Paid plans start at ~$99/year. Proprietary. Not self-hostable.

### Remmina — Rejected as primary, available as future add-on

Excellent open-source multi-protocol client (VNC/RDP/SSH/X2Go) on Linux. However: no real macOS support (requires XQuartz), client-only (no inbound access), and RustDesk covers the primary use case. Can be added as a `remmina.yml` sub-task later if raw VNC/RDP client access is needed on Linux.

### Apache Guacamole — Rejected for workstation role

Clientless browser-based gateway — great for server infrastructure, but overkill for a desktop workstation role. Better suited as infrastructure than as a workstation-provisioned tool.

### TigerVNC / TurboVNC — Rejected as primary

Open-source VNC server/client. Solid for pure VNC, but doesn't provide the integrated client+server+relay architecture that RustDesk offers. Would require assembling separate server and client components. Could be added as a future sub-task if standard VNC interop is needed.
