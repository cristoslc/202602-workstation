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

1. Back up `$HOME` (with exclude patterns) directly to Backblaze B2.
2. Run Backrest as a background service for scheduling, monitoring, browsing,
   and restoring — with notifications on backup success/failure.
3. Retain 365+ days of deduplicated, encrypted file history.
4. Isolate each workstation's snapshots by hostname.
5. Allow the user to pause and resume backups from the Backrest web UI.

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
5. **SOPS-encrypted secrets** — repo password and B2 credentials in
   `shared/secrets/vars.sops.yml`.
6. **Backup notifications** — Backrest Shoutrrr hook for email/Gotify
   notifications on backup success, failure, and errors. Healthchecks.io
   integration for heartbeat monitoring (detect missing backups).
7. **Pause/resume** — Backrest plan management (disable/enable plans from
   web UI). Documented in post-install.
8. **Playbook tag updates** — add `restic` and `backrest` tags to both platform
   playbooks alongside existing `backblaze`/`timeshift` tags.
9. **Post-install doc updates** — update `docs/post-install.md` with restic
   verification steps and Backrest web UI access.
10. **`make` targets** — `backup-status` (show last snapshot), `backup-browse`
    (open Backrest web UI).

### Out of scope

- Replacing Backblaze Personal on macOS (stays as a belt-and-suspenders layer).
- Replacing Timeshift on Linux (stays for system-level rollback).
- B2 bucket creation and IAM (one-time manual setup in B2 console).
- Native tray icon (Backrest is web UI; tray indicators are a future
  nice-to-have via SwiftBar/xbar on macOS, polybar/waybar on Linux).
- Weekly digest emails with data-uploaded stats (Backrest doesn't support
  aggregated weekly summaries natively; Healthchecks.io provides a monitoring
  dashboard as a partial substitute; custom reporting is a v2 candidate).

---

## Architecture

### v1: B2-direct (this PRD)

```
┌──────────────────────┐
│  macOS workstation    │──── restic backup ────▶ B2 bucket
│  restic + Backrest    │     (direct, encrypted)
└──────────────────────┘

┌──────────────────────┐
│  Linux workstation    │──── restic backup ────▶ same B2 bucket
│  restic + Backrest    │     (--host isolates snapshots)
└──────────────────────┘

         ┌──────────────────┐
         │  Healthchecks.io  │◀── heartbeat ping on each backup
         └──────────────────┘
```

Each workstation talks directly to B2. No intermediate server. Restic encrypts
all data client-side (AES-256 + Poly1305) before upload — B2 only ever sees
ciphertext. The `--host` flag isolates each workstation's snapshots in the
shared bucket.

### v2: Proxmox REST server (future enhancement)

Add a local `restic/rest-server` on Proxmox as a LAN-speed primary target.
Benefits: faster backups, `--append-only` ransomware protection, local
restores without internet. B2 becomes the offsite mirror via `rclone sync`.
This is a pure acceleration/hardening upgrade — no workstation config changes
beyond swapping the repo URL.

### Encryption model

| Layer | What | Who encrypts | Key custody |
|-------|------|-------------|-------------|
| **Restic (primary)** | All backup data + metadata | Client-side on workstation | User-owned. SOPS-encrypted in repo + 1Password. |
| **B2 SSE-B2 (optional)** | Data at rest on B2 servers | Server-side by Backblaze | Backblaze-managed. Defense-in-depth only. |

Restic's client-side encryption is the trust boundary. Data is encrypted and
authenticated before it leaves the workstation. B2 never sees plaintext. B2's
optional SSE-B2 (Backblaze-managed keys) can be enabled on the bucket as an
additional at-rest layer — this is defense-in-depth, not the primary
protection.

B2 SSE-C (customer-managed keys) is also supported but adds key-management
burden without meaningful benefit over restic's encryption. SSE-B2 is the
simpler choice for the server-side layer.

### Backup layers (post-implementation)

| Layer | Tool | Scope | Retention | Purpose |
|-------|------|-------|-----------|---------|
| System snapshots | Timeshift (Linux) | `/` filesystem | ~67 days | Quick rollback after bad update |
| Full-disk cloud | Backblaze Personal (macOS) | Entire disk | 1 year (vendor) | "Lost my Mac entirely" recovery |
| **File versioning** | **Restic + Backrest** | **`$HOME` (both)** | **365+ days** | **"I need the file from 8 months ago"** |

### Data flow

1. **Backrest** triggers `restic backup` on schedule (cron expression in
   config, e.g. `0 */4 * * *` for every 4 hours).
2. **Restic** reads `$HOME`, applies exclude patterns, deduplicates, encrypts
   client-side, and uploads to `b2:<bucket>:/`.
3. **Backrest** runs `restic forget` with retention policy after each backup,
   then periodic `restic prune` and `restic check`.
4. **Backrest** sends a notification on backup completion or failure
   (Shoutrrr → email/Gotify) and pings Healthchecks.io as a heartbeat.

### Notifications and monitoring

| Mechanism | What it tells you | How |
|-----------|------------------|-----|
| **Shoutrrr** (email/Gotify) | Backup succeeded or failed | Backrest hook on `CONDITION_SNAPSHOT_END` / `CONDITION_SNAPSHOT_ERROR` |
| **Healthchecks.io** | Backup is still running on schedule | Backrest hook pings HC URL on success; HC alerts if ping is missed |
| **Backrest web UI** | Full dashboard: history, sizes, errors, next run | `localhost:9898` |
| **`make backup-status`** | Quick CLI check: latest 3 snapshots | Runs `restic snapshots --latest 3` |

Healthchecks.io provides the "Backblaze-like heartbeat" — if a workstation
stops backing up (machine off, network down, daemon crashed), HC sends an
alert after the grace period. The free tier covers up to 20 checks.

Backrest does **not** support aggregated weekly digest emails (e.g., "X GB
uploaded this week"). For data-volume reporting, a v2 enhancement could add a
custom post-backup hook that logs `restic stats` output and feeds a weekly
cron summary. For now, Backrest's web UI shows per-snapshot sizes and the
Healthchecks.io dashboard shows check-in history.

### Pause and resume

Backrest plans can be **disabled** from the web UI — this stops scheduled
backups without removing the configuration. Re-enabling resumes the schedule.
This covers the "pause backups while on metered connection" use case.

There is no bandwidth throttling UI in Backrest. Restic supports
`--limit-upload` and `--limit-download` flags (KiB/s) which can be set as
extra flags in the Backrest plan config. If needed, Ansible can template a
bandwidth limit into the config for metered environments.

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
- **Repo:** B2 bucket (from `restic_b2_bucket` default), password (from
  SOPS var `restic_repo_password`), B2 credentials (from SOPS vars
  `restic_b2_account_id` and `restic_b2_account_key`).
- **Plan:** Backup `$HOME`, exclude file path, schedule (cron), hostname tag.
- **Retention:** `keep-daily: 365`, `keep-weekly: 52`, `keep-monthly: 24`,
  `keep-yearly: 5`.
- **Maintenance:** Prune schedule, check schedule.
- **Notifications:** Shoutrrr hook for email/Gotify on `CONDITION_SNAPSHOT_END`
  and `CONDITION_SNAPSHOT_ERROR`. Healthchecks.io hook for heartbeat ping.
- **Environment:** `B2_ACCOUNT_ID`, `B2_ACCOUNT_KEY` (from SOPS),
  `RESTIC_PASSWORD` (from SOPS).
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

# Repository — B2-direct (v1)
restic_b2_bucket: ""               # e.g. "my-workstation-backups"
restic_repo_password: ""           # override from shared/secrets/vars.sops.yml
restic_b2_account_id: ""           # override from shared/secrets/vars.sops.yml
restic_b2_account_key: ""          # override from shared/secrets/vars.sops.yml

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

# Bandwidth (0 = unlimited; KiB/s)
restic_upload_limit: 0
restic_download_limit: 0

# Notifications
restic_healthchecks_url: ""        # e.g. "https://hc-ping.com/<uuid>"
restic_shoutrrr_url: ""            # e.g. "smtp://user:pass@smtp.example.com:587/?to=you@example.com"

# Excludes
restic_extra_excludes: []  # user-extensible list appended to template
```

### D7: SOPS secrets (`shared/secrets/vars.sops.yml`)

Add to the shared encrypted vars:

- `restic_repo_password` — restic repository encryption key (user-owned,
  restic uses this to encrypt/decrypt all backup data client-side).
- `restic_b2_account_id` — B2 application key ID (scoped to the backup
  bucket, read-write).
- `restic_b2_account_key` — B2 application key secret.

The B2 credentials should use a **bucket-scoped application key** (not the
master key). This limits blast radius if credentials are leaked — the key
can only access the backup bucket, not the entire B2 account.

Optional (for notifications):
- `restic_healthchecks_url` — Healthchecks.io ping URL (contains UUID, mildly
  sensitive).
- `restic_shoutrrr_url` — Shoutrrr notification URL (may contain SMTP
  credentials).

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

### D10: B2 bucket setup (manual, one-time)

Not Ansible-managed (B2 is external infrastructure). Document the setup
procedure in post-install docs:

1. Create B2 bucket (private, server-side encryption SSE-B2 enabled).
2. Create bucket-scoped application key (read + write + list + delete).
3. Add credentials to `shared/secrets/vars.sops.yml` via
   `make edit-secrets-shared`.
4. Init the restic repo: `restic -r b2:<bucket>:/ init`
5. (Optional) Create a Healthchecks.io check for each workstation.

### D11: Notification hooks (`backrest-config.json.j2`)

Configured within the Backrest config template (D3):

1. **Shoutrrr hook** — fires on `CONDITION_SNAPSHOT_END` and
   `CONDITION_SNAPSHOT_ERROR`. Sends backup result (success/failure, duration,
   snapshot size) to the configured Shoutrrr URL (email via SMTP, Gotify, etc.).
   Uses `ON_ERROR_IGNORE` so notification failures don't block backups.

2. **Healthchecks.io hook** — fires on `CONDITION_SNAPSHOT_END`. Pings the
   HC URL on success, pings `<url>/fail` on error. HC alerts if ping is missed
   for the configured grace period (e.g., 8 hours for a 4-hour schedule).

Both hooks are optional — if the SOPS vars are empty, the template omits them.

### D12: Post-install doc updates

Update `docs/post-install.md`:

**Both platforms:**
- [ ] Restic: verify backup works (`make backup-status`)
- [ ] Backrest: open `http://localhost:9898` and confirm dashboard shows repo
- [ ] Verify first backup completes without error
- [ ] (Optional) Pause backups: Backrest web UI → plan → disable schedule
- [ ] (Optional) Bandwidth limit: set `restic_upload_limit` in defaults

**Linux:**
- Replace "Backblaze is macOS-only; verify Timeshift snapshots are running"
  with "Verify Timeshift snapshots (`sudo timeshift --list`) and Restic
  backups (`make backup-status`)"

**macOS:**
- Keep Backblaze sign-in step.
- Add: "Verify Restic backup is running alongside Backblaze"

### D13: Makefile targets

```makefile
backup-status: ## Show latest restic snapshot for this host
	@B2_ACCOUNT_ID=$$(sops -d --extract '["restic_b2_account_id"]' shared/secrets/vars.sops.yml) \
	B2_ACCOUNT_KEY=$$(sops -d --extract '["restic_b2_account_key"]' shared/secrets/vars.sops.yml) \
	RESTIC_PASSWORD=$$(sops -d --extract '["restic_repo_password"]' shared/secrets/vars.sops.yml) \
	restic -r "b2:$(RESTIC_B2_BUCKET):/" snapshots --host "$$(hostname)" --latest 3

backup-browse: ## Open Backrest web UI
	$(if $(filter darwin,$(PLATFORM)),open,xdg-open) http://localhost:9898
```

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| B2 outage or rate limit | Backups fail temporarily | Healthchecks.io alerts on missed heartbeat; Backrest retries on next schedule; B2 has 99.9% SLA |
| Internet connection down | Backups queue up, can't upload | Backrest shows error; backups resume automatically when connection returns; HC alerts after grace period |
| Restic repo password lost | All backups unrecoverable | SOPS-encrypted in repo + 1Password entry; document in disaster recovery runbook |
| B2 application key compromised | Attacker can read/delete backups | Use bucket-scoped key (not master); restic encryption means data is ciphertext; rotate key via `sops` edit + `make apply ROLE=backups` |
| Backrest version drift | Config format changes break template | Pin version in defaults; test upgrades manually before bumping |
| macOS `~/Library` excludes miss new cache paths | Backup grows over time | Periodic review of backup size; add new excludes to template |
| Initial upload is large / slow | First backup takes hours over internet | Expect it; restic dedup means subsequent backups are incremental (fast). Can throttle with `--limit-upload`. |
| Backrest scheduling conflicts with manual `restic` runs | Lock contention, failed operations | Document that Backrest owns scheduling; CLI use should be read-only (snapshots, find, mount, restore) unless Backrest is stopped |

---

## Implementation order

The deliverables have dependencies. Suggested sequencing:

```
Phase 1: Secrets and B2 setup (manual)
  D10: B2 bucket setup (create bucket, app key, restic init)
  D7:  SOPS secrets (repo password, B2 credentials, notification URLs)

Phase 2: Core role implementation
  D6:  Role defaults
  D4:  Exclude patterns template
  D1:  Restic binary installation
  D8:  main.yml orchestrator update

Phase 3: Backrest layer
  D3:  Backrest config template (including notification hooks)
  D11: Notification hooks (Shoutrrr + Healthchecks)
  D5:  Systemd user service template
  D2:  Backrest installation + service enable

Phase 4: Integration
  D9:  Playbook tag updates
  D12: Post-install doc updates
  D13: Makefile targets

Phase 5: Verification
  First backup + restore test on both platforms
  Verify retention policy (simulate forget --dry-run)
  Verify notifications fire on success/failure
  Verify Healthchecks.io heartbeat
```

Phase 1 is lightweight (no server to provision — just B2 console + `sops` edit
+ `restic init`). Phases 2–3 can be developed locally with `--check`/`--diff`
mode. Phase 4 is low-risk wiring.

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
2. Set B2 credentials and repo password:
   ```bash
   export B2_ACCOUNT_ID="..."  # from 1Password or SOPS
   export B2_ACCOUNT_KEY="..."
   export RESTIC_REPOSITORY="b2:my-backup-bucket:/"
   export RESTIC_PASSWORD="..."
   ```
3. `restic snapshots --host old-hostname` → find last snapshot.
4. `restic restore latest --target /tmp/staging --host old-hostname`
5. Cherry-pick from staging into new `$HOME`.

Since B2 is the primary (and only) backend, there is no server dependency.
All you need is credentials + internet access.

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
6. All secrets (repo password, B2 credentials, notification URLs) are
   SOPS-encrypted in `shared/secrets/vars.sops.yml` and not present in
   plaintext anywhere in the repo.
7. Data in B2 is encrypted client-side by restic — `restic cat config`
   against the B2 repo confirms encryption is active.
8. Exclude patterns prevent `~/Library/Caches`, `node_modules`, `.cache`, etc.
   from appearing in backups (verify with `restic ls latest | grep -c Caches`).
9. After 2+ test runs, `restic forget --keep-daily 365 --dry-run` correctly
   identifies which snapshots would be retained.
10. `make backup-status` and `make backup-browse` work on both platforms.
11. Shoutrrr notification fires on backup completion (email/Gotify received).
12. Healthchecks.io shows green check-in after first successful backup.
13. Disabling a Backrest plan from the web UI stops scheduled backups;
    re-enabling resumes them.
