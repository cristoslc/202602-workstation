# Research: Secrets Placeholder Autodiscovery

**Status:** Planned
**Gate:** Pre-MVP (blocks reliable multi-machine bootstrap)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Planned | 2026-02-25 | — | Initial creation |

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

## Approaches to investigate

### A. Convention-based scanning

Scan all `shared/roles/*/defaults/main.yml` files. Any variable matching a naming convention (e.g., suffix `_api_key`, `_token`, `_secret`) with an empty default is a secret placeholder.

**Pros:** Zero extra metadata, works with existing file structure.
**Cons:** Fragile naming heuristic, misses secrets with unconventional names, can't distinguish "optional" from "required."

### B. YAML comment annotations

Annotate secret vars in `defaults/main.yml` with structured comments:

```yaml
# @secret label="Brave Search API key" doc_url="https://brave.com/search/api/"
docker_mcp_brave_api_key: ""
```

A scanner reads these annotations and generates the `SecretField` list at TUI startup.

**Pros:** Source of truth lives next to the default value, single file to edit per role.
**Cons:** YAML comments aren't parsed by Ansible (custom parser needed), fragile if format drifts.

### C. Sidecar metadata file

Each role that needs secrets provides a `secrets.yml` manifest alongside `defaults/main.yml`:

```yaml
# shared/roles/docker/secrets.yml
- key: docker_mcp_brave_api_key
  label: "Brave Search API key"
  doc_url: "https://brave.com/search/api/"
  password: true
  storage: ansible_var   # or shell_export
```

The TUI discovers these files at startup via glob and builds the prompt list dynamically.

**Pros:** Structured, no comment parsing, role is fully self-contained.
**Cons:** Extra file per role, needs a schema.

### D. Hybrid: convention + opt-in metadata

Use approach A as a baseline (flag any empty `_api_key`/`_token` var as a potential secret), then let roles override metadata via approach C for labels, doc URLs, and masking.

## Go/no-go criteria

- **Go:** At least one approach can be implemented in < 1 day, doesn't require changing existing role defaults format, and catches 100% of current secrets.
- **No-go:** All approaches require significant migration effort or introduce brittle parsing. In that case, keep the curated list but consolidate first-run.py to import from `lib/secrets.py`.

## Pivot if no-go

Consolidate `first-run.py` to import `SHARED_ANSIBLE_VARS` and `SHELL_SECRETS` from `scripts/setup_tui/lib/secrets.py` instead of maintaining its own copy. Add a `make check` validation that compares role defaults containing empty `_api_key`/`_token` vars against the declared `SecretField` list and fails if any are missing.

## Dependencies

- None (pure investigation).

## Blocks

- Reliable multi-machine bootstrap (secrets silently empty if not prompted).
- Scaling to more roles with API keys (each new key is manual bookkeeping today).

## PRD risks addressed

- Secret collection completeness during first-run and bootstrap.
- Maintainability as the role count grows.
