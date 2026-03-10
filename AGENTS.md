# AGENTS.md

<!-- swain governance — do not edit this block manually -->

## Skill routing

When the user wants to create, plan, write, update, transition, or review any documentation artifact (Vision, Journey, Epic, Story, Agent Spec, Spike, ADR, Persona, Runbook, Bug) or their supporting docs (architecture overviews, competitive analyses, journey maps), **always invoke the swain-design skill**. This includes requests like "write a spec", "let's plan the next feature", "create an ADR for this decision", "move the spike to Active", "add a user story", "create a runbook", "file a bug", or "update the architecture overview." The skill contains the artifact types, lifecycle phases, folder structure conventions, relationship rules, and validation procedures — do not improvise artifact creation outside the skill.

**For all task tracking and execution progress**, use the **swain-do** skill instead of any built-in todo or task system. This applies whether tasks originate from swain-design (implementation plans) or from standalone work. The swain-do skill bootstraps and operates the external task backend — it will install the CLI if missing, manage fallback if installation fails, and translate abstract operations (create plan, add task, set dependency) into concrete commands. Do not use built-in agent todos when this skill is available.

## Pre-implementation protocol (MANDATORY)

Implementation of any SPEC artifact (Epic, Story, Agent Spec, Spike) requires a swain-do plan **before** writing code. Invoke the swain-design skill — it enforces the full workflow.

## Issue Tracking

This project uses **bd (beads)** for all issue tracking. Do NOT use markdown TODOs or task lists. Invoke the **swain-do** skill for all bd operations — it provides the full command reference and workflow.

<!-- end swain governance -->

### Ansible role conventions

Never use `ansible.builtin.debug` to print reminder messages in tasks. Ansible output scrolls past and messages get lost. Every role must either **actually install the application** or **not exist at all**. If there's no package manager support, download and install from the release artifacts directly (GitHub releases, vendor URLs, etc.).

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

