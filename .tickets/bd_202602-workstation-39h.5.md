---
id: bd_202602-workstation-39h.5
status: closed
deps: []
links: []
created: 2026-03-03T06:31:44Z
type: task
priority: 2
---
# Create Docker config.json shared stow package

Create shared/dotfiles/docker/ stow package with .docker/config.json (credential helpers, log rotation). No tokens in shared layer — secrets go in SOPS-encrypted secrets layer.


