---
id: bd_202602-workstation-x18.1
status: closed
deps: []
links: []
created: 2026-03-11T17:16:10Z
type: task
priority: 2
assignee: Cristos L-C
---
# Move eza aliases to shared aliases.zsh

Move ls/ll/la eza aliases from both macos.zsh and linux.zsh into shared/dotfiles/zsh/.config/zsh/aliases.zsh. These are identical on both platforms. Guard with 'command -v eza' conditional.


