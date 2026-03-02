---
title: "SPIKE-001: Raycast Settings Export"
artifact: SPIKE-001
status: Complete
author: cristos
created: 2026-02-25
last-updated: 2026-02-25
gate: Pre-implementation (blocks SPEC-001 delivery)
linked-specs:
  - SPEC-001
---

# SPIKE-001: Raycast Settings Export

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-02-25 | dfa9e8d | Initial creation |
| Complete | 2026-02-25 | 20fb970 | Investigation complete; go decision |

---

## Question

What is the most reliable way to export, version-control, and re-import Raycast settings so that bootstrap yields a fully-configured instance?

## Risks addressed

- Opaque/binary settings format (need to determine if diffs are reviewable)
- Embedded secrets in export (need to audit what the export contains)
- Schema stability across Raycast updates

## Dependencies

- None (investigation only — requires a configured Raycast instance on the source machine).

## Blocks

- SPEC-001 implementation (can't build the sync mechanism without knowing the format).

---

## Findings

### Where Raycast stores its data

| Location | Size | Contents |
|----------|------|----------|
| `~/Library/Preferences/com.raycast.macos.plist` | ~420 KB | General preferences only (global hotkey, appearance, text size, browser pref). **No hotkeys, snippets, or quicklinks.** |
| `~/Library/Application Support/com.raycast.macos/` | ~226 MB | Bundled Node.js (104 MB), extension cache (30 MB), RaycastWrapped (69 MB), **encrypted SQLite databases** (~10 MB) |
| `raycast-enc.sqlite` | 9 MB | Encrypted — stores hotkeys, snippets, quicklinks, extension config |
| `raycast-activities-enc.sqlite` | 1.1 MB | Encrypted — usage history |

The real configuration (hotkeys, snippets, quicklinks, extension settings) lives in `raycast-enc.sqlite`, an encrypted SQLite database. The plist only covers general preferences.

### Approach A: `.rayconfig` export — GO

Raycast's built-in export (Settings > Advanced > Export) produces a `.rayconfig` file containing the full configuration: extensions, hotkeys, snippets, quicklinks, and preferences. Format details require hands-on inspection (see remaining TODO below), but this is the only sanctioned full-export path.

**Import:** `open <file>.rayconfig` triggers Raycast's import wizard (GUI dialog). Semi-interactive — acceptable for an interactive bootstrap session.

**Deeplink for re-export:** `open "raycast://extensions/raycast/raycast/export-settings-data"` opens the export UI. After clicking "Always Open Command" once, the deeplink confirmation is suppressed on future invocations. The file-save dialog still requires interaction.

### Approach B: Plist capture — SUPPLEMENT ONLY

- `defaults export com.raycast.macos - | plutil -convert xml1 -o <file> -` captures general prefs as human-readable XML.
- `defaults import com.raycast.macos <file>` restores them.
- **Stow symlinks do not work** — macOS `cfprefsd` caches plists in memory and writes to the real path.
- Covers only: global hotkey, appearance, text size, preferred browser, skin tone, UI prefs.
- Missing: hotkeys, snippets, quicklinks, extension config (all in encrypted SQLite).

### Approach C: `raycast://` URL scheme — NO STANDALONE PATH

- `raycast://extensions/raycast/raycast/export-settings-data` opens export UI.
- `raycast://extensions/raycast/raycast/import-settings-data` opens import UI.
- Both require GUI interaction (file dialogs). No silent/headless mode.
- Useful as a convenience shortcut, not as a non-interactive mechanism.

### Approach D: Application Support directory — NOT VIABLE

- 226 MB total, mostly regenerable (Node.js runtime, extension cache, Wrapped).
- Core databases are encrypted (`raycast-enc.sqlite`), not inspectable or diff-able.
- Direct file copy while Raycast is running risks WAL corruption.
- Not equivalent to `.rayconfig` — different scope, no password protection.

### Automation pathways exhausted

| Pathway | Result |
|---------|--------|
| CLI (`npx ray`) | Extension dev tool only, no settings access |
| AppleScript / JXA | No scripting dictionary exposed |
| Script Commands / Extensions API | Cannot invoke internal Raycast commands |
| Community CLI (`pomdtr/ray`) | Deeplink wrapper, still triggers GUI dialogs |
| `defaults` manipulation | No export trigger key |
| System Events (Accessibility) | Fragile GUI scripting, breaks on updates |
| Cloud Sync API | No public API |
| Scheduled Exports (Pro) | GUI-configured schedule only, requires Pro |

**No fully non-interactive export path exists.** Raycast intentionally keeps its config in encrypted storage with no programmatic extraction.

---

## Decision: GO

The go/no-go criteria specified: "At least one approach produces a complete settings artifact that can be restored with a single manual import step and does not embed secrets."

**Recommended approach — age-encrypted `.rayconfig` export:**

1. **`.rayconfig` file without password** — exported on-demand via GUI or deeplink. Age-encrypted with the repo's public key and committed as `macos/files/raycast/raycast.rayconfig.age`.
2. **`make export-raycast` Makefile target** — opens Raycast export UI via deeplink, waits for user to save, age-encrypts the result, cleans up plaintext.
3. **Ansible import task** — during bootstrap, decrypts the `.age` file to `/tmp/`, opens it (triggers Raycast import dialog), pauses for user confirmation, then deletes the plaintext.

This accepts a single interactive step (import dialog on fresh machine) as the cost of using a closed-source launcher — acceptable since workstation bootstrap is always run interactively on a Mac. No password to manage — the age key infrastructure already handles encryption/decryption.

### Remaining TODO (during SPEC-001 implementation)

- [ ] Perform the actual export and inspect `.rayconfig` format (ZIP? JSON? encrypted blob?)
- [ ] Audit export contents for embedded secrets before first `make export-raycast`

---

## References

- Raycast deeplinks manual: https://manual.raycast.com/deeplinks
- Raycast v1.22.0 changelog (export feature): https://www.raycast.com/changelog/1-22-0
- Raycast v1.59.0 changelog (scheduled exports): https://www.raycast.com/changelog/1-59-0
- Raycast Cloud Sync manual: https://manual.raycast.com/cloud-sync
- Community CLI (`pomdtr/ray`): https://github.com/pomdtr/ray
