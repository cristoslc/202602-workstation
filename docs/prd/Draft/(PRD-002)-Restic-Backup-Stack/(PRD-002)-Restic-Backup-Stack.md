# PRD-002: Restic Backup Stack

**Status:** Draft
**Author:** cristos
**Created:** 2026-02-26
**Last Updated:** 2026-02-26
**Research:** [Backup Solution Evaluation](../../../research/Active/backup-solution-evaluation/README.md)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Draft | 2026-02-26 | 20e5b38 | Initial creation |

---

## Problem

The workstation provisioning stack has incomplete backup coverage:

- **macOS:** Backblaze Personal provides unlimited cloud backup with 1-year
  history, but is proprietary, not self-hostable, macOS-only, and opaque.
- **Linux:** Timeshift provides system snapshots (rsync-based) with max ~67 days
  retention (5 daily + 3 weekly + 2 monthly). No file-level versioning.
- **Neither platform** has a self-hosted, cross-platform, file-level versioned
  backup with 365-day retention and per-workstation isolation.

On a fresh bootstrap, backup configuration is entirely manual (Backblaze
sign-in, Timeshift left at defaults). There is no Ansible-managed,
zero-touch backup pipeline.

## Goal

After `make apply ROLE=backups`, both macOS and Linux workstations are
automatically configured to:

1. Back up `$HOME` (with exclude patterns) to a self-hosted restic REST server.
2. Run Backrest as a background service for scheduling, monitoring, browsing,
   and restoring.
3. Retain 365+ days of deduplicated, encrypted file history.
4. Isolate each workstation's snapshots by hostname.

A nightly `rclone sync` on the Proxmox host mirrors the restic repo to
Backblaze B2 for offsite redundancy. Workstations never interact with B2
directly.

## Scope

### In scope

1. **Restic binary installation** — cross-platform (macOS + Linux), pinned
   version, installed to `/usr/local/bin/` or Homebrew.
2. **Backrest installation and configuration** — cross-platform, background
   service (systemd user service on Linux, launchd user agent on macOS),
   Ansible-templated `config.json`.
3. **Exclude patterns template** — `restic-excludes.txt.j2` covering OS noise,
   build artifacts, IDE state, large binaries, and macOS `~/Library` surgical
   carve-outs (keep config, skip caches).
4. **Role defaults** — `shared/roles/backups/defaults/main.yml` with repo URL,
   password reference, retention counts, Backrest port, exclude list.
5. **SOPS-encrypted repo password** — added to `shared/secrets/vars.sops.yml`.
6. **Proxmox REST server provisioning** — LXC or VM running
   `restic/rest-server` in Docker with `--append-only`, `--private-repos`,
   `.htpasswd` auth, TLS.
7. **rclone B2 offsite sync** — cron job on Proxmox host, nightly mirror of
   the restic repo to a B2 bucket.
8. **Playbook tag updates** — add `restic` and `backrest` tags to both platform
   playbooks alongside existing `backblaze`/`timeshift` tags.
9. **Post-install doc updates** — update `docs/post-install.md` with restic
   verification steps and Backrest web UI access.
10. **`make` targets** — `backup-status` (show last snapshot), `backup-browse`
    (open Backrest web UI).

### Out of scope

- Replacing Backblaze Personal on macOS (stays as a belt-and-suspenders layer).
- Replacing Timeshift on Linux (stays for system-level rollback).
- Proxmox host provisioning automation (manual LXC/VM setup — Proxmox is
  managed infrastructure, not a workstation).
- B2 bucket creation and IAM (one-time manual setup in B2 console).
- Native tray icon (Backrest is web UI; tray indicators are a future
  nice-to-have via SwiftBar/xbar on macOS, polybar/waybar on Linux).
- Notification integrations (Gotify, Slack hooks — can be added to Backrest
  config later without role changes).

---

## Architecture

```
┌──────────────────────┐         ┌──────────────────────────────┐
│  macOS workstation    │────────▶│  Proxmox LXC/VM              │
│  restic + Backrest    │  REST   │  restic REST server (Docker)  │
└──────────────────────┘         │  /data/backups/               │
                                  │                                │
┌──────────────────────┐         │  cron: rclone sync ──────────▶ B2
│  Linux workstation    │────────▶│       (nightly offsite copy)   │
│  restic + Backrest    │  REST   └──────────────────────────────┘
└──────────────────────┘
```

### Backup layers (post-implementation)

| Layer | Tool | Scope | Retention | Purpose |
|-------|------|-------|-----------|---------|
| System snapshots | Timeshift (Linux) | `/` filesystem | ~67 days | Quick rollback after bad update |
| Full-disk cloud | Backblaze (macOS) | Entire disk | 1 year (vendor) | "Lost my Mac entirely" recovery |
| **File versioning** | **Restic + Backrest** | **`$HOME` (both)** | **365+ days** | **"I need the file from 8 months ago"** |
| Offsite mirror | rclone → B2 | Restic repo | Mirrors local | Disaster recovery if Proxmox is lost |

### Data flow

1. **Backrest** triggers `restic backup` on schedule (cron expression in
   config, e.g. `0 */4 * * *` for every 4 hours).
2. **Restic** reads `$HOME`, applies exclude patterns, deduplicates, encrypts,
   and pushes to the REST server at `rest:https://backup.local:8000/<user>/`.
3. **Backrest** runs `restic forget` with retention policy after each backup,
   then periodic `restic prune` and `restic check`.
4. **rclone sync** (cron on Proxmox, nightly) mirrors
   `/data/backups/` → `b2:<bucket>/`.

---

## Deliverables

### D1: Restic binary installation (`restic.yml`)

New task file: `shared/roles/backups/tasks/restic.yml`

- macOS: `brew install restic` (Homebrew manages updates).
- Linux: Use the established binary installation pattern:
  1. `version-check.yml` — query GitHub API for latest, warn if pinned
     version is behind.
  2. Shell check — `restic version | grep -qF '{{ restic_version }}'`.
  3. `download-and-verify.yml` — download pinned release with SHA-256
     checksum from `defaults/main.yml`.
  4. `ansible.builtin.copy` — install to `/usr/local/bin/restic`,
     mode `0755`.
  5. Clean up temp file.
- Both: Verify with `restic version` handler.

### D2: Backrest installation (`backrest.yml`)

New task file: `shared/roles/backups/tasks/backrest.yml`

- macOS: `brew tap garethgeorge/homebrew-backrest-tap` then
  `brew install backrest`. Enable via `brew services start backrest`
  (launchd agent).
- Linux: Same binary installation pattern as D1:
  1. `version-check.yml` — query GitHub API for latest Backrest release.
  2. Shell check — `backrest version | grep -qF '{{ backrest_version }}'`.
  3. `download-and-verify.yml` — download with SHA-256 checksum.
  4. Install to `/usr/local/bin/backrest`, mode `0755`.
  5. Template and enable systemd user service (D5).
- Both: Template `~/.config/backrest/config.json` from
  `backrest-config.json.j2` (D3).

### D3: Backrest config template (`backrest-config.json.j2`)

New template: `shared/roles/backups/templates/backrest-config.json.j2`

Must configure:
- **Repo:** REST server URL (from `restic_repo_url` default), password (from
  SOPS var `restic_repo_password`).
- **Plan:** Backup `$HOME`, exclude file path, schedule (cron), hostname tag.
- **Retention:** `keep-daily: 365`, `keep-weekly: 52`, `keep-monthly: 24`,
  `keep-yearly: 5`.
- **Maintenance:** Prune schedule, check schedule.
- **Backrest port:** `{{ backrest_port }}` (default `127.0.0.1:9898`).

### D4: Exclude patterns template (`restic-excludes.txt.j2`)

New template: `shared/roles/backups/templates/restic-excludes.txt.j2`

Categories (from research doc):
- OS noise (`.DS_Store`, `.Trash`, `.Spotlight-V100`, etc.)
- Runtime/build artifacts (`node_modules`, `__pycache__`, `.venv`, `.cargo/registry`, etc.)
- Editor/IDE state (`.idea`, `.vscode/workspaceStorage`, `*.swp`)
- Large binaries (`*.iso`, `*.dmg`, `*.vmdk`, `*.qcow2`)
- macOS `~/Library` carve-outs (keep `Preferences/`, `Application Support/*/config`,
  `Keychains/`, `Fonts/`; exclude `Caches/`, `Logs/`, `*/Cache`, `*/GPUCache`,
  `*/Service Worker`, `*/Code Cache`, `Developer/`, `Saved Application State/`)
- Linux-specific (`baloo`, `akonadi`, `snap/*/common/cache`, `flatpak`)
- Optional user-extensible block via `{{ restic_extra_excludes | default([]) }}`

### D5: Systemd user service (`backrest.service.j2`)

New template: `shared/roles/backups/templates/backrest.service.j2`

Linux only. Runs Backrest as a systemd `--user` service so it starts on login.
Sets `BACKREST_PORT`, `BACKREST_CONFIG`, `BACKREST_RESTIC_COMMAND` environment
variables.

### D6: Role defaults (`defaults/main.yml`)

New file: `shared/roles/backups/defaults/main.yml`

```yaml
---
# Restic — pinned version + checksum (Linux only; macOS uses Homebrew)
restic_version: "0.17.3"
restic_sha256: "<sha256-of-linux-amd64-binary>"
restic_url: "https://github.com/restic/restic/releases/download/v{{ restic_version }}/restic_{{ restic_version }}_linux_amd64.bz2"
restic_repo: "restic/restic"  # for version-check.yml

# Backrest — pinned version + checksum (Linux only; macOS uses Homebrew tap)
backrest_version: "1.7.1"
backrest_sha256: "<sha256-of-linux-amd64-binary>"
backrest_url: "https://github.com/garethgeorge/backrest/releases/download/v{{ backrest_version }}/backrest_Linux_x86_64.tar.gz"
backrest_repo: "garethgeorge/backrest"  # for version-check.yml

# Repository
restic_repo_url: ""        # set per-environment (e.g. rest:https://user:pass@backup.local:8000/)
restic_repo_password: ""   # override from shared/secrets/vars.sops.yml

# Backrest
backrest_port: "127.0.0.1:9898"

# Retention
restic_keep_daily: 365
restic_keep_weekly: 52
restic_keep_monthly: 24
restic_keep_yearly: 5

# Schedule (cron syntax — Backrest format)
restic_backup_schedule: "0 */4 * * *"  # every 4 hours
restic_prune_schedule: "0 3 * * 0"     # weekly Sunday 3am

# Excludes
restic_extra_excludes: []  # user-extensible list appended to template
```

### D7: SOPS secret (`shared/secrets/vars.sops.yml`)

Add `restic_repo_password` to the shared encrypted vars. This is the
repository encryption password — not the REST server auth password (that
lives in `.htpasswd` on the server).

Also add `restic_rest_auth` (username:password for `.htpasswd` REST server
auth) so the repo URL can be constructed as
`rest:https://{{ restic_rest_auth }}@backup.local:8000/`.

### D8: `main.yml` orchestrator update

Update `shared/roles/backups/tasks/main.yml` to include the new task files:

```yaml
---
# Backups role: Backblaze (macOS) + Timeshift (Linux) + Restic/Backrest (both)

- name: Install Backblaze
  ansible.builtin.include_tasks: backblaze.yml
  tags: [backblaze]

- name: Install Timeshift
  ansible.builtin.include_tasks: timeshift.yml
  tags: [timeshift]

- name: Install and configure Restic
  ansible.builtin.include_tasks: restic.yml
  tags: [restic]

- name: Install and configure Backrest
  ansible.builtin.include_tasks: backrest.yml
  tags: [backrest]
```

### D9: Playbook tag updates

**`linux/plays/03-desktop.yml`:**
```yaml
- role: backups
  tags: [backups, timeshift, restic, backrest, desktop]
```

**`macos/plays/03-desktop.yml`:**
```yaml
- role: backups
  tags: [backups, backblaze, restic, backrest, desktop]
```

### D10: Proxmox REST server setup (manual, documented)

Not Ansible-managed (Proxmox is infrastructure, not a workstation). Document
the setup procedure:

1. Create LXC container (Debian, 1 CPU, 512 MB RAM, storage mount at
   `/data/backups`).
2. Install Docker.
3. Run `restic/rest-server` with `--append-only`, `--private-repos`,
   `--tls`, `.htpasswd` auth.
4. Create `.htpasswd` entry for each workstation user.
5. Init the restic repo: `restic -r rest:https://user:pass@backup.local:8000/ init`
6. Set up rclone B2 remote and nightly sync cron.

Delivered as: `docs/research/Active/backup-solution-evaluation/proxmox-rest-server-setup.md`

### D11: Post-install doc updates

Update `docs/post-install.md`:

**Both platforms:**
- [ ] Restic: verify backup works (`restic -r ... snapshots`)
- [ ] Backrest: open `http://localhost:9898` and confirm dashboard shows repo
- [ ] Verify first backup completes without error

**Linux:**
- Replace "Backblaze is macOS-only; verify Timeshift snapshots are running"
  with "Verify Timeshift snapshots (`sudo timeshift --list`) and Restic
  backups (`restic snapshots`)"

**macOS:**
- Keep Backblaze sign-in step.
- Add: "Verify Restic backup is running alongside Backblaze"

### D12: Makefile targets

```makefile
backup-status: ## Show latest restic snapshot for this host
	restic -r "$(RESTIC_REPOSITORY)" snapshots --host "$$(hostname)" --latest 3

backup-browse: ## Open Backrest web UI
	$(if $(filter darwin,$(PLATFORM)),open,xdg-open) http://localhost:9898
```

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Proxmox host is offline | Backups fail silently | Backrest shows error in UI; add notification hook (Gotify/desktop) as follow-up |
| REST server storage fills up | Backup writes fail | Monitor via Prometheus `/metrics`; alert on disk usage; B2 copy is independent |
| Restic repo password lost | All backups unrecoverable | SOPS-encrypted in repo + 1Password entry; document in disaster recovery runbook |
| `.htpasswd` credential rotation | Workstations can't authenticate | Ansible manages the credential; rotate via `sops` edit + `make apply ROLE=backups` |
| Backrest version drift | Config format changes break template | Pin version in defaults; test upgrades manually before bumping |
| macOS `~/Library` excludes miss new cache paths | Backup grows over time | Periodic review of backup size; add new excludes to template |
| `rclone sync` deletes B2 data after local prune | Lose offsite history | Use B2 lifecycle rules: keep deleted objects for 30 days as safety net |
| Backrest scheduling conflicts with manual `restic` runs | Lock contention, failed operations | Document that Backrest owns scheduling; CLI use should be read-only (snapshots, find, mount, restore) unless Backrest is stopped |

---

## Implementation order

The deliverables have dependencies. Suggested sequencing:

```
Phase 1: Server infrastructure (manual)
  D10: Proxmox REST server setup
  D7:  SOPS secrets (repo password, REST auth)

Phase 2: Core role implementation
  D6:  Role defaults
  D4:  Exclude patterns template
  D1:  Restic binary installation
  D8:  main.yml orchestrator update

Phase 3: Backrest layer
  D3:  Backrest config template
  D5:  Systemd user service template
  D2:  Backrest installation + service enable

Phase 4: Integration
  D9:  Playbook tag updates
  D11: Post-install doc updates
  D12: Makefile targets

Phase 5: Verification
  First backup + restore test on both platforms
  Verify retention policy (simulate forget --dry-run)
  Verify B2 offsite mirror
```

Phase 1 must be done first (need a server to test against). Phases 2–3 can be
developed locally with `--check`/`--diff` mode. Phase 4 is low-risk wiring.

---

## Browsing and restore UX

### Day-to-day: Backrest web UI (`localhost:9898`)

1. Open browser → snapshot timeline with dates and sizes.
2. Click snapshot → browse file tree visually.
3. Select file(s) → **Download** (browser stream) or **Restore** (disk write).
4. Dashboard shows: backup history, errors, next scheduled run.

### Power user: restic CLI

```bash
restic snapshots --host "$(hostname)"        # list snapshots
restic find "quarterly-report.xlsx"           # search across snapshots
restic mount /tmp/restic-mount               # FUSE browse
restic restore latest --target /tmp/restore \
  --include "/home/user/Documents/file.pdf"  # restore specific file
restic dump latest "/home/user/.zshrc"       # dump to stdout
restic diff abc123 def456                    # diff two snapshots
```

### Disaster recovery: full workstation loss

1. Install restic on fresh OS.
2. `export RESTIC_REPOSITORY="rest:https://..."` (or B2 if Proxmox is down).
3. `restic snapshots --host old-hostname` → find last snapshot.
4. `restic restore latest --target /tmp/staging --host old-hostname`
5. Cherry-pick from staging into new `$HOME`.

The B2 mirror is a byte-for-byte copy — any restic command works against it
as a fallback if the Proxmox host is unavailable.

---

## Success criteria

1. `make apply ROLE=backups` on a clean machine installs restic + Backrest,
   templates all config, and starts the Backrest service — no manual steps.
2. First automated backup completes within 15 minutes of role application.
3. `restic snapshots --host $(hostname)` shows at least one snapshot.
4. Backrest web UI at `localhost:9898` displays the repo, plan, and snapshot
   history.
5. `restic restore latest --target /tmp/test --include <file>` recovers the
   correct file content.
6. Restic repo password is SOPS-encrypted in `shared/secrets/vars.sops.yml`
   and not present in plaintext anywhere in the repo.
7. `rclone sync` on Proxmox successfully mirrors the repo to B2; `restic -r
   b2:... snapshots` returns the same snapshot list.
8. Exclude patterns prevent `~/Library/Caches`, `node_modules`, `.cache`, etc.
   from appearing in backups (verify with `restic ls latest | grep -c Caches`).
9. After 2+ test runs, `restic forget --keep-daily 365 --dry-run` correctly
   identifies which snapshots would be retained.
10. `make backup-status` and `make backup-browse` work on both platforms.
