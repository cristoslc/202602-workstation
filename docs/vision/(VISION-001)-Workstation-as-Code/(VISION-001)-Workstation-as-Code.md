---
title: "VISION-001: Workstation as Code"
artifact: VISION-001
status: Active
author: cristos
created: 2026-02-27
last-updated: 2026-03-03
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
| Dotfiles diverge across machines | Symlink-managed dotfiles, version-controlled |
| Secrets in plaintext or memory | Encrypted at rest, repo-safe |
| Platform-specific ad-hoc scripts | Unified roles with OS dispatch |
| "Works on my machine" configuration | Idempotent, repeatable provisioning |
| No audit trail for changes | Full git history of every configuration change |
| Painful machine migration | One-time data pull + continuous sync across fleet |
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

- **Phase-based provisioning** — Roles organized into phases (system, security, dev tools, desktop, dotfiles, gaming, sync) applied selectively or all at once.
- **Cross-platform OS dispatch** — Each role handles both macOS and Linux internally, abstracting platform differences.
- **Layered dotfile management** — Multiple dotfile layers (shared, secrets, platform-specific) deployed with file-level granularity and collision detection.
- **Encrypted secrets at rest** — Variables and sensitive config files encrypted in the repo, decrypted on-the-fly during provisioning, with pre-commit hooks to prevent plaintext leaks.
- **Interactive setup wizard** — TUI for first-run personalization, bootstrap mode selection, role/phase picking, secrets editing, and settings import/export.

### Data & sync

- **Machine migration** — Bulk data pull for documents, media, and code from an existing machine to a new one.
- **Ongoing sync** — User data synced across machines continuously; code working trees (including uncommitted changes) synced with branch isolation.
- **Settings export/import** — Encrypted capture and restore of application preferences that cannot be managed as dotfiles.

### Developer experience

- **Selective application** — Apply a single role or sub-task without re-running the full provisioning.
- **Verification** — Post-install checks confirm every tool is installed and correctly configured.
- **Extensibility** — Adding a new tool follows a documented pattern with cross-platform support.

See [architecture-overview.md](./architecture-overview.md) for the full system description including technology choices and implementation details.

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Persona | [PERSONA-001](../../persona/(PERSONA-001)-The-Multi-Machine-Developer/(PERSONA-001)-The-Multi-Machine-Developer.md) | The Multi-Machine Developer |
| Journey | [JOURNEY-001](../../journey/(JOURNEY-001)-Fresh-Machine-Bootstrap/(JOURNEY-001)-Fresh-Machine-Bootstrap.md) | Fresh Machine Bootstrap |
| Journey | [JOURNEY-002](../../journey/(JOURNEY-002)-Configuration-Evolution/(JOURNEY-002)-Configuration-Evolution.md) | Configuration Evolution |
| Journey | [JOURNEY-003](../../journey/(JOURNEY-003)-Machine-Migration/(JOURNEY-003)-Machine-Migration.md) | Machine Migration |
| Journey | [JOURNEY-004](../../journey/(JOURNEY-004)-Daily-Multi-Machine-Workflow/(JOURNEY-004)-Daily-Multi-Machine-Workflow.md) | Daily Multi-Machine Workflow |
| ADR | [ADR-002](../../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md) | Encryption at Rest for Personal Files |
| ADR | [ADR-003](../../adr/Adopted/(ADR-003)-Cross-Platform-Action-Bindings.md) | Cross-Platform Action Bindings |
| ADR | [ADR-004](../../adr/Adopted/(ADR-004)-Sync-App-Settings.md) | Sync App Settings |
| ADR | [ADR-005](../../adr/Adopted/(ADR-005)-TUI-Annotation-Secrets-Autodiscovery.md) | @tui Annotation-Based Secrets Autodiscovery |
| ADR | [ADR-006](../../adr/Adopted/(ADR-006)-Git-Repo-Detection-Journal-with-Sync-Boundary-Enforcement.md) | Git Repo Detection Journal with Sync Boundary Enforcement |
| Epic | [EPIC-001](../../epic/(EPIC-001)-Restic-Backup-Stack/(EPIC-001)-Restic-Backup-Stack.md) | Restic Backup Stack |
| Epic | [EPIC-002](../../epic/(EPIC-002)-Sync-User-Folders/(EPIC-002)-Sync-User-Folders.md) | Sync User Folders |
| Epic | [EPIC-003](../../epic/(EPIC-003)-Sync-App-Settings/(EPIC-003)-Sync-App-Settings.md) | Sync App Settings |
| Epic | [EPIC-004](../../epic/(EPIC-004)-Platform-Developer-Experience/(EPIC-004)-Platform-Developer-Experience.md) | Platform Developer Experience |
| Epic | [EPIC-007](../../epic/(EPIC-007)-Steam-Deck-Provisioning/(EPIC-007)-Steam-Deck-Provisioning.md) | Steam Deck Provisioning |
| Spec | [SPEC-001](../../spec/(SPEC-001)-Raycast-Sync/(SPEC-001)-Raycast-Sync.md) | Raycast Sync |
| Vision | [VISION-002](../(VISION-002)-Server-as-Code/(VISION-002)-Server-as-Code.md) | Server as Code (sibling — shared platform layer) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Active | 2026-02-27 | e883231 | Initial creation — project is already operational |
| Active | 2026-02-28 | 0cf0e98 | Narrowed scope — remote desktop/access moved to separate project |
| Active | 2026-03-01 | 75224f8 | Expanded scope — multi-workstation fleet management |
