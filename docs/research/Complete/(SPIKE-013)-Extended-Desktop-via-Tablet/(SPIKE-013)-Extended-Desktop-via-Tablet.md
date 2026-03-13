---
title: "Extended Desktop via Tablet"
artifact: SPIKE-013
status: Complete
author: Cristos L-C
created: 2026-03-12
last-updated: 2026-03-12
question: "Can we provision a true extended desktop (not just mirroring) from a tablet or secondary device, and what tooling does that require on macOS and Linux?"
gate: Pre-implementation
risks-addressed:
  - "Weylus may be mirror-only with no virtual display support"
  - "macOS and Linux may require different virtual display drivers"
depends-on: []
evidence-pool: ""
linked-bugs:
  - BUG: bd_202602-workstation-rzb
---

# Extended Desktop via Tablet

## Question

Can we provision a true extended desktop (not just screen mirroring) from a tablet or secondary device, and what tooling does that require on macOS and Linux?

The current `display` role installs Weylus, but Weylus only mirrors existing monitors. An extended desktop requires a virtual display that the OS treats as a real monitor, plus a way to stream that display to the tablet.

## Go / No-Go Criteria

1. **GO if** at least one cross-platform solution (or one per platform) can create a virtual display and stream it to a tablet with < 50ms latency at 1080p.
2. **GO if** the solution can be provisioned via Ansible (package install + config, no manual GUI steps).
3. **NO-GO if** macOS requires unsigned kernel extensions or SIP must be disabled.

## Pivot Recommendation

If no viable extended-desktop solution exists:
- Keep Weylus for mirroring-only use cases and document the limitation.
- Evaluate dedicated hardware solutions (portable USB-C monitors) as the recommended path for extra screen real estate.

## Candidates to Investigate

- **Weylus** — confirm whether virtual display is supported or roadmapped
- **Deskreen** — screen sharing app; check if it supports virtual displays
- **Virtual display drivers** — macOS (BetterDisplay / dummy display), Linux (xrandr virtual output, evdi/DisplayLink)
- **VNC-based approach** — virtual framebuffer (Xvfb on Linux, headless display on macOS) + VNC server + tablet VNC client
- **Splashtop Wired XDisplay / Duet Display / Luna Display** — commercial options; check Ansible-installability

## Findings

### 1. Weylus (current solution) — MIRROR ONLY

Weylus is designed as a graphic tablet/touch input tool, not an extended display solution. Its README confirms: on macOS and Windows it can **only mirror** existing screens. On Linux with **Intel GPUs only**, you can create a virtual output via `xrandr --addmode VIRTUAL1` and then mirror that — but the project explicitly warns this "may break starting the X server."

- Last meaningful release: 2021. Project appears stagnant.
- No virtual display creation built-in; relies on external xrandr hacks (Intel-only).
- **Verdict: Not viable for extended desktop. Keep for stylus/touch input use case only.**

Sources: [Weylus README](https://github.com/H-M-H/Weylus), [r/linux discussion](https://www.reddit.com/r/linux/comments/gxgm69/), [HN thread](https://news.ycombinator.com/item?id=23443430)

### 2. Deskreen — EXTENDED DESKTOP (with caveats)

Open-source (Electron/WebRTC), cross-platform. Can mirror screen, share a single app window, or stream an extended desktop — but **extended mode requires a Virtual Display Adapter** (HDMI dummy plug or software virtual display driver). The [Virtual Display Drivers Knowledge Base](https://github.com/pavlobu/deskreen/discussions/86) documents software alternatives to dummy plugs.

- Streams via WebRTC in a web browser — no client app needed on tablet.
- Video quality reported as "not suitable" by multiple Reddit users compared to Sunshine/Moonlight.
- Higher latency than hardware-accelerated streaming.
- Install: `brew install --cask deskreen` (macOS), AppImage or `.deb` (Linux).
- **Verdict: Functional but inferior streaming quality. Better options exist.**

Sources: [deskreen.com](https://deskreen.com/), [GitHub](https://github.com/pavlobu/deskreen), [r/linux discussion](https://www.reddit.com/r/linux/comments/l3etrn/), [XDA](https://www.xda-developers.com/deskreen-app-secondary-screen-pc/)

### 3. Sunshine + Moonlight + Virtual Display — RECOMMENDED

**Architecture:** Sunshine (streaming server on host) encodes a display via hardware-accelerated video (VideoToolbox on macOS, VAAPI/NVENC on Linux) and streams it over LAN to Moonlight (client on tablet). Combined with a virtual display driver, the OS sees a real second monitor that gets streamed to the tablet.

**Why this wins:**
- Hardware-accelerated encoding: < 16ms encode latency achievable on LAN.
- Active development: Sunshine (LizardByte) and Moonlight are very actively maintained.
- Cross-platform: Sunshine runs on macOS + Linux; Moonlight available on iOS, Android, macOS, Linux.
- 60+ FPS at 1080p confirmed by multiple users.
- Fully automatable via package managers.

**macOS stack:**
| Component | Purpose | Install |
|-----------|---------|---------|
| [BetterDisplay](https://github.com/waydabber/BetterDisplay) | Virtual display creation (no dummy plug needed) | `brew install --cask betterdisplay` |
| [Sunshine](https://github.com/LizardByte/Sunshine) | Streaming server with HW-accelerated encoding | `brew install --cask sunshine` |
| [Moonlight](https://moonlight-stream.org/) | Streaming client on tablet | App Store / Play Store |

- BetterDisplay creates virtual dummy displays at any resolution via menu bar — no SIP disable, no kexts.
- BetterDisplay Pro ($21.99) for full features, but free tier supports virtual display creation.
- BetterDisplay has a CLI (`betterdisplaycli`) for automation.

**Linux stack:**
| Component | Purpose | Install |
|-----------|---------|---------|
| xrandr virtual output (Intel/AMD) OR [Linux-Virtual-Display-Driver](https://github.com/VirtualDrivers/Linux-Virtual-Display-Driver) | Virtual display creation | xrandr (built-in) or DKMS module |
| [Sunshine](https://github.com/LizardByte/Sunshine) | Streaming server | apt/flatpak/AppImage |
| [Moonlight](https://moonlight-stream.org/) | Streaming client on tablet | Play Store / App Store |

- On Wayland/Sway: `swaymsg create_output` creates a HEADLESS-1 virtual output natively.
- On X11 with Intel: `xrandr --addmode VIRTUAL1 1920x1080` (built-in, no extra driver).
- On X11 with AMD/Nvidia: Linux-Virtual-Display-Driver (DKMS kernel module, actively maintained).

**Notable forks:**
- **Apollo** (Sunshine fork) — automates virtual display creation/teardown per streaming session.
- **Artemis** (Moonlight fork) — built-in virtual display driver that activates only while streaming.
- Both are newer and less battle-tested than mainline Sunshine/Moonlight.

Sources: [r/MoonlightStreaming guide](https://www.reddit.com/r/MoonlightStreaming/comments/1cytahf/), [r/linux 60fps guide](https://www.reddit.com/r/linux/comments/1kaxdyr/), [Sunshine docs](https://docs.lizardbyte.dev/projects/sunshine/latest/), [nite07.com tutorial](https://www.nite07.com/en/posts/extended-screen/), [dansblog guide](https://dansblog.pages.dev/blog/how-i-turned-my-tablet-into-a-second-monitor-with-sunshine-en/)

### 4. VirtScreen (Linux only) — FUNCTIONAL BUT LIMITED

Creates a virtual secondary screen via xrandr and shares it through VNC (x11vnc). GUI and CLI modes. Simple to set up.

- **X11 only — does NOT support Wayland.**
- Higher latency than Sunshine/Moonlight (VNC encoding vs HW-accelerated h264/h265).
- Last release: v0.3.1 (project appears dormant).
- Install: AppImage or `pip install virtscreen`.
- **Verdict: Works for basic use, but VNC latency and X11-only limitation make it a fallback.**

Sources: [GitHub](https://github.com/kbumsik/VirtScreen), [brightcoding.dev guide](https://converter.brightcoding.dev/blog/how-to-turn-your-tablet-into-a-linux-second-monitor-the-ultimate-vnc-guide-2025)

### 5. Commercial Solutions — DISQUALIFIED

| Solution | Platforms | Why disqualified |
|----------|-----------|-----------------|
| Duet Display | macOS/Windows host, iPad/Android client | No Linux host support; paid subscription |
| Luna Display | macOS only (hardware dongle) | No Linux; requires $130 hardware |
| Splashtop Wired XDisplay | Windows/macOS host | No Linux host; paid |
| SuperDisplay | Windows host, Android client only | No macOS/Linux; no iOS |

None support Linux as a host, and none are Ansible-automatable. **All disqualified.**

Sources: [ProductHunt alternatives](https://www.producthunt.com/products/duet-display/alternatives), [AlternativeTo](https://alternativeto.net/software/weylus/)

### 6. HDMI Dummy Plug (hardware fallback)

A $5-10 HDMI/DP dummy plug creates a virtual display that the OS treats as a real monitor. Combined with any streaming solution (Deskreen, Sunshine, VNC), it provides a guaranteed extended desktop. Downside: requires physical hardware per machine, but eliminates all software virtual display driver complexity.

## Recommendation

**GO — all three criteria met.**

1. Sunshine + Moonlight achieves < 16ms encode latency (well under 50ms threshold) at 1080p 60fps.
2. All components installable via Homebrew (macOS) or apt/flatpak (Linux) — fully Ansible-provisionable.
3. No SIP disable or kernel extensions required on macOS (BetterDisplay uses native macOS APIs).

**Proposed new `display` role architecture:**

| Component | macOS | Linux |
|-----------|-------|-------|
| Virtual display | BetterDisplay (`brew install --cask betterdisplay`) | xrandr virtual output / Linux-Virtual-Display-Driver |
| Streaming server | Sunshine (`brew install --cask sunshine`) | Sunshine (apt/flatpak) |
| Streaming client | Moonlight (tablet app — manual install) | Moonlight (tablet app — manual install) |
| Legacy | Weylus (keep for stylus/touch input) | Weylus (keep for stylus/touch input) |

**Next steps if proceeding:**
1. Create SPEC for display role refactor (add Sunshine + BetterDisplay, keep Weylus optional).
2. Test BetterDisplay virtual display creation via CLI for Ansible automation.
3. Test Sunshine headless provisioning (config file generation, firewall rules).
4. Close BUG bd_202602-workstation-rzb as "resolved by design change."

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-03-12 | — | Initial creation; linked to BUG bd_202602-workstation-rzb |
| Active | 2026-03-12 | — | Research conducted; web search across general, Reddit, ProductHunt sources |
| Complete | 2026-03-12 | — | GO: Sunshine+Moonlight+BetterDisplay; approved for implementation |
