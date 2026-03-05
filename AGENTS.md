# AGENTS.md

## Skill routing

When the user wants to create, plan, write, update, transition, or review any documentation artifact (Vision, Journey, Epic, Story, Agent Spec, Spike, ADR, Persona, Runbook, Bug) or their supporting docs (architecture overviews, competitive analyses, journey maps), **always invoke the spec-management skill**. This includes requests like "write a spec", "let's plan the next feature", "create an ADR for this decision", "move the spike to Active", "add a user story", "create a runbook", "file a bug", or "update the architecture overview." The skill contains the artifact types, lifecycle phases, folder structure conventions, relationship rules, and validation procedures — do not improvise artifact creation outside the skill.

**For all task tracking and execution progress**, use the **execution-tracking** skill instead of any built-in todo or task system. This applies whether tasks originate from spec-management (implementation plans) or from standalone work. The execution-tracking skill bootstraps and operates the external task backend — it will install the CLI if missing, manage fallback if installation fails, and translate abstract operations (create plan, add task, set dependency) into concrete commands. Do not use built-in agent todos when this skill is available.

## Pre-implementation protocol (MANDATORY)

Implementation of any SPEC artifact (Epic, Story, Agent Spec, Spike) requires an execution-tracking plan **before** writing code. Invoke the spec-management skill — it enforces the full workflow.

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

## Issue Tracking

This project uses **bd (beads)** for all issue tracking. Do NOT use markdown TODOs or task lists. Invoke the **execution-tracking** skill for all bd operations — it provides the full command reference and workflow.
