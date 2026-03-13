---
id: bd_202602-workstation-2nn
status: closed
deps: []
links: []
created: 2026-03-06T05:41:54Z
type: epic
priority: 2
external-ref: STORY-005
---
# Code Repo Migration Tool

Create scripts/code-pull.sh that discovers git repos on a source machine via SSH, classifies clean vs dirty, and transfers them appropriately (git clone for clean, rsync for dirty). Add make code-pull SOURCE=<host> target.


