# PRD-002: Remote Desktop Bootstrap

**Status:** Draft
**Author:** cristos
**Created:** 2026-02-26
**Last Updated:** 2026-02-26
**Research:** None (straightforward tool installation — no spike needed)
**ADR:** [(ADR-001) Remote Desktop via RustDesk + GLI KVM](../../../adr/Proposed/(ADR-001)-Remote-Desktop-RustDesk-GLI-KVM.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-02-26 | d627b5b | Initial creation |

---

## Problem

The workstation has no remote desktop tooling provisioned by bootstrap. The user currently:

- Manually installs **Remotix** for VNC/RDP access to other machines, but Remotix was acquired by Acronis in 2021, rebranded as Acronis Cyber Protect Connect, and switched to a subscription model with a 15-minute session cap on the free tier. Perpetual licenses were discontinued at end of 2022. The product is effectively dead for personal use.
- Manually installs the **GL.iNet GLKVM** macOS app for hardware KVM-over-IP access to headless machines via a Comet device. No Linux app exists — GL.iNet recommends browser access via Tailscale.
- Has **no inbound remote desktop** capability (no VNC/RDP server) provisioned on either platform.

This leaves a gap: fresh machines require manual installation of remote desktop tools, and the Remotix dependency is a liability.

## Goal

After `make apply`, both macOS and Linux workstations have:

1. A cross-platform remote desktop client+server (RustDesk) for OS-level remote access in both directions.
2. The GLI KVM client installed (macOS) or documented as browser-only (Linux) for hardware-level access.
3. Self-hosted relay infrastructure configuration ready (RustDesk relay server address).

## Scope

### In scope

- **RustDesk client+server** install on Linux (.deb) and macOS (Homebrew cask or DMG)
- **RustDesk relay server** address configuration (pointing to self-hosted or Tailscale-accessible relay)
- **GLI KVM app** install on macOS (Homebrew cask or DMG)
- **GLI KVM Linux** — debug message directing user to browser via Tailscale IP
- New `shared/roles/remote-desktop/` role following `adding-tools.md` conventions
- Role added to `03-desktop.yml` on both platforms
- Brewfile entries for macOS tools

### Out of scope

- Deploying a RustDesk relay server (that's infrastructure, not workstation provisioning)
- VNC/RDP server setup (xrdp, x11vnc) — RustDesk subsumes this need
- Remotix / Acronis Cyber Protect Connect — deprecated, will not be provisioned
- Remmina — RustDesk covers multi-protocol needs; Remmina can be added later via `adding-tools.md` if needed
- macOS Screen Sharing configuration (already built-in, no provisioning needed)

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| RustDesk not in default apt/brew repos | Install fails or requires manual repo setup | Use `.deb` from GitHub releases via `ansible.builtin.get_url` + `ansible.builtin.apt` (deb); Homebrew cask on macOS |
| RustDesk upstream changes license or goes hostile | Dependency becomes unreliable | AGPL source is forkable; self-hosted relay means no cloud dependency |
| GLI KVM app not in Homebrew | Can't automate macOS install | Use `ansible.builtin.get_url` for DMG + manual mount, or check if cask exists first |
| RustDesk requires systemd service for unattended access | Extra configuration beyond simple install | Add systemd enable/start tasks on Linux; launchd plist on macOS |
| Self-hosted relay not yet deployed | RustDesk falls back to public relay or direct connection | Direct connection via Tailscale works without relay; relay is a future enhancement |

## Research

No spike is needed. RustDesk and GLI KVM are well-documented tools with straightforward installation paths. The key decisions (tool selection, role structure) are captured in ADR-001.

## Success Criteria

1. `make apply` on a clean Linux machine installs RustDesk and prints a GLI KVM browser-access note.
2. `make apply` on a clean macOS machine installs RustDesk and the GLI KVM app.
3. `make apply ROLE=remote-desktop` runs only the remote-desktop role.
4. `make apply ROLE=rustdesk` runs only RustDesk tasks; `make apply ROLE=gli-kvm` runs only GLI KVM tasks.
5. RustDesk is configured to use the self-hosted relay address (when available) without manual intervention.
6. No Remotix or Acronis software is installed.
