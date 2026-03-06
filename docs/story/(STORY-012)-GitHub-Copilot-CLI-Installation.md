---
title: "STORY-012: GitHub Copilot CLI Installation"
artifact: STORY-012
status: Implemented
author: cristos
created: 2026-03-05
last-updated: 2026-03-06
parent-epic: EPIC-006
depends-on: []
addresses: []
---

# STORY-012: GitHub Copilot CLI Installation

**As a** developer on a Bureau Veritas machine, **I want** GitHub Copilot CLI installed as a standalone tool, **so that** I can use Copilot suggestions from the terminal without depending on `gh` CLI or Phase 2.

## Acceptance Criteria

1. On macOS, Copilot CLI is installed via Homebrew (`brew install github-copilot-cli` or the current formula name) and `github-copilot-cli` (or `copilot`) is on PATH.
2. On Linux, Copilot CLI is installed via npm (`npm install -g @githubnext/github-copilot-cli`) or the official installer, and the CLI binary is on PATH.
3. Installation is handled by an Ansible task (either a new role or added to `editor-insiders`) included in Phase 6.
4. The installation has no dependency on `gh` CLI or Phase 2 dev-tools.
5. Running `copilot --version` (or equivalent) succeeds after provisioning.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-05 | ab03bdb | Initial creation |
| Implemented | 2026-03-06 | 9a4bc83 | Implementation complete — copilot-cli role verified |
