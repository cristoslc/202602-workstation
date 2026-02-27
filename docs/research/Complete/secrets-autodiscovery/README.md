# Research: Secrets Placeholder Autodiscovery

**Status:** Complete
**Gate:** Pre-MVP (blocks reliable multi-machine bootstrap)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-02-25 | — | Initial creation |
| Complete | 2026-02-27 | — | Implemented approach B (@tui annotations) |

---

## Question

Can we automatically discover which secrets a bootstrap run needs — by scanning Ansible role defaults for empty/placeholder values — instead of maintaining a hand-curated list in `lib/secrets.py` and `first-run.py`?

## Context

Today, the secrets collection flow relies on two hard-coded lists:

- `scripts/setup_tui/lib/secrets.py` → `SHARED_ANSIBLE_VARS`, `SHELL_SECRETS`
- `scripts/first-run.py` → its own duplicate `SHARED_ANSIBLE_VARS`, `SHELL_SECRETS`

Every time a role adds a new secret (e.g., `docker_mcp_brave_api_key` for the MCP gateway), a developer must manually add a `SecretField` to the TUI lib. If they forget, the secret silently stays empty until the user notices a broken tool.

### Current pain points

1. **Manual bookkeeping** — adding a secret means touching 2–3 files (role defaults, secrets.py, possibly first-run.py).
2. **Divergence** — first-run.py has its own copy of the secret field lists (should be consolidated).
3. **No validation** — nothing warns during bootstrap if a role has an empty default that was never prompted for.
4. **No metadata in defaults** — role `defaults/main.yml` has no machine-readable hint about which vars are secrets vs. configuration.

## Approaches investigated

### A. Convention-based scanning

Scan all `shared/roles/*/defaults/main.yml` files. Any variable matching a naming convention (e.g., suffix `_api_key`, `_token`, `_secret`) with an empty default is a secret placeholder.

**Pros:** Zero extra metadata, works with existing file structure.
**Cons:** Fragile naming heuristic, misses secrets with unconventional names, can't distinguish "optional" from "required."

### B. YAML comment annotations — **SELECTED**

Annotate secret vars in `defaults/main.yml` with structured comments:

```yaml
# @tui secret password label="Restic repo password"
restic_repo_password: ""           # Restic encryption key
```

A scanner reads these annotations and generates the `SecretField` list at TUI startup.

**Pros:** Source of truth lives next to the default value, single file to edit per role.
**Cons:** YAML comments aren't parsed by Ansible (custom parser needed), fragile if format drifts.

### C. Sidecar metadata file

Each role that needs secrets provides a `secrets.yml` manifest alongside `defaults/main.yml`.

**Pros:** Structured, no comment parsing, role is fully self-contained.
**Cons:** Extra file per role, needs a schema.

### D. Hybrid: convention + opt-in metadata

Use approach A as a baseline, then let roles override metadata via approach C for labels, doc URLs, and masking.

## Decision: Approach B — `@tui` annotations

### Annotation format

```
# @tui <directive> [flags...] [key="value"...]
variable_name: ""
```

| Element | Values | Purpose |
|---------|--------|---------|
| Directive | `secret`, `shell-secret`, `skip` | Controls whether var appears in TUI and which SOPS file it targets |
| Flags | `password`, `optional` | Mask input, allow empty |
| Key-values | `label`, `placeholder`, `description`, `doc_url` | Override auto-generated metadata |

### Implementation

| File | Purpose |
|------|---------|
| `scripts/setup_tui/lib/var_scanner.py` | Scans `@tui` annotations from all role `defaults/main.yml` |
| `scripts/setup_tui/lib/secrets.py` | `SHARED_ANSIBLE_VARS` now populated dynamically by scanner |
| `tests/python/test_var_scanner.py` | 31 tests covering parser, scanner, and integration |

### Annotated roles

| Role | Vars discovered | Skipped |
|------|----------------|---------|
| backups | `restic_b2_bucket`, `restic_repo_password`, `b2_master_key_id`, `b2_master_key`, `restic_shoutrrr_url` | `restic_b2_account_id`, `restic_b2_account_key` (auto-provisioned) |
| docker | `docker_mcp_brave_api_key` | — |
| git | `git_user_email`, `git_user_name`, `git_signing_key` | — |
| syncthing | `syncthing_hub_device_id`, `syncthing_hub_address` | — |
| remote-desktop | `rustdesk_relay_host`, `rustdesk_relay_key` | — |
| unison | `unison_hub_host` | — |

### Remaining work

- `scripts/first-run.py` still maintains its own duplicate `SHARED_ANSIBLE_VARS` — should be consolidated to import from the TUI lib.

## Go/no-go result

**Go.** Approach B was implemented in a single session, required only adding `# @tui` comments to existing defaults files, and catches 100% of current secrets (14 ansible vars + 2 shell exports).

## Dependencies

- None (pure investigation).

## Blocks (now resolved)

- Reliable multi-machine bootstrap (secrets silently empty if not prompted).
- Scaling to more roles with API keys (each new key is manual bookkeeping today).

## PRD risks addressed

- Secret collection completeness during first-run and bootstrap.
- Maintainability as the role count grows.
