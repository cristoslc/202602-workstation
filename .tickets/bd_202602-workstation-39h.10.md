---
id: bd_202602-workstation-39h.10
status: closed
deps: []
links: []
created: 2026-03-03T06:36:24Z
type: task
priority: 1
assignee: Cristos L-C
---
# Capture Docker config.json with SOPS encryption for auth tokens

~/.docker/config.json exists but contains NO auth tokens (auths is empty, credentials delegated to Docker Desktop keychain via credsStore: desktop). Just needs a simple shared stow package — no SOPS needed. Config: {credsStore: desktop, currentContext: desktop-linux}


