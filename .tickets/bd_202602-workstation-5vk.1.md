---
id: bd_202602-workstation-5vk.1
status: closed
deps: []
links: []
created: 2026-03-03T19:39:46Z
type: task
priority: 2
---
# Create hub-backup-keys.sh script

Script that SSHs to hub, downloads cert.pem+key.pem from /home/syncthing/.local/state/syncthing/, age-encrypts using pubkey from .sops.yaml, stores at shared/secrets/syncthing-hub-keys/. Follow data-pull.sh conventions.


