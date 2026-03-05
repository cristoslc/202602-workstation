# Hub Replacement Runbook

Operational procedures for hub server migration and emergency replacement. Covers both Syncthing (file sync) and Unison/wsync (code sync) in the hub-and-spoke topology.

**Origin:** [SPIKE-007](../research/Complete/(SPIKE-007)-Hub-Server-Failover-and-Migration/(SPIKE-007)-Hub-Server-Failover-and-Migration.md)

## Architecture Summary

**Topology:** Hub-and-spoke. One always-on Linux server acts as the central relay for both Syncthing (file sync) and Unison/wsync (code sync). Spokes are macOS and Linux workstations (2-3 devices).

### Key paths on the hub

| Component | Path | Purpose |
|-----------|------|---------|
| Syncthing keys | `/home/syncthing/.local/state/syncthing/cert.pem`, `key.pem` | Device identity (preserving these preserves the device ID) |
| Syncthing config | `/home/syncthing/.local/state/syncthing/config.xml` | Hub configuration, API key, device list |
| Syncthing data | `/srv/syncthing/{Documents,Pictures,Music,Videos,Downloads}` | Synced user data |
| Syncthing database | `/home/syncthing/.local/state/syncthing/index-v0.14.0.db/` | File metadata index (auto-rebuilds -- do NOT migrate) |
| Unison data | `/srv/code-sync/<repo>/<branch>/` | Per-repo, per-branch working trees |
| Unison binary | `/usr/local/bin/unison` | Must match version `2.53.5` across all nodes |
| Systemd service | `syncthing@syncthing.service` | Runs Syncthing as the `syncthing` system user |

### Secrets that reference the hub

| Variable | Location | Purpose |
|----------|----------|---------|
| `syncthing_hub_device_id` | `shared/secrets/vars.sops.yml` | Syncthing 56-char device ID derived from `cert.pem` |
| `syncthing_hub_address` | `shared/secrets/vars.sops.yml` | Tailscale IP or hostname of the hub |
| `unison_hub_host` | `shared/secrets/vars.sops.yml` | SSH destination for wsync |
| `WSYNC_HUB_HOST` | `~/.config/wsync/config` on each spoke | Runtime env var for wsync script |

### Ansible entry points

| Command | What it does |
|---------|-------------|
| `make apply ROLE=syncthing-hub` | Installs Syncthing on hub, creates data dirs, starts service, configures REST API |
| `make apply ROLE=syncthing` | Spoke-side: installs, configures hub pairing via REST API |
| `make apply ROLE=unison` | Spoke-side: installs binary, deploys wsync + profile, sets up timers |
| `make edit-secrets-shared` | Opens `sops shared/secrets/vars.sops.yml` to edit encrypted secrets |

---

## Runbook A: Planned Migration (Same Device ID)

**Scenario:** Moving the hub to a new server. Old hub is still running.

**Target:** Near-zero downtime. Spokes auto-reconnect (same device ID). No spoke reconfiguration needed unless IP changes.

**Total downtime:** 5-15 minutes.

### Prerequisites

- [ ] New server provisioned with Debian/Ubuntu, SSH access, and Tailscale
- [ ] SSH key-based access to both old hub (`OLD_HUB`) and new hub (`NEW_HUB`)
- [ ] New server has sufficient disk space (check `du -sh /srv/syncthing/ /srv/code-sync/` on old hub)
- [ ] Unison `2.53.5` available for installation

### Phase 1: Pre-stage data (no downtime)

Run while old hub is still serving. Can repeat over hours/days to minimize final delta.

```bash
# 1. Initial rsync of Syncthing data
rsync -avz --progress OLD_HUB:/srv/syncthing/ NEW_HUB:/srv/syncthing/

# 2. Initial rsync of Unison code-sync data
rsync -avz --progress OLD_HUB:/srv/code-sync/ NEW_HUB:/srv/code-sync/
```

**Verify:** `ssh NEW_HUB "du -sh /srv/syncthing/ /srv/code-sync/"` -- sizes should approximate old hub.

### Phase 2: Provision Syncthing and Unison on new hub

```bash
# 3. Run syncthing-hub role on the new hub
cd <workstation-repo>/linux
ansible-playbook site.yml --tags syncthing-hub -e "unison_is_hub=true"

# 4. Install Unison (matching pinned version)
ssh NEW_HUB "wget -q https://github.com/bcpierce00/unison/releases/download/v2.53.5/unison-2.53.5-ubuntu-x86_64.tar.gz && \
  tar xzf unison-2.53.5-ubuntu-x86_64.tar.gz && \
  sudo cp bin/unison /usr/local/bin/unison && \
  sudo chmod 0755 /usr/local/bin/unison && \
  unison -version"

# 5. Ensure code-sync directory exists
ssh NEW_HUB "sudo mkdir -p /srv/code-sync && sudo chown \$(whoami):\$(whoami) /srv/code-sync"
```

### Phase 3: Cutover (downtime starts)

```bash
# 6. Stop Syncthing on old hub
ssh OLD_HUB "sudo systemctl stop syncthing@syncthing"

# 7. Final delta rsync
rsync -avz --delete OLD_HUB:/srv/syncthing/ NEW_HUB:/srv/syncthing/
rsync -avz --delete OLD_HUB:/srv/code-sync/ NEW_HUB:/srv/code-sync/

# 8. Stop Syncthing on new hub (it generated new keys during provisioning)
ssh NEW_HUB "sudo systemctl stop syncthing@syncthing"

# 9. Copy identity keys from old hub to new hub
scp OLD_HUB:/home/syncthing/.local/state/syncthing/cert.pem /tmp/cert.pem
scp OLD_HUB:/home/syncthing/.local/state/syncthing/key.pem /tmp/key.pem
scp /tmp/cert.pem NEW_HUB:/tmp/cert.pem
scp /tmp/key.pem NEW_HUB:/tmp/key.pem
ssh NEW_HUB "sudo cp /tmp/{cert,key}.pem /home/syncthing/.local/state/syncthing/ && \
  sudo chown syncthing:syncthing /home/syncthing/.local/state/syncthing/{cert,key}.pem && \
  sudo chmod 0600 /home/syncthing/.local/state/syncthing/key.pem && \
  rm -f /tmp/{cert,key}.pem"
rm -f /tmp/{cert,key}.pem

# 10. Copy config.xml (contains API key, device list, folder config)
scp OLD_HUB:/home/syncthing/.local/state/syncthing/config.xml /tmp/config.xml
scp /tmp/config.xml NEW_HUB:/tmp/config.xml
ssh NEW_HUB "sudo cp /tmp/config.xml /home/syncthing/.local/state/syncthing/config.xml && \
  sudo chown syncthing:syncthing /home/syncthing/.local/state/syncthing/config.xml && \
  rm -f /tmp/config.xml"
rm -f /tmp/config.xml

# 11. Do NOT copy the database (index-v0.14.0.db/) -- let it rebuild

# 12. Start Syncthing on new hub
ssh NEW_HUB "sudo systemctl start syncthing@syncthing"
```

**Verify device ID matches:**

```bash
ssh NEW_HUB "sudo -u syncthing syncthing --device-id"
# Must match syncthing_hub_device_id in SOPS secrets
```

### Phase 4: Update hub address (only if IP changed)

If `NEW_HUB` has a different Tailscale IP:

```bash
# 13. Update SOPS secrets
make edit-secrets-shared
# Set: syncthing_hub_address: "NEW_HUB_IP"
# Set: unison_hub_host: "NEW_HUB_IP"

# 14. Re-run spoke roles on each workstation
make apply ROLE=syncthing
make apply ROLE=unison
```

If the IP did NOT change, skip this phase entirely.

### Phase 5: Verify

```bash
# 15. Check Syncthing service
ssh NEW_HUB "sudo systemctl status syncthing@syncthing"

# 16. Verify spokes reconnected (on each spoke)
# macOS: open http://127.0.0.1:8384 -- hub should show "Connected"
# Linux: journalctl --user -u syncthing@$(whoami) --since "5 min ago" | grep -i connected

# 17. Verify Unison/wsync (on each spoke)
wsync

# 18. End-to-end test
echo "hub-migration-test $(date)" > ~/Documents/hub-test.txt
# Wait ~60 seconds, check other spoke:
cat ~/Documents/hub-test.txt
rm ~/Documents/hub-test.txt
```

### Rollback

1. `ssh NEW_HUB "sudo systemctl stop syncthing@syncthing"`
2. `ssh OLD_HUB "sudo systemctl start syncthing@syncthing"`
3. If IP was updated: revert SOPS secrets and re-run `make apply ROLE=syncthing` on spokes
4. Spokes reconnect to old hub automatically (same device ID)

---

## Runbook B: Emergency Replacement (Keys Available)

**Scenario:** Hub is gone (hardware failure, VM deleted) but `cert.pem` and `key.pem` are recoverable from backup.

**Target:** Preserve device ID. Spokes auto-reconnect after hub is provisioned.

**Total time:** 35-60 minutes (hub online). Data re-syncs in background.

### Prerequisites

- [ ] New server provisioned with Debian/Ubuntu, SSH access, Tailscale
- [ ] Syncthing keys recoverable from backup (restic, manual copy, or age-encrypted in repo)
- [ ] Ansible control machine with workstation repo and `age` key

### Procedure

```bash
# 1. Provision new hub
cd <workstation-repo>/linux
ansible-playbook site.yml --tags syncthing-hub -e "unison_is_hub=true"

# 2. Install Unison
ssh NEW_HUB "wget -q https://github.com/bcpierce00/unison/releases/download/v2.53.5/unison-2.53.5-ubuntu-x86_64.tar.gz && \
  tar xzf unison-2.53.5-ubuntu-x86_64.tar.gz && \
  sudo cp bin/unison /usr/local/bin/unison && sudo chmod 0755 /usr/local/bin/unison"

# 3. Create code-sync directory
ssh NEW_HUB "sudo mkdir -p /srv/code-sync && sudo chown \$(whoami):\$(whoami) /srv/code-sync"

# 4. Stop Syncthing (it generated new keys)
ssh NEW_HUB "sudo systemctl stop syncthing@syncthing"

# 5. Recover keys from backup
#    Option A: From restic (if hub was backed up)
restic -r b2:<bucket>:/ restore latest \
  --target /tmp/hub-restore \
  --include /home/syncthing/.local/state/syncthing/cert.pem \
  --include /home/syncthing/.local/state/syncthing/key.pem
#    Option B: From age-encrypted repo copy
age -d -i ~/.config/sops/age/keys.txt shared/secrets/syncthing-hub-keys/cert.pem.age > /tmp/cert.pem
age -d -i ~/.config/sops/age/keys.txt shared/secrets/syncthing-hub-keys/key.pem.age > /tmp/key.pem

# 6. Install recovered keys on new hub
scp /tmp/cert.pem /tmp/key.pem NEW_HUB:/tmp/
ssh NEW_HUB "sudo cp /tmp/{cert,key}.pem /home/syncthing/.local/state/syncthing/ && \
  sudo chown syncthing:syncthing /home/syncthing/.local/state/syncthing/{cert,key}.pem && \
  sudo chmod 0600 /home/syncthing/.local/state/syncthing/key.pem && \
  rm -f /tmp/{cert,key}.pem"

# 7. Start Syncthing
ssh NEW_HUB "sudo systemctl start syncthing@syncthing"

# 8. Verify device ID
ssh NEW_HUB "sudo -u syncthing syncthing --device-id"

# 9. Re-run hub configure (sets autoAcceptFolders)
ansible-playbook site.yml --tags syncthing-hub-configure

# 10. Trigger spoke reconnection
# macOS: osascript -e 'tell application "Syncthing" to quit'; sleep 2; open -a Syncthing
# Linux: systemctl --user restart syncthing@$(whoami)
```

If IP changed: update SOPS secrets and re-run spoke roles (same as Runbook A Phase 4).

Data re-syncs automatically: spokes push their data to the empty hub in the background.

Verify: same as Runbook A Phase 5.

---

## Runbook C: Emergency Replacement (Keys Lost)

**Scenario:** Hub is gone AND keys are not recoverable. New device ID required. All spokes must be reconfigured.

**Total time:** 45-70 minutes. Data re-syncs in background.

### Prerequisites

- [ ] New server provisioned with Debian/Ubuntu, SSH access, Tailscale
- [ ] Ansible control machine with workstation repo and `age` key
- [ ] SSH access to all spoke machines (for re-running Ansible)

### Procedure

```bash
# 1. Provision new hub (generates new device ID)
cd <workstation-repo>/linux
ansible-playbook site.yml --tags syncthing-hub -e "unison_is_hub=true"

# 2. Record the new device ID from Ansible output, or:
ssh NEW_HUB "sudo -u syncthing syncthing --device-id"

# 3. Install Unison + create code-sync directory
ssh NEW_HUB "wget -q https://github.com/bcpierce00/unison/releases/download/v2.53.5/unison-2.53.5-ubuntu-x86_64.tar.gz && \
  tar xzf unison-2.53.5-ubuntu-x86_64.tar.gz && \
  sudo cp bin/unison /usr/local/bin/unison && sudo chmod 0755 /usr/local/bin/unison"
ssh NEW_HUB "sudo mkdir -p /srv/code-sync && sudo chown \$(whoami):\$(whoami) /srv/code-sync"
```

### Update all secrets

```bash
# 4. Edit SOPS secrets
make edit-secrets-shared
```

Update these values:

| Secret | New Value |
|--------|-----------|
| `syncthing_hub_device_id` | New 56-char device ID from step 2 |
| `syncthing_hub_address` | New hub Tailscale IP (if changed) |
| `unison_hub_host` | New hub Tailscale IP (if changed) |

```bash
# 5. Commit the secrets update
git add shared/secrets/vars.sops.yml
git commit -m "chore: update hub identity after emergency replacement"
```

### Reconfigure all spokes

```bash
# 6. On each spoke, pull and re-run roles
cd <workstation-repo>
git pull
make apply ROLE=syncthing   # Reconfigures hub device ID via REST API
make apply ROLE=unison       # Updates wsync config if hub host changed
```

The hub's `autoAcceptFolders: true` setting auto-accepts folder shares from spokes when they connect.

```bash
# 7. Restart Syncthing on each spoke to force reconnection
# macOS: osascript -e 'tell application "Syncthing" to quit'; sleep 2; open -a Syncthing
# Linux: systemctl --user restart syncthing@$(whoami)

# 8. Trigger initial Unison sync on each spoke
wsync
```

### Verify

Same as Runbook A Phase 5. Additionally, SSH-tunnel to the hub web UI to verify all spokes connected:

```bash
ssh -L 8384:127.0.0.1:8384 NEW_HUB
# Open http://127.0.0.1:8384 -- all spoke devices should show "Connected"
```

---

## Key Backup Recommendations

The single most impactful operational improvement is **backing up hub Syncthing keys**. Without keys, Runbook C (full spoke reconfiguration) is required instead of Runbook B (transparent recovery).

**Recommended approach:** Age-encrypt `cert.pem` and `key.pem` and store them in the repo:

```bash
# Export and encrypt
scp HUB:/home/syncthing/.local/state/syncthing/{cert,key}.pem /tmp/
age -r "$(grep -oP 'age1\S+' .sops.yaml)" /tmp/cert.pem > shared/secrets/syncthing-hub-keys/cert.pem.age
age -r "$(grep -oP 'age1\S+' .sops.yaml)" /tmp/key.pem > shared/secrets/syncthing-hub-keys/key.pem.age
rm -f /tmp/{cert,key}.pem
git add shared/secrets/syncthing-hub-keys/
git commit -m "chore: backup hub syncthing identity keys (age-encrypted)"
```

This follows the encryption-at-rest pattern from [ADR-002](../adr/Adopted/(ADR-002)-Encryption-at-Rest-for-Personal-Files.md).
