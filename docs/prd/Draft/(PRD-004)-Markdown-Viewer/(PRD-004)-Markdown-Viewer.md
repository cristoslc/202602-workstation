# PRD-004: Markdown Viewer

**Status:** Draft
**Author:** cristos
**Created:** 2026-02-28
**Last Updated:** 2026-02-28
**Research:** —
**ADR:** —

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-02-28 | 18fbe9b | Initial creation |

---

## Problem

The workstation project has no provisioned markdown previewer. On macOS, Marked 2 (via SetApp) fills this role — a live-preview app that watches files edited in any external editor and renders them instantly. On Linux there is no equivalent installed, and Marked 2 is macOS-only.

Key pain points:

- **No Linux parity.** Opening a `.md` file on a Linux workstation requires either a browser-based workaround or reading raw markup.
- **No provisioned install.** Even on macOS, Marked 2 is obtained through SetApp rather than the Ansible/Homebrew pipeline — it is not captured in the workstation config.
- **GFM preview is the primary gap.** The core need is rendering GitHub-Flavored Markdown (fenced code blocks, tables, task lists, strikethrough) accurately. An inline editor is a nice-to-have — the main workflow is preview alongside VS Code or Neovim.

## Goal

After `make apply`, each workstation has a markdown tool that:

1. **Must have:** Renders GitHub-Flavored Markdown accurately — fenced code blocks, tables, task lists, strikethrough, autolinks.
2. **Must have:** Live-reloads on file save (watch mode) so it pairs with an external editor.
3. **Nice to have:** Inline editing capability (split-pane or WYSIWYG) for quick fixes without switching apps.
4. Is installed and configured by the provisioning pipeline — no manual steps.

## Scope

### In scope

- Select a Linux desktop markdown previewer (or a single cross-platform tool).
- Decide whether to keep Marked 2 on macOS or replace it with the cross-platform pick.
- Create a shared or platform-specific Ansible role to install the chosen tool(s).
- Desktop integration: `.md` file association, launcher entry.

### Out of scope

- Primary markdown *editing* — the editor is VS Code / Neovim, already provisioned. An inline editing pane is welcome but not the driver.
- Terminal-only renderers (`glow`, `mdcat`) — useful but do not replace a desktop previewer with live-reload.
- Note-taking / Zettelkasten apps (Obsidian, Zettlr) — different category.

## Candidates

| Tool | Platforms | GFM | Live-reload | Inline editor | License | Notes |
|------|-----------|-----|-------------|---------------|---------|-------|
| **Marked 2** | macOS only | Full | Yes (file watch) | No (preview only) | Proprietary (SetApp / $14) | Current tool. Gold standard for preview UX. No Linux support. |
| **Mark Text** | macOS, Linux, Windows | Full | Yes (built-in) | Yes (WYSIWYG) | MIT | Electron-based. Last release 2022 — maintenance unclear. |
| ~~**Typora**~~ **Selected** | macOS, Linux, Windows | Full | Yes (inline) | Yes (inline WYSIWYG) | Proprietary ($15) | Polished. Actively maintained. Cross-platform with identical UX. |
| **Apostrophe** | Linux (GNOME) | Partial (via cmark) | Yes (side panel) | Yes (split pane) | GPL-3.0 | Linux-only, GFM extensions unverified. |
| **Ghostwriter** | Linux, Windows | Full (via cmark-gfm) | Yes (side panel) | Yes (split pane) | GPL-3.0 | No official macOS build. |

## Decision

**Typora on both macOS and Linux.** One tool, identical GFM rendering and inline WYSIWYG editing on both platforms. Replaces Marked 2 on macOS.

- macOS: `brew install --cask typora`
- Linux: Typora APT/DNF repo or Snap (`snap install typora`)

Rationale:
- Full GFM support (fenced code blocks, tables, task lists, strikethrough, autolinks).
- Inline WYSIWYG editing — satisfies the nice-to-have without a separate editor.
- Actively maintained with regular releases.
- Single tool to learn and provision across platforms.
- $15 one-time purchase (no subscription).

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Typora is proprietary / closed-source | Vendor lock-in; no community fork if abandoned | Low switching cost — Typora edits plain `.md` files, no lock-in on data. Monitor alternatives. |
| $15 license per machine | Minor cost | One-time purchase, not subscription. Acceptable for a professional tool. |
| Linux package freshness | Repo may lag behind macOS releases | Typora maintains its own APT repo; Snap is also an option. Pin to known-good version if needed. |
| No file-watch mode (unlike Marked 2) | Must open files directly rather than auto-following editor saves | Typora auto-reloads on external change when the file is already open. Acceptable trade-off since inline editing reduces the need for a separate previewer. |

## Research

No research spikes required — Typora is a known, actively maintained tool with documented cross-platform support. Evaluate during implementation if any provisioning issues arise.

## Success Criteria

1. `make apply` installs Typora on both macOS and Linux workstations — no manual steps.
2. `.md` files can be opened in Typora from the file manager or command line.
3. A test document with fenced code blocks, tables, task lists, and images renders correctly on both platforms.
4. Typora is configured as a `.md` file association on both platforms.
