---
title: "EPIC-006: VSCode Insiders and GitHub Copilot CLI"
artifact: EPIC-006
status: Proposed
author: cristos
created: 2026-03-05
last-updated: 2026-03-05
parent-vision: VISION-001
success-criteria:
  - VSCode Insiders is installed via Ansible on both macOS and Linux
  - VSCode Insiders extensions are managed declaratively (separate from stable VSCode)
  - GitHub Copilot and Copilot Chat extensions are installed in VSCode Insiders
  - GitHub Copilot CLI is installed as a standalone tool with no Phase 2 dependency
  - Bureau Veritas development workflow is functional after a single provisioning run
depends-on: []
addresses: []
---

# EPIC-006: VSCode Insiders and GitHub Copilot CLI

## Goal / Objective

Add VSCode Insiders and GitHub Copilot CLI to the Bureau Veritas phase (Phase 6). This is a separate editor from the stable VSCode already provisioned in Phase 2 (dev-tools) — both can coexist on the same machine. Copilot CLI is a standalone tool (not a `gh` extension) — Phase 6 has no dependency on Phase 2.

## Existing Infrastructure

The following is already in place for stable VSCode and should inform (but not be duplicated by) this work:

| Component | Location | Phase |
|-----------|----------|-------|
| VSCode (stable) install | `shared/roles/editor/tasks/main.yml` | Phase 2 (dev-tools) |
| Stable extensions list | `shared/roles/editor/files/extensions.txt` | Phase 2 (dev-tools) |
| VSCode dotfiles (settings, keybindings) | `{linux,macos}/dotfiles/vscode/` | Phase 4 (dotfiles) |

**Key difference:** VSCode stable uses `code` CLI / `visual-studio-code` cask. Insiders uses `code-insiders` CLI / `visual-studio-code-insiders` cask. They have separate extension directories, settings paths, and binaries. The existing editor role is a useful structural reference but is not a dependency.

## Scope Boundaries

**In scope:**
- New Ansible role for VSCode Insiders installation (Homebrew cask `visual-studio-code-insiders` on macOS, `.deb` on Linux)
- Separate extensions list for Insiders (including `github.copilot` and `github.copilot-chat`)
- Insiders dotfiles/settings managed via Stow (separate stow package from stable)
- GitHub Copilot CLI installation (Homebrew `copilot-cli` on macOS, `npm install -g @github/copilot` or curl installer on Linux)
- Include the new role(s) in `06-bureau-veritas.yml` on both platforms
- Encryption-at-rest for any personalized Insiders config per AGENTS.md policy

**Out of scope:**
- Changes to the existing stable VSCode editor role (Phase 2)
- VSCode Remote/SSH or Dev Container setup
- Copilot subscription management or billing
- IDE-level workspace settings for specific Bureau Veritas projects
- Copilot extensions in stable VSCode (Phase 2 stays as-is)

## Child Specs

_To be created as the epic is decomposed._

## Key Dependencies

None. Copilot CLI is standalone (Homebrew formula / npm package) — no `gh` CLI required. Phase 6 is fully independent of Phase 2.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Proposed | 2026-03-05 | 4e5aaba | Initial creation for Bureau Veritas phase |
