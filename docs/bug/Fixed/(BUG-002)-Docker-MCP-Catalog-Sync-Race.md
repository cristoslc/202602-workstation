---
title: "BUG-002: Docker MCP Server Enable Fails Due to Catalog Sync Race"
artifact: BUG-002
status: Fixed
author: cristos
created: 2026-03-13
last-updated: 2026-03-13
severity: medium
affected-artifacts: []
discovered-in: "Ansible log failure — shared/roles/docker/tasks/mcp-gateway.yml:90, 2026-03-13"
fix-ref: ""
---

# BUG-002: Docker MCP Server Enable Fails Due to Catalog Sync Race

## Description

The "Enable MCP servers" task in `shared/roles/docker/tasks/mcp-gateway.yml` fails with "server X not found in catalog" for all six configured MCP servers (brave, context7, dockerhub, duckduckgo, markdownify, playwright).

The readiness gate (`docker mcp server ls`) only checks that the MCP CLI is available — it does not verify the catalog index has synced. After the MCP Toolkit is first enabled and Docker Desktop restarts, the catalog needs time to populate. The task runs immediately after the CLI becomes available, before the catalog is ready.

## Reproduction Steps

1. Start with a fresh Docker Desktop install (or one where MCP Toolkit was not previously enabled)
2. Run the full Ansible playbook (`./bootstrap.sh` or equivalent)
3. The playbook enables MCP Toolkit in Docker Desktop settings, restarts Docker Desktop, then attempts to enable MCP servers
4. The `docker mcp server enable <name>` commands fail with "server X not found in catalog" for all servers

## Expected Behavior

MCP servers enable successfully, retrying if the catalog is not yet synced after Docker restart.

## Actual Behavior

All six `docker mcp server enable` commands fail immediately with rc=1 and "not found in catalog" errors. The task has no retry logic and the playbook aborts.

## Impact

The Docker MCP Gateway setup fails on first-run provisioning. Manual re-running of the playbook succeeds once the catalog has synced, but this breaks the "single-run bootstrap" goal. Medium severity because the failure is transient and self-resolving on retry.

## Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Reported | 2026-03-13 | _pending_ | Initial report |
| Fixed | 2026-03-13 | _pending_ | Added retries (6x, 10s) to Enable MCP servers task |
