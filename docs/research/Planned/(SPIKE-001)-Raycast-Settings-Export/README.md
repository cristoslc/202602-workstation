# SPIKE-001: Raycast Settings Export

**Status:** Planned
**Gate:** Pre-implementation (blocks PRD-001 delivery)
**PRD:** [(PRD-001) Raycast Sync](../../../prd/Draft/(PRD-001)-Raycast-Sync/(PRD-001)-Raycast-Sync.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-02-25 | 03eb670 | Initial creation |

---

## Question

What is the most reliable way to export, version-control, and re-import Raycast settings so that bootstrap yields a fully-configured instance?

## PRD risks addressed

- Opaque/binary settings format (need to determine if diffs are reviewable)
- Embedded secrets in export (need to audit what the export contains)
- Schema stability across Raycast updates

## Dependencies

- None (investigation only — requires a configured Raycast instance on the source machine).

## Blocks

- PRD-001 implementation (can't build the sync mechanism without knowing the format).

## Approaches to investigate

### A. Raycast manual export (`Raycast > Settings > Advanced > Export`)

Raycast has a built-in export that produces a `.rayconfig` file.

**Investigate:**
- What format is the `.rayconfig` file? (ZIP? JSON? plist? binary?)
- Does it include extension data, hotkeys, snippets, quicklinks, and preferences?
- Does it include auth tokens, API keys, or session data?
- Can it be imported non-interactively (CLI or URL scheme)?
- Is the format stable across Raycast versions?

### B. Preferences plist capture (`~/Library/Preferences/com.raycast.macos.plist`)

Raycast stores preferences in a standard macOS defaults domain.

**Investigate:**
- Does the plist contain the full configuration or just general preferences?
- Are extensions/hotkeys stored elsewhere (e.g., `~/Library/Application Support/com.raycast.macos/`)?
- Can the plist be converted to XML for readable diffs (`plutil -convert xml1`)?
- Does deploying via Stow (symlink) work, or does Raycast require the file at the real path?
- Does `defaults import com.raycast.macos <file>` work for restore?

### C. `raycast://` URL scheme for scripted export

Raycast supports deep links (`raycast://extensions/...`).

**Investigate:**
- Is there a `raycast://export` or `raycast://settings` URL scheme?
- Can export be triggered programmatically from an Ansible task?
- Does this require Raycast to be running with an active GUI session?

### D. Application Support directory capture

Some Raycast data may live in `~/Library/Application Support/com.raycast.macos/`.

**Investigate:**
- What lives here (databases, caches, extension state)?
- Is any of it required for a full settings restore?
- Is it small enough to version-control?

## Go/no-go criteria

- **Go:** At least one approach produces a complete, human-reviewable settings artifact that can be restored non-interactively (or with a single manual import step) and does not embed secrets.
- **No-go:** All approaches produce opaque blobs, require Raycast Pro cloud sync, or embed unstrippable secrets.

## Pivot if no-go

Document Raycast configuration as a `post-install.md` checklist item with screenshots. Accept manual setup as the cost of using a closed-source launcher. Evaluate whether Raycast's hotkey management should be delegated entirely to Hammerspoon (via the action registry) to minimize what needs reconfiguring.
