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
| **Marked 2** | macOS only | Full | Yes (file watch) | No (preview only) | Proprietary (SetApp / $14) | Current tool. Gold standard for preview UX. |
| **Mark Text** | macOS, Linux, Windows | Full | Yes (built-in) | Yes (WYSIWYG) | MIT | Electron-based. Last release 2022 — maintenance unclear. |
| **Typora** | macOS, Linux, Windows | Full | Yes (inline) | Yes (inline WYSIWYG) | Proprietary ($15) | Polished. Actively maintained. |
| **Apostrophe** | Linux (GNOME) | Partial (via cmark) | Yes (side panel) | Yes (split pane) | GPL-3.0 | GNOME-native, Flatpak. GFM extensions may need verification. |
| **Ghostwriter** | Linux, Windows | Full (via cmark-gfm) | Yes (side panel) | Yes (split pane) | GPL-3.0 | KDE/Qt-based, ships with cmark-gfm processor. |

## Strategy options

### Option A — Keep Marked 2 on macOS, add a Linux previewer

- macOS: Marked 2 via SetApp (status quo, no provisioning change needed).
- Linux: Apostrophe or Ghostwriter via Flatpak/package manager.
- Pro: Best-in-class UX on macOS. Minimal disruption.
- Con: Two different tools to learn; no config parity.

### Option B — Single cross-platform tool on both platforms

- Replace Marked 2 with Mark Text or Typora everywhere.
- Pro: Identical UX and config on both platforms.
- Con: Gives up Marked 2's superior preview-only workflow; Mark Text maintenance risk.

### Option C — Marked 2 on macOS + Ghostwriter on Linux (recommended starting point)

- macOS: Marked 2 via `mas` role or SetApp (capture in provisioning either way).
- Linux: Ghostwriter via system package (`ghostwriter` is in Fedora/Ubuntu repos and Flathub).
- Pro: Native-feeling app per platform. Both support GFM, live preview, and custom CSS.
- Con: Different tools, but both are split-pane previewer+editor — close enough in workflow.

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Mark Text abandoned (last release v0.17.1, Aug 2022) | Stuck on outdated Electron, security issues | Prefer actively maintained alternatives (Ghostwriter, Apostrophe) |
| Ghostwriter UX gap vs Marked 2 | Friction on Linux | Evaluate in spike; accept minor parity gap if core preview works |
| SetApp Marked 2 not capturable in provisioning | macOS install stays manual | Check if Marked 2 is also on `mas` (Mac App Store CLI); if so, provision via `mas` role |
| Flatpak sandboxing limits file access | Previewer can't watch project directories | Use system package where available; configure Flatpak overrides if needed |

## Research

| ID | Question | Status | Blocks |
|----|----------|--------|--------|
| SPIKE-002 | Evaluate Ghostwriter + Apostrophe on Linux: GFM support, live-reload, file-watch, custom CSS, desktop integration | Planned | Tool selection and implementation |

## Success Criteria

1. `make apply` on a Linux workstation installs a markdown previewer with GFM support and live-reload.
2. `.md` files can be opened in the previewer from the file manager or command line.
3. On macOS, Marked 2 (or chosen replacement) is captured in the provisioning pipeline — not a manual SetApp install.
4. Both platforms can preview a test document with fenced code blocks, tables, task lists, and images without rendering errors.
