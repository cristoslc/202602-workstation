# AGENTS.md

## Skill routing

When the user wants to create, plan, write, update, transition, or review any documentation artifact (Vision, Journey, Epic, Story, Agent Spec, Spike, ADR, Persona) or their supporting docs (architecture overviews, competitive analyses, journey maps), **always invoke the spec-management skill**. This includes requests like "write a spec", "let's plan the next feature", "create an ADR for this decision", "move the spike to Active", "add a user story", or "update the architecture overview." The skill contains the procedures, formats, and validation rules — do not improvise artifact creation from the reference tables below.

**For all task tracking and execution progress**, use the **execution-tracking** skill instead of any built-in todo or task system. This applies whether tasks originate from spec-management (implementation plans) or from standalone work. The execution-tracking skill bootstraps and operates the external task backend — it will install the CLI if missing, manage fallback if installation fails, and translate abstract operations (create plan, add task, set dependency) into concrete commands. Do not use built-in agent todos when this skill is available.

## Documentation lifecycle workflow

### Encryption-at-rest policy

All personalized or user-specific files MUST be age-encrypted before committing to the repo. No plaintext personal data at rest in git.

**What counts as personalized:** application preferences, plugin/extension lists, profile backups, dotfiles exported from a running system — anything that reveals the user's identity, username, installed software, or workflow configuration.

**What does NOT need encryption:** generic configs shipped with the repo (e.g., SSH agent socket path, Hammerspoon keybindings, Espanso `backend: auto`), templates with placeholder tokens, and documentation.

**How to encrypt:** Use `age -r <pubkey>` with the public key from `.sops.yaml`. Store the `.age` file in `macos/files/<app>/` and gitignore the plaintext source. Decrypt during import with `age -d -i <keyfile>`.

**Current encrypted exports:**

| App | Encrypted file | Plaintext (gitignored) |
|-----|---------------|----------------------|
| iTerm2 | `macos/files/iterm2/iterm2.plist.age` | `macos/dotfiles/iterm2/.config/iterm2/com.googlecode.iterm2.plist` |
| Raycast | `macos/files/raycast/raycast.rayconfig.age` | (temp file, deleted after import) |
| Espanso snippets (from Raycast) | `shared/secrets/dotfiles/espanso/.config/espanso/match/raycast.yml.sops` | (decrypted by secrets-manager, stowed to `~/.config/espanso/match/raycast.yml`) |
| Stream Deck profiles | `macos/files/stream-deck/streamdeck.backup.age` | (temp file, deleted after import) |
| Stream Deck plugins | `macos/files/stream-deck/plugins.json.age` | `macos/files/stream-deck/plugins.json` |
| OpenIn | `macos/files/openin/openin.plist.age` | `macos/files/openin/openin.plist` |

When adding a new app export, follow this pattern: export plaintext locally, age-encrypt for the repo, gitignore the plaintext, decrypt on import. See [ADR-002](docs/adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) for the decision record.

### General rules

- Each top-level directory within `docs/` must include a `README.md` with an explanation and index.
- All artifacts MUST be titled AND numbered.
  - Good: `(ADR-192)-Multitenant-Gateway-Architecture.md`
  - Bad: `{ADR} Multitenant Gateway Architectre (#192).md`
- **Every artifact is the authoritative record of its own lifecycle.** Each must embed a lifecycle table in its frontmatter tracking every phase transition with date, commit hash, and notes. Index files (`list-<type>.md`) mirror this data as a project-wide dashboard but are not the source of truth — the artifact is.
- Each doc-type directory keeps a single lifecycle index (`list-<type>.md`, e.g., `list-specs.md`) with one table per phase and commit hash stamps for auditability.

### Artifact types

Phases are **available waypoints**, not mandatory gates. Artifacts may skip intermediate phases (e.g., Draft → Adopted) when the work is completed conversationally in a single session. The lifecycle table records only the phases the artifact actually occupied. **Abandoned** is a universal end-of-life phase available from any state — it signals the artifact was intentionally not pursued.

| Type | Path | Format | Phases |
|------|------|--------|--------|
| Product Vision | `docs/vision/` | Folder containing titled `.md` + supporting docs (competitive analysis, market research, etc.) | Draft → Active → Sunset · Abandoned |
| User Journey | `docs/journey/` | Folder containing titled `.md` with embedded Mermaid journey diagram + supporting docs | Draft → Validated · Archived · Abandoned |
| Epics | `docs/epic/` | Folder containing titled `.md` + supporting docs | Proposed → Active → Complete · Abandoned |
| User Story | `docs/story/` | Markdown file per story | Draft → Ready → Implemented · Abandoned |
| Agent Specs | `docs/spec/` | Folder containing titled `.md` + supporting docs | Draft → Review → Approved → Implemented → Deprecated · Abandoned |
| Research / Spikes | `docs/research/` | Folder containing titled `.md` (not `README.md`) | Planned → Active → Complete · Abandoned |
| ADRs | `docs/adr/` | Markdown file in `<Phase>/` subdirectory (e.g., `docs/adr/Adopted/(ADR-001)-Title.md`) | Draft → Proposed → Adopted → Retired · Superseded · Abandoned |
| Personas | `docs/persona/` | Folder containing titled `.md` + supporting docs (interview notes, research data) | Draft → Validated → Archived · Abandoned |

### Artifact hierarchy

```
Product Vision (VISION-NNN) — one per product or product area
  ├── User Journey (JOURNEY-NNN) — end-to-end user experience map
  ├── Epic (EPIC-NNN) — strategic initiative / major capability
  │     ├── User Story (STORY-NNN) — atomic user-facing requirement
  │     ├── Agent Spec (SPEC-NNN) — behavior contract
  │     │     └── Implementation Plan (via execution-tracking)
  │     └── ADR (ADR-NNN) — architectural decision (cross-cutting)
  ├── Persona (PERSONA-NNN) — user archetype (cross-cutting)
  └── Research Spike (SPIKE-NNN) — can attach to any artifact ↑
```

**Relationship rules:**
- Every Epic MUST reference a parent Vision in its frontmatter.
- Every User Journey MUST reference a parent Vision.
- Every User Story MUST reference a parent Epic.
- Every Agent Spec MUST reference a parent Epic.
- Spikes can belong to any artifact type (Vision, Journey, Epic, Story, Agent Spec, ADR, Persona). The owning artifact controls all spike tables.
- ADRs are cross-cutting: they link to all affected Epics/Agent Specs but are not owned by any single one.
- Personas are cross-cutting: they link to all Journeys, Stories, and other artifacts that reference them but are not owned by any single one.
- An artifact may only have one parent in the hierarchy but may reference siblings or cousins via `related` links.

For detailed procedures, see the **spec-management** skill (referenced in Skill routing above).
