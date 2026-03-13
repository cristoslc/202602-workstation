---
id: bd_202602-workstation-x18
status: closed
deps: []
links: []
created: 2026-03-11T17:16:05Z
type: epic
priority: 2
external-ref: STORY-013
---
# Implement STORY-013: Cross-Platform Shell Alias Sync

Deduplicate shell aliases across shared and platform-specific zsh config files. Move identical aliases (eza/ls variants) to shared/aliases.zsh, consolidate bat/cat with conditional detection, keep platform-only aliases in place. Verify stow simulation clean on both platforms.


