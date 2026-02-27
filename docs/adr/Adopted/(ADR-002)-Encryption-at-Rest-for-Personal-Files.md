# ADR-002: Encryption at Rest for Personal Files

**Status:** Adopted
**Date:** 2026-02-27
**Author:** cristos
**Affects:** All export/import flows (iTerm2, Raycast, Stream Deck profiles, Stream Deck plugins)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Adopted | 2026-02-27 | d546629 | Created directly as Adopted; implementation complete |

---

## Context

The repo stores application settings exports alongside infrastructure-as-code (Ansible roles, stow packages, scripts). Some of these exports contain personalized data — home directory paths, usernames, installed plugin inventories, workflow configurations.

Prior to this decision, encryption was applied inconsistently:

| Export | Before | Personal data exposed |
|--------|--------|-----------------------|
| Raycast config | age-encrypted | None |
| Stream Deck profiles | age-encrypted | None |
| iTerm2 plist | **plaintext** | `/Users/<username>`, window geometry, profile GUIDs |
| Stream Deck plugins | **plaintext** (newly added) | Installed plugin names, UUIDs, versions |

The Raycast and Stream Deck backup exports already followed the correct pattern: age-encrypt before committing, decrypt during import. The iTerm2 plist was committed as plaintext XML in the stow package directory, and the newly added plugin list was written as plaintext JSON/HTML.

The repo is **public** — it must be visible from bootstrap machines without pre-authenticated git access. This makes plaintext personal data in git history a direct exposure, not a hypothetical risk.

## Decision

**All personalized or user-specific files must be age-encrypted before committing to the repo. No plaintext personal data at rest in git.**

### What counts as personalized

- Application preferences exported from a running system
- Plugin, extension, or add-on inventories
- Profile backups
- Any file that reveals the user's identity, username, installed software, or workflow configuration

### What does NOT need encryption

- Generic configs shipped with the repo (e.g., SSH agent socket path, Hammerspoon keybindings, Espanso `backend: auto`)
- Templates with placeholder tokens (e.g., `${AGE_PUBLIC_KEY}`)
- Documentation, scripts, and infrastructure code

### Standard pattern

Every app export follows the same lifecycle:

1. **Export:** capture settings locally, then `age -r <pubkey>` encrypt to `macos/files/<app>/<file>.age`
2. **Commit:** only the `.age` file is tracked in git
3. **Gitignore:** the plaintext source is listed in `.gitignore`
4. **Import:** `age -d -i <keyfile>` decrypt to the local target path (stow dir, temp file, etc.)

The age public key is read from `.sops.yaml`. The private key lives at `~/.config/sops/age/keys.txt` (never committed).

### Current encrypted exports

| App | Encrypted file (committed) | Plaintext (gitignored) |
|-----|---------------------------|----------------------|
| iTerm2 | `macos/files/iterm2/iterm2.plist.age` | `macos/dotfiles/iterm2/.config/iterm2/com.googlecode.iterm2.plist` |
| Raycast | `macos/files/raycast/raycast.rayconfig.age` | temp file, deleted after import |
| Stream Deck profiles | `macos/files/stream-deck/streamdeck.backup.age` | temp file, deleted after import |
| Stream Deck plugins | `macos/files/stream-deck/plugins.json.age` | `macos/files/stream-deck/plugins.json` |

## Consequences

### Positive

- **Consistent security posture** — every personalized file gets the same treatment, no exceptions to remember
- **Defense in depth** — even if the repo is exposed, personal data is encrypted
- **Clear pattern for new exports** — when adding a new app export, the encrypt/gitignore/decrypt pattern is documented and enforced
- **Git history is clean** — no personal data in any commit, past or future

### Negative

- **Extra step in export/import** — each flow requires an `age` encrypt or decrypt call (mitigated: already the pattern for 2 of 4 exports)
- **Key dependency** — import flows require the age private key; a machine without it cannot decrypt (mitigated: key transfer is already handled by `make key-send` / `make key-receive`)
- **Plaintext needed locally** — some files (iTerm2 plist) must exist in plaintext for the app to read them; gitignore prevents accidental commits but doesn't prevent local exposure (acceptable: full-disk encryption handles local-at-rest)

### Neutral

- The `.sops.yaml` creation rules for `*/secrets/*` are unchanged. SOPS handles secrets (API keys, passwords); `age` CLI handles personal-but-not-secret exports. Both use the same key pair.

## Alternatives Considered

### SOPS for all personal files — Rejected

SOPS supports YAML, JSON, ENV, and INI formats. It cannot handle binary files or XML plists. Age CLI handles arbitrary files, which is what we need for plist and `.rayconfig` exports.

### Commit plaintext and rely on repo obscurity — Rejected

The repo is public by design (bootstrap machines need unauthenticated clone access). Plaintext personal data would be directly visible to anyone. Even if the repo were made private, git history is permanent — data committed in plaintext stays in history even after deletion. Encryption at rest eliminates this class of risk entirely.

### Exclude personal files from git entirely — Rejected

These exports are the whole point of the repo — syncing settings across machines. Excluding them would require a separate sync mechanism (Syncthing, cloud storage), adding complexity and another failure mode. Encrypting in-repo keeps everything in one place.
