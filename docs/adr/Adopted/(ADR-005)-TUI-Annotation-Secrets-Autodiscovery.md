---
title: "ADR-005: @tui Annotation-Based Secrets Autodiscovery"
artifact: ADR-005
status: Adopted
author: cristos
created: 2026-03-02
last-updated: 2026-03-02
linked-research:
  - SPIKE-002
---

# ADR-005: @tui Annotation-Based Secrets Autodiscovery

## Context

The workstation provisioning system collects secrets (API keys, passwords, hostnames) during bootstrap via a TUI wizard. The list of secrets was maintained as hand-curated `SecretField` arrays in `scripts/setup_tui/lib/secrets.py` and duplicated in `scripts/first-run.py`. Every time a role added a new secret, a developer had to manually add entries to 2-3 files. Forgotten entries meant secrets silently stayed empty until a broken tool exposed the gap.

This approach does not scale as the role count grows, and the duplication between `secrets.py` and `first-run.py` was a maintenance liability.

## Decision

Annotate secret variables in each role's `defaults/main.yml` with structured YAML comments using a `@tui` directive format:

```yaml
# @tui secret password label="Restic repo password"
restic_repo_password: ""
```

A scanner (`scripts/setup_tui/lib/var_scanner.py`) reads these annotations at TUI startup and dynamically builds the `SecretField` list. The source of truth for which variables are secrets lives next to the default values themselves — one file to edit per role.

### Directive format

```
# @tui <directive> [flags...] [key="value"...]
```

| Element | Values | Purpose |
|---------|--------|---------|
| Directive | `secret`, `shell-secret`, `skip` | Controls TUI appearance and target SOPS file |
| Flags | `password`, `optional` | Mask input, allow empty |
| Key-values | `label`, `placeholder`, `description`, `doc_url` | Override auto-generated metadata |

## Alternatives Considered

### A. Convention-based scanning

Scan `defaults/main.yml` for variables matching naming conventions (suffix `_api_key`, `_token`, `_secret`) with empty defaults.

**Rejected:** Fragile naming heuristic, misses secrets with unconventional names (e.g., `git_user_email`), cannot distinguish optional from required.

### B. Sidecar metadata file

Each role provides a `secrets.yml` manifest alongside `defaults/main.yml`.

**Rejected:** Extra file per role, requires a schema, separates the metadata from the default value it describes.

### C. Hybrid (convention + opt-in metadata)

Use convention scanning as a baseline, override with sidecar metadata for labels and masking.

**Rejected:** Combines the fragility of convention scanning with the file overhead of sidecars.

## Consequences

**Positive:**
- Single source of truth per role — secret metadata lives next to the default value.
- Adding a secret to a new role requires editing one file (`defaults/main.yml`), not 2-3.
- 31 tests validate the parser, scanner, and integration.
- Currently covers 14 Ansible vars + 2 shell exports across 6 roles.

**Accepted downsides:**
- YAML comments are not parsed by Ansible — requires a custom Python parser.
- Annotation format could drift if not validated (mitigated by test suite).
- `scripts/first-run.py` still has a duplicate secret list that should be consolidated to import from the scanner (tracked as remaining work in SPIKE-002).

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Adopted | 2026-03-02 | 7d4d74c | Retroactive ADR from SPIKE-002; implementation already complete |
