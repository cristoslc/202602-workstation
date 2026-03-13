---
id: 2w-wkka
status: closed
deps: []
links: []
created: 2026-03-13T05:06:35Z
type: epic
priority: 2
assignee: cristos
external-ref: SPEC-006
---
# Implement SPEC-006: SteamOS Platform Bootstrap

Scaffold steamos/ directory, steamos-bootstrap role (sshd+nix+stow), and Makefile SteamOS detection.


## Notes

**2026-03-13T05:09:16Z**

SPEC-006 scaffold complete; ansible-lint partially passes (expected errors for SPEC-007/008 roles). Committing after SPEC-007/008 so lint is fully clean.

**2026-03-13T05:13:52Z**

SPEC-006 fully implemented: steamos/ scaffold, bootstrap role (sshd+nix+stow), Makefile detection, site.yml. Commit 91fcac1. yamllint clean.
