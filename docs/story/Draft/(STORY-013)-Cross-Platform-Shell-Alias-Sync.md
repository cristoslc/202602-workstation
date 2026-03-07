---
title: "Cross-Platform Shell Alias Sync"
artifact: STORY-013
status: Draft
author: cristos
created: 2026-03-07
last-updated: 2026-03-07
parent-epic: EPIC-003
depends-on: []
addresses: []
execution-tracking: required
---

# Cross-Platform Shell Alias Sync

**As a** developer using both macOS and Linux Mint, **I want** my shell aliases deduplicated and correctly layered across shared and platform-specific files, **so that** I get a consistent CLI experience on both platforms without maintaining duplicate definitions.

## Context

The repo already has a three-file alias structure:

- `shared/dotfiles/zsh/.config/zsh/aliases.zsh` -- cross-platform aliases
- `macos/dotfiles/zsh/.config/zsh/macos.zsh` -- macOS-specific shell config
- `linux/dotfiles/zsh/.config/zsh/linux.zsh` -- Linux-specific shell config

Some aliases (e.g., `eza`/`ls`, `bat`/`cat`) are duplicated in both platform files despite being functionally identical. Other aliases may exist on the live systems but are not yet captured in the repo.

## Acceptance Criteria

1. All aliases present on both live systems (macOS and Mint) are audited and captured in the repo.
2. Aliases that are identical across platforms live only in `shared/dotfiles/zsh/.config/zsh/aliases.zsh` -- no duplication in platform files.
3. Aliases that differ by platform (e.g., `batcat` vs `bat`, `fdfind` vs `fd`, `apt` shortcuts, `flushdns`) remain in their respective platform files.
4. `stow --simulate` runs cleanly for the `zsh` package on both platforms with no collisions.
5. A fresh `make apply` on either platform produces the expected alias set (verified by sourcing and spot-checking).

## Implementation Approach

1. Audit live aliases on both systems (`alias` command output) against repo files.
2. Move shared aliases (eza/ls, bat/cat) from platform files into `aliases.zsh`, using `command -v` guards where the binary name differs.
3. Keep platform-only aliases (apt shortcuts, `open`/`xdg-open`, `flushdns`, `fdfind` alias) in their platform files.
4. Verify stow simulation on both platforms.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-07 | — | Initial creation |
