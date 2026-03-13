---
title: "STORY-014: SteamOS Shell and Dotfile Setup"
artifact: STORY-014
status: Ready
author: cristos
created: 2026-03-12
last-updated: 2026-03-13
parent-epic: EPIC-007
depends-on:
  - SPEC-006
  - SPEC-007
addresses: []
swain-do: required
---

# STORY-014: SteamOS Shell and Dotfile Setup

**As a** multi-machine developer provisioning a Steam Deck, **I want** my dotfiles, shell configuration, and git identity deployed identically to my other machines, **so that** I have a consistent dev environment across macOS, Linux, and SteamOS without manual setup.

## Acceptance Criteria

1. Running `make apply` on a bootstrapped Steam Deck deploys shared dotfiles (git, zsh, tmux, ssh, direnv) to `/home/deck` via Stow.
2. Zsh is the default shell in Konsole — opening a new Konsole window drops into zsh with the full prompt, aliases, and completions from `shared/dotfiles/zsh/`.
3. A `steamos/dotfiles/` directory exists for SteamOS-specific config overrides (Konsole profile, platform-specific zsh config), stowed alongside shared dotfiles.
4. Git commit signing works using an age-managed SSH key (no 1Password agent on SteamOS).
5. The dotfile deployment survives SteamOS updates (everything lives in `/home`).

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-12 | — | Created during EPIC-007 decomposition |
| Ready | 2026-03-13 | — | SPEC-006 approved; acceptance criteria reviewed and ready for implementation |
