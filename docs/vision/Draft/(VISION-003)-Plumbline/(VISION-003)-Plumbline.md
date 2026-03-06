---
title: "VISION-003: Plumbline"
artifact: VISION-003
status: Draft
author: cristos
created: 2026-03-05
last-updated: 2026-03-05
depends-on:
  - VISION-001
---

# VISION-003: Plumbline

## Problem

The provisioning engine built for VISION-001 (Workstation as Code) solves a real problem — but it solves it only for one person. The phase architecture, dotfile layering, secret encryption, cross-platform dispatch, fleet inventory, and TUI setup wizard are all general-purpose capabilities entangled with one user's personal configuration. Anyone who wants the same capabilities must fork the entire repo and surgically remove the personal bits, or start from scratch.

No open-source tool occupies this niche well. Ansible is too general-purpose and ceremony-heavy for personal workstations. Nix is powerful but demands a paradigm shift most developers won't make. Chezmoi manages dotfiles but not full-system provisioning. None of them offer an integrated story for phase-based provisioning, encrypted secrets, fleet management, and first-run onboarding — the combination that makes VISION-001 work.

## Vision

**Extract the generic provisioning engine from the workstation repo into Plumbline — a standalone, open-source tool that anyone can use to define their workstation (or server) as code.** The current 202602-workstation repo becomes one user's Plumbline configuration; the engine, conventions, and tooling become a shared project that others can adopt and extend.

Plumbline is the level — the reference line — that keeps your machines true. You define what a machine should look like; Plumbline makes it so, idempotently, across platforms, across your fleet.

## Target Audience

Developers and power users who:

- Want reproducible, version-controlled workstation setup without adopting Nix or writing raw Ansible
- Maintain one or more macOS and/or Linux machines
- Need encrypted secrets in a public or shared repo
- Value a guided first-run experience over a blank-slate config language
- Want to share provisioning patterns with others while keeping personal config private

## Value Proposition

| Without Plumbline | With Plumbline |
|-------------------|----------------|
| Fork someone's dotfiles repo, delete their stuff, hope it still works | `plumbline init` scaffolds your own config repo with the full engine |
| Invent your own phase/role/dotfile conventions | Opinionated but extensible conventions out of the box |
| Secrets management is DIY or absent | age-encrypted secrets integrated into the provisioning lifecycle |
| No onboarding — read the README and figure it out | Interactive TUI guides first-run setup, role selection, secrets editing |
| Single-machine assumption | Fleet inventory with per-machine overrides built in |
| macOS or Linux, pick one | Cross-platform dispatch is a first-class primitive in every role |

## Success Metrics

1. **Clean separation** — The Plumbline engine has zero references to any specific user's configuration. Personal config lives in a separate repo that depends on Plumbline.
2. **Init-to-apply** — A new user can run `plumbline init`, answer the TUI prompts, and `plumbline apply` a working baseline environment in under 10 minutes.
3. **Existing user migration** — The 202602-workstation repo migrates to use Plumbline as its engine with no loss of functionality.
4. **Community roles** — Third-party roles (e.g., "gaming on Linux", "data science on macOS") can be published, discovered, and composed without forking Plumbline itself.
5. **Upstream independence** — Users can update Plumbline (the engine) without their personal config being overwritten or conflicting.

## Non-Goals

- **Replacing Ansible/Nix/Chezmoi** — Plumbline is opinionated and narrower. It is not a general-purpose configuration management tool. Users who need Ansible's full power should use Ansible.
- **SaaS or hosted service** — Plumbline is a local CLI tool. No cloud accounts, no telemetry, no vendor lock-in.
- **Windows support** — macOS and Linux only, at least initially.
- **Enterprise fleet management** — This is for personal and small-team use. MDM, compliance policies, and centralized control planes are out of scope.

## Open Questions

- **Extraction boundary:** What is "engine" vs. "config"? The phase definitions, role runner, dotfile deployer, secret manager, and TUI are clearly engine. But some roles (e.g., "install Homebrew", "configure SSH") are so universal they might belong in Plumbline's standard library rather than user config.
- **Distribution:** Is Plumbline a Homebrew formula? A pip package? A single binary? The answer affects how users bootstrap it on a fresh machine (chicken-and-egg problem).
- **Role format:** Should Plumbline roles be Ansible roles (leveraging the existing ecosystem) or a simpler custom format? Ansible brings power but also complexity and a Python dependency.
- **Naming:** "Plumbline" is the working name. Validate availability (PyPI, Homebrew, GitHub, npm) before committing.

## Related Artifacts

| Type | ID | Title |
|------|----|-------|
| Vision | [VISION-001](../../(VISION-001)-Workstation-as-Code/(VISION-001)-Workstation-as-Code.md) | Workstation as Code (source project) |
| Vision | [VISION-002](../../(VISION-002)-Server-as-Code/(VISION-002)-Server-as-Code.md) | Server as Code (potential consumer) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-05 | c53c8bb | Initial creation |
