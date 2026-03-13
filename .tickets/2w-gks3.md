---
id: 2w-gks3
status: closed
deps: []
links: []
created: 2026-03-13T05:06:58Z
type: task
priority: 2
assignee: Cristos L-C
parent: 2w-wkka
tags: [spec:SPEC-006]
---
# Create steamos-bootstrap role (stow)

Task: install GNU Stow via nix profile install nixpkgs#stow. Idempotent.


## Notes

**2026-03-13T05:08:05Z**

Implemented stow.yml: check stow, nix profile install nixpkgs#stow, verify stow --version. main.yml wires all 3 tasks.
