---
title: "VISION-001: Workstation as Code"
status: Active
author: cristos
created: 2026-02-27
last-updated: 2026-03-01
---

# VISION-001: Workstation as Code

## Problem

Setting up a development workstation is slow, manual, and error-prone. Every fresh install or new machine means hours of reinstalling tools, re-creating dotfiles, re-entering credentials, and remembering obscure configuration steps — only to end up with an environment that drifts from every other machine you use. Secrets are scattered. Configs are fragile. Platform differences between macOS and Linux multiply the burden.

There is no good way to treat a workstation like infrastructure: version-controlled, reproducible, and recoverable.

When you maintain multiple workstations, the problem compounds. Each machine drifts on its own trajectory — different tools enabled, different versions installed, different phases applied. There is no single source of truth for what each machine should look like, and no mechanism for ensuring that shared configurations stay coherent across the fleet.

## Vision

**Make development workstations fungible — whether you have one or five.** Run a single command on a fresh macOS or Linux machine and get a fully configured development environment — tools installed, dotfiles deployed, secrets decrypted, keybindings set, applications configured — in minutes, not hours.

The workstation fleet is defined in code, versioned in git, and applied idempotently. Changing a configuration means editing a file and re-running the playbook. Adding a machine means declaring it in the repo and bootstrapping. Losing a machine means nothing, because every machine's desired state lives in the repo. Machines that share roles stay coherent; machines that differ do so explicitly.

## Target audience

A solo developer (or small team) who:

- Maintains multiple macOS and Linux machines that should stay in sync
- Values reproducibility and auditability over manual flexibility
- Wants secrets encrypted at rest in a public repository
- Needs to provision a fresh machine quickly after hardware failure, upgrades, or OS reinstalls

## Value proposition

| Without this project | With this project |
|---------------------|-------------------|
| Hours of manual setup per machine | Single-command bootstrap (~10 min unattended) |
| Dotfiles diverge across machines | Stow-managed dotfiles, version-controlled |
| Secrets in plaintext or memory | SOPS + age encryption, repo-safe |
| Platform-specific ad-hoc scripts | Unified Ansible roles with OS dispatch |
| "Works on my machine" configuration | Idempotent, repeatable provisioning |
| No audit trail for changes | Full git history of every configuration change |
| Painful machine migration | `rsync` data pull + Syncthing/Unison for ongoing sync |
| Each machine configured ad-hoc | Fleet defined in inventory — shared defaults, per-machine overrides |
| Drift between machines invisible | One repo, one truth — diff any machine's config against any other |

## Success metrics

1. **Bootstrap time** — A fresh machine reaches a usable development environment in under 15 minutes of unattended run time.
2. **Idempotency** — Running `make apply` twice produces no changes on the second run.
3. **Cross-platform parity** — The same role set produces functionally equivalent environments on macOS and Linux.
4. **Secret safety** — Zero plaintext secrets committed to git (enforced by pre-commit hooks).
5. **Recovery confidence** — Losing a machine requires only a new age key and `./setup.sh` to fully rebuild.
6. **Fleet coherence** — Shared roles produce identical outcomes on every machine they target; per-machine variation is limited to explicit overrides in inventory.

## Non-goals

- **Centralized MDM** — This manages a personal workstation fleet, not an enterprise device fleet. There is no central control plane pushing policy — each machine self-provisions from the same repo.
- **Server provisioning** — Servers are a different workload profile with different roles and lifecycle; see [VISION-002](../(VISION-002)-Server-as-Code/(VISION-002)-Server-as-Code.md). A shared platform layer may emerge across both visions.
- **Container/VM provisioning** — The scope is bare-metal workstation setup, not cloud infrastructure or container orchestration.
- **Application-level configuration** — Tools are installed and pointed at config files, but in-app settings that require GUI interaction (Setapp, MAS sign-in, Accessibility permissions) remain manual.
- **Remote desktop / remote access** — Screen sharing, VNC/RDP clients, hardware KVM, and relay infrastructure are managed in a separate project.
- **Multi-user support** — One user per machine, one age key, one repo.

## Capabilities

### Multi-machine fleet

- **Declarative inventory** — Every workstation is defined in the repo with its platform and enabled phases. Adding a machine is a config change, not a new playbook.
- **Selective convergence** — Each machine converges only the phases and roles it declares. Not every workstation needs gaming or compliance — differences are explicit, not accidental.
- **Shared role coherence** — Roles applied to multiple machines produce consistent results everywhere they run.

### Core platform

- **Phase-based Ansible provisioning** — Roles organized into phases (system, security, dev tools, desktop, dotfiles, gaming, sync) applied selectively or all at once.
- **Cross-platform OS dispatch** — Each role handles both macOS and Linux internally via platform-specific task includes.
- **GNU Stow dotfile layering** — Four stow layers (shared, shared-secrets, platform, platform-secrets) deployed with `--no-folding` for file-level symlinks.
- **SOPS + age secrets management** — Encrypted variables and dotfiles, decrypted on-the-fly during Ansible runs, with pre-commit hooks for safety.
- **Textual TUI** — Python-based interactive setup wizard for first-run personalization, bootstrap mode selection, role/phase picking, secrets editing, and settings import/export.

### Data & sync

- **Machine migration** — Bulk data pull via SSH/rsync for Documents, Pictures, Music, Videos, Downloads.
- **Ongoing sync** — Syncthing (hub-and-spoke) for user data, Unison for git working trees with uncommitted changes.
- **Settings export/import** — Age-encrypted capture of iTerm2, Raycast, Stream Deck, and OpenIn preferences.

### Developer experience

- **Selective application** — `make apply ROLE=git` for single-role runs, tags for sub-task granularity.
- **Verification** — `make verify` post-install checks on all tools; per-role verification available.
- **Extensibility** — Adding a new tool follows a documented pattern: create/extend a role, add platform includes, wire into a phase playbook.

## Architecture (summary)

```
./setup.sh  →  Textual TUI  →  Ansible playbooks
                                    ├── shared/roles/ (45+ roles, OS dispatch)
                                    ├── macos/roles/ (Homebrew, MAS, defaults)
                                    ├── linux/roles/ (apt, system, desktop-env)
                                    └── Stow dotfile deployment (4 layers)

Secrets: SOPS + age  |  Signing: 1Password SSH  |  Supply chain: pinned + checksums
```

See `architecture-overview.md` (forthcoming) for the full system description.

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Persona | [PERSONA-001](../../persona/(PERSONA-001)-The-Multi-Machine-Developer/(PERSONA-001)-The-Multi-Machine-Developer.md) | The Multi-Machine Developer |
| Journey | [JOURNEY-001](../../journey/(JOURNEY-001)-Fresh-Machine-Bootstrap/(JOURNEY-001)-Fresh-Machine-Bootstrap.md) | Fresh Machine Bootstrap |
| Journey | [JOURNEY-002](../../journey/(JOURNEY-002)-Configuration-Evolution/(JOURNEY-002)-Configuration-Evolution.md) | Configuration Evolution |
| Journey | [JOURNEY-003](../../journey/(JOURNEY-003)-Machine-Migration/(JOURNEY-003)-Machine-Migration.md) | Machine Migration |
| ADR | [ADR-002](../../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) | Encryption at Rest for Personal Files |
| PRD | [PRD-001](../../prd/Draft/(PRD-001)-Raycast-Sync/(PRD-001)-Raycast-Sync.md) | Raycast Sync |
| PRD | [PRD-002 (Draft)](../../prd/Draft/(PRD-002)-Restic-Backup-Stack/(PRD-002)-Restic-Backup-Stack.md) | Restic Backup Stack |
| PRD | [PRD-003](../../prd/Draft/(PRD-003)-Sync-User-Folders/(PRD-003)-Sync-User-Folders.md) | Sync User Folders |
| PRD | [PRD-004](../../prd/Implemented/(PRD-004)-Markdown-Viewer/(PRD-004)-Markdown-Viewer.md) | Markdown Viewer |
| Vision | [VISION-002](../(VISION-002)-Server-as-Code/(VISION-002)-Server-as-Code.md) | Server as Code (sibling — shared platform layer) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Active | 2026-02-27 | e883231 | Initial creation — project is already operational |
| Active | 2026-02-28 | 0cf0e98 | Narrowed scope — remote desktop/access moved to separate project |
| Active | 2026-03-01 | 75224f8 | Expanded scope — multi-workstation fleet management |
