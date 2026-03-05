---
title: "SPEC-005: VSCode Insiders Ansible Role"
artifact: SPEC-005
status: Draft
author: cristos
created: 2026-03-05
last-updated: 2026-03-05
parent-epic: EPIC-006
linked-research: []
linked-adrs: []
depends-on: []
addresses: []
---

# SPEC-005: VSCode Insiders Ansible Role

## Problem Statement

Bureau Veritas development requires VSCode Insiders with GitHub Copilot extensions. The existing `editor` role (Phase 2) installs stable VSCode and must not be modified. A new role is needed to install VSCode Insiders alongside stable, with its own declarative extension list, integrated into Phase 6 on both macOS and Linux.

## External Behavior

**Inputs:**
- `shared/roles/editor-insiders/files/extensions.txt` — line-separated extension IDs for Insiders
- Platform detection (macOS vs Linux) via Ansible facts

**Outputs:**
- VSCode Insiders installed and available as `code-insiders` CLI
- All listed extensions installed in the Insiders extension directory
- Phase 6 playbook (`06-bureau-veritas.yml`) includes the new role

**Preconditions:**
- Homebrew available (macOS) or apt available (Linux)
- No dependency on Phase 2 or stable VSCode

**Postconditions:**
- `code-insiders --version` succeeds
- `code-insiders --list-extensions` includes all entries from `extensions.txt`
- Stable VSCode (if installed) is unaffected

## Acceptance Criteria

1. **Given** a fresh macOS machine with Homebrew, **when** Phase 6 runs, **then** VSCode Insiders is installed via `visual-studio-code-insiders` cask and `code-insiders` is on PATH.
2. **Given** a fresh Linux machine with apt, **when** Phase 6 runs, **then** VSCode Insiders is installed via the Microsoft `.deb` package (Insiders channel) and `code-insiders` is on PATH.
3. **Given** the extensions list contains `github.copilot` and `github.copilot-chat`, **when** the role runs, **then** both extensions are installed in Insiders.
4. **Given** stable VSCode is already installed from Phase 2, **when** Phase 6 runs, **then** stable VSCode's extensions and settings are unchanged.
5. **Given** Phase 6 has already run once, **when** it runs again (idempotent), **then** no errors occur and no unnecessary changes are made.

## Scope & Constraints

**In scope:**
- New Ansible role `editor-insiders` at `shared/roles/editor-insiders/`
- Extensions list file with at minimum: `github.copilot`, `github.copilot-chat`
- Role inclusion in `macos/plays/06-bureau-veritas.yml` and `linux/plays/06-bureau-veritas.yml`
- Linux install via Microsoft apt repo (Insiders channel) following the stable editor role pattern

**Out of scope:**
- VSCode Insiders dotfiles/settings (no stable dotfiles exist yet either)
- Copilot CLI installation (separate STORY-012)
- Changes to the stable editor role
- Remote/SSH or Dev Container configuration

## Implementation Approach

1. Create `shared/roles/editor-insiders/tasks/main.yml` modeled on the existing `editor` role structure.
2. macOS task: `homebrew_cask: name=visual-studio-code-insiders state=present`
3. Linux task: download and install the Insiders `.deb` from Microsoft (follow the existing stable pattern but use the Insiders download URL).
4. Extension installation task: loop over `extensions.txt` using `code-insiders --install-extension`.
5. Create `shared/roles/editor-insiders/files/extensions.txt` with initial extensions.
6. Add `editor-insiders` role to both platform Phase 6 playbooks.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-05 | ab03bdb | Initial creation |
