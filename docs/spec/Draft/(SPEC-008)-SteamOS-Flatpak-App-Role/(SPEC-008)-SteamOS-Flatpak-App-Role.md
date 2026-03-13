---
title: "SPEC-008: SteamOS Flatpak App Role"
artifact: SPEC-008
status: Draft
author: cristos
created: 2026-03-12
last-updated: 2026-03-12
parent-epic: EPIC-007
linked-research:
  - SPIKE-012
linked-adrs: []
depends-on:
  - SPEC-006
addresses: []
evidence-pool: ""
swain-do: required
---

# SPEC-008: SteamOS Flatpak App Role

## Problem Statement

GUI applications on SteamOS must be installed via Flatpak to survive OS updates — pacman installs are wiped. Ansible has native Flatpak support (`community.general.flatpak`), and Flatpak is pre-installed on SteamOS. The provisioning engine needs a role that declaratively installs GUI apps via Flatpak, analogous to Homebrew Cask on macOS.

## External Behavior

**Inputs:**
- A list of Flatpak application IDs defined in `steamos/group_vars/all.yml` under a `flatpak_apps` variable
- Flatpak already available (pre-installed on SteamOS)

**Outputs:**
- All apps in `flatpak_apps` installed from Flathub
- A `steamos-flatpak` Ansible role that:
  1. Ensures the Flathub remote is configured
  2. Installs each app in `flatpak_apps` using `community.general.flatpak`
  3. Supports a `flatpak_apps_remove` list for uninstalling deprecated apps

**Default app list** (from EPIC-007 scope):
- Browsers: Firefox (`org.mozilla.firefox`), Brave (`com.brave.Browser`)
- Text expansion: Espanso (`org.espanso.Espanso`)
- Communication: Slack (`com.slack.Slack`), Signal (`org.signal.Signal`)
- Media: Spotify (`com.spotify.Client`), VLC (`org.videolan.VLC`)

**Constraints:**
- Only runs when `ansible_distribution is search("SteamOS")`
- Uses `community.general.flatpak` module (already in requirements.yml)

## Acceptance Criteria

1. **Given** a Steam Deck with Flatpak available, **when** the flatpak role runs, **then** all apps in `flatpak_apps` are installed.
2. **Given** Flathub is not configured as a remote, **when** the role runs, **then** Flathub is added before app installation.
3. **Given** an app is already installed, **when** the role runs again, **then** no reinstallation occurs (idempotent).
4. **Given** an app is listed in `flatpak_apps_remove`, **when** the role runs, **then** that app is removed.
5. **Given** the role is run on macOS or Linux Mint, **then** it is skipped entirely.

## Verification

| Criterion | Evidence | Result |
|-----------|----------|--------|

## Scope & Constraints

- **In scope:** Flatpak app installation role, Flathub remote setup, default app list, removal support.
- **Out of scope:** Flatpak app configuration/preferences (manual or future spec), CLI tools (SPEC-007), Flatpak permissions/overrides.
- The `community.general` collection must be in `shared/requirements.yml` (already present).

## Implementation Approach

1. Create `steamos-flatpak` role using `community.general.flatpak` module.
2. Add Flathub remote setup as first task.
3. Loop over `flatpak_apps` with the flatpak module (state: present).
4. Loop over `flatpak_apps_remove` with state: absent.
5. Define default `flatpak_apps` in `steamos/group_vars/all.yml`.
6. Test: verify install, idempotency, removal, and platform guard.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-12 | — | Created during EPIC-007 decomposition |
