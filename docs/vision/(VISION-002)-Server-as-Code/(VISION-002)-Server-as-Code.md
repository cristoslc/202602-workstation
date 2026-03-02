---
title: "VISION-002: Server as Code"
artifact: VISION-002
status: Draft
author: cristos
created: 2026-03-01
last-updated: 2026-03-01
---

# VISION-002: Server as Code

## Problem

Home servers and personal infrastructure — media servers, backup targets, development VMs, self-hosted services — are configured by hand and never reproduced. When a server dies, rebuilding it means piecing together half-remembered commands, outdated wiki notes, and guesswork. Platform capabilities that every machine needs (backups, remote access, monitoring, security hardening) get reimplemented independently on each server and workstation, drifting apart over time.

## Vision

**Extend infrastructure-as-code from workstations to servers.** A shared platform layer handles the capabilities every machine needs — backups, remote access, security, monitoring — while server-specific roles handle the services only servers run. Defining a new server means declaring its role in inventory, not writing a new playbook from scratch.

The same provisioning model proven on workstations (VISION-001) applies to servers: idempotent, version-controlled, secrets-encrypted, and reproducible. Workstations and servers share a platform; they diverge only in what runs on top of it.

## Target audience

The same solo developer or homelab operator from VISION-001 who also maintains one or more servers (physical or virtual) alongside their workstations.

## Value proposition

| Without | With |
|---------|------|
| Server setup is ad-hoc, unreproducible | Declarative server roles, same toolchain as workstations |
| Platform capabilities reimplemented per machine type | Shared platform layer inherited by all machine types |
| Workstation and server configs drift independently | Single repo (or coordinated repos), shared roles, coherent fleet |
| Server rebuild requires archaeology | Server rebuild requires `./setup.sh` on a fresh host |

## Success metrics

1. **Platform reuse** — Shared platform roles (backups, security, remote access) run unmodified on both workstations and servers.
2. **Server bootstrap** — A fresh server reaches its target state from a single command.
3. **Separation of concerns** — Server-specific roles do not leak into workstation provisioning and vice versa.

## Non-goals

- **Cloud infrastructure provisioning** — This manages what runs *on* a server, not the server's existence. VM lifecycle, networking, and DNS are out of scope (or handled by separate infrastructure-as-code tooling).
- **Container orchestration** — Kubernetes, Docker Compose stacks, and similar are workloads *deployed to* a server, not part of the server provisioning itself.
- **Multi-tenant or team use** — Same single-user model as VISION-001.

## Open questions

- Should this live in the same repository as VISION-001 or in a separate project? Shared platform roles argue for colocation; divergent lifecycles and audiences argue for separation.
- What is the minimum viable server profile? SSH + backups + monitoring, or does it include application services (media, DNS, etc.)?
- How does the TUI adapt? Servers may not have a desktop session — headless bootstrap may be required.

## Related artifacts

| Type | ID | Title |
|------|----|-------|
| Vision | [VISION-001](../(VISION-001)-Workstation-as-Code/(VISION-001)-Workstation-as-Code.md) | Workstation as Code (foundation) |

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-03-01 | 75224f8 | Initial creation |
