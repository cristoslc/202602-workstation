# Research: Backup Solution Evaluation

**Status:** Active
**Date:** 2026-02-26
**Scope:** Evaluate file-level backup tools that provide 365+ days of versioned
history, unique per-workstation namespacing, and self-hosted backend support.
Cross-platform (macOS + Linux) required.

**In scope:** Deduplicated, encrypted, file-level backup tools that can be
automated via Ansible (systemd timers / launchd plists). Backend options
(self-hosted and cloud).

**Out of scope:** System snapshots (Timeshift stays for Linux), full-disk
imaging, sync tools (covered by sync-user-folders research), Backblaze Personal
(stays as macOS belt-and-suspenders layer).

---

## Context

### Current backup stack

| Platform | Tool | Type | Retention | Gap |
|----------|------|------|-----------|-----|
| macOS | Backblaze Personal | Full-disk cloud backup | 1 year (vendor-managed) | Not self-hostable, no Linux client, opaque |
| Linux | Timeshift | System snapshots (rsync) | 5 daily + 3 weekly + 2 monthly (~67 days max) | No file-level versioning, well under 365 days |

### Requirements

1. **365+ days of file-level version history** — recover any file as it existed
   up to a year ago.
2. **Unique backup per workstation** — each machine's backup is isolated and
   identifiable; no cross-machine pollution.
3. **Self-hosted backend option** — can target a local NAS, home server, or
   self-hosted object storage. Cloud backends acceptable as supplement.
4. **Cross-platform** — single tool for both macOS and Linux workstations.
5. **Ansible-automatable** — install, configure, and schedule via Ansible roles
   (no GUI-dependent setup).
6. **Encrypted at rest** — backup data encrypted before leaving the workstation.
7. **Deduplicated** — storage-efficient; daily backups for a year must not
   require 365x the source size.

### Relationship to existing stack

The new tool complements (does not replace) the existing layers:

- **Timeshift** remains for Linux system rollback (quick restore of `/` after a
  bad update). Different purpose: system snapshots vs. file versioning.
- **Backblaze Personal** remains as a macOS safety net (unlimited cloud backup
  with no config burden). The new tool adds self-hosted + cross-platform +
  longer retention guarantees.

---

## Candidates

### A. Restic

| Attribute | Detail |
|-----------|--------|
| Language | Go (single static binary) |
| First release | 2015 |
| Encryption | AES-256 + Poly1305 (repository-level) |
| Deduplication | Content-defined chunking, global dedup across snapshots |
| Backends | Local, SFTP, S3, B2, Azure, GCS, MinIO, rclone (40+ cloud targets) |
| Retention | `restic forget --keep-daily 365 --keep-weekly 52 --keep-monthly 24 --keep-yearly 5` |
| Per-workstation | `--host` flag filters snapshots by hostname in a shared repo; or use separate repos |
| Scheduling | External: systemd timers (Linux), launchd (macOS), cron |
| Restore | `restic restore`, `restic mount` (FUSE), `restic dump` |
| Wrappers | `resticprofile` (YAML config), `autorestic` (YAML + hooks), `runrestic` |
| Community | Very active, 25k+ GitHub stars, regular releases |
| Ansible | Install binary + template systemd timer/launchd plist + template exclude file |

**Pros:**
- Simplest mental model: `backup`, `forget`, `prune`, `restore`.
- Single static binary — trivial cross-platform install.
- Backend flexibility means self-hosted (SFTP to NAS) and cloud (B2) work
  identically.
- `--host` flag is purpose-built for multi-workstation repos.
- Battle-tested at scale (used by infrastructure teams, not just desktops).

**Cons:**
- No built-in scheduler — requires systemd/launchd/cron setup.
- No web UI (third-party options: `restic-browser`, `restatic`).
- Prune can be slow on very large repos (improved in recent versions).

### B. Kopia

| Attribute | Detail |
|-----------|--------|
| Language | Go |
| First release | 2019 |
| Encryption | AES-256-GCM or ChaCha20-Poly1305 |
| Deduplication | Content-defined chunking |
| Backends | Local, SFTP, S3, B2, Azure, GCS, rclone, WebDAV |
| Retention | Per-directory policies with daily/weekly/monthly/yearly counts |
| Per-workstation | Built-in hostname-based snapshot namespacing |
| Scheduling | Built-in (`kopia server`), or external systemd/launchd |
| Restore | `kopia restore`, `kopia mount` (FUSE) |
| Web UI | Built-in dashboard (optional) |
| Community | Growing, 8k+ GitHub stars |
| Ansible | Install binary + configure repository + set policies |

**Pros:**
- Built-in scheduler and web UI reduce external dependencies.
- Modern UX — policies, server mode, streaming compression.
- Native hostname awareness for multi-workstation setups.
- Compression options (zstd, s2, pgzip) reduce storage further.

**Cons:**
- Younger project — less battle-tested than restic or borg.
- More features = more configuration surface.
- `kopia server` mode adds daemon management complexity.

### C. BorgBackup + Borgmatic

| Attribute | Detail |
|-----------|--------|
| Language | Python + C (Cython) |
| First release | 2010 (Attic fork in 2015) |
| Encryption | AES-256-CTR + HMAC-SHA256 (or repokey/keyfile modes) |
| Deduplication | Fixed-size chunking — best-in-class dedup ratios |
| Backends | Local, SSH/SFTP **only** (no native S3/B2) |
| Retention | `keep_daily: 365`, `keep_weekly: 52` etc. via borgmatic YAML |
| Per-workstation | Separate repos per host (standard practice) |
| Scheduling | Borgmatic + systemd timers / cron |
| Restore | `borg extract`, `borg mount` (FUSE), `borg list` |
| Wrapper | Borgmatic — declarative YAML config, hooks, health checks |
| Community | Very mature, 11k+ GitHub stars, proven track record |
| Ansible | `geerlingguy.borgbackup`-style roles exist; or template borgmatic config |

**Pros:**
- Most mature deduplication — best storage efficiency.
- Borgmatic makes configuration fully declarative (YAML).
- Excellent documentation and long track record.
- Append-only mode for tamper-resistant backups.

**Cons:**
- **SSH-only backend** — need a server running `borg serve`. No native S3/B2.
  Can work around with rclone or BorgBase, but adds friction.
- Python dependency (needs Python 3.9+ on both source and target).
- macOS support works but is less polished (FUSE dependency for mount).
- Borg 2.0 has been in beta for years — migration path unclear.

### D. Duplicati

| Attribute | Detail |
|-----------|--------|
| Language | C# / .NET |
| Backends | Many (S3, B2, SFTP, WebDAV, etc.) |
| UI | Web-based GUI (primary interface) |

**Eliminated.** GUI-centric design doesn't fit CLI/Ansible automation workflow.
.NET runtime dependency on Linux is heavyweight. Historical database corruption
issues. Not evaluated further.

---

## Evaluation matrix

| Criterion | Weight | Restic | Kopia | Borg+Borgmatic |
|-----------|--------|--------|-------|----------------|
| 365-day retention | Must | ✅ flexible `forget` | ✅ built-in policies | ✅ borgmatic config |
| Per-workstation isolation | Must | ✅ `--host` flag | ✅ built-in hostname | ✅ separate repos |
| Self-hosted backend | Must | ✅ SFTP, MinIO, local | ✅ SFTP, S3, local | ✅ SFTP only |
| Cross-platform | Must | ✅ static Go binary | ✅ Go binary | ⚠️ Python + FUSE on macOS |
| Ansible automation | High | ✅ binary + systemd | ✅ binary + built-in sched | ✅ borgmatic role |
| Encryption at rest | Must | ✅ AES-256 | ✅ AES-256-GCM | ✅ AES-256 |
| Deduplication | High | ✅ excellent | ✅ excellent | ✅ best ratios |
| Maturity / stability | High | ✅ 10+ years, proven | ⚠️ 6 years, maturing | ✅ 15+ years, most proven |
| Simplicity | Med | ✅ minimal concepts | ⚠️ more features/config | ⚠️ Python + borgmatic stack |
| Backend flexibility | Med | ✅ S3, SFTP, rclone | ✅ S3, SFTP, rclone | ❌ SSH/SFTP only |

---

## Backend options

The backup tool needs a target. These are independent of the tool choice
(assuming S3/SFTP support):

### Self-hosted

| Backend | Protocol | Cost | Notes |
|---------|----------|------|-------|
| NAS (Synology, TrueNAS) + SFTP | SFTP | Hardware cost only | Works with all three tools. Simplest self-hosted path. |
| NAS + MinIO | S3 | Hardware cost only | Self-hosted S3 API. Works with restic/kopia. Overkill for personal use. |
| Dedicated server + borg serve | SSH | Hardware cost only | Required for Borg. Not needed for restic/kopia. |
| Old workstation + SFTP | SFTP | Free (repurpose hardware) | Viable for a single-user setup. |

### Cloud (supplement or alternative)

| Backend | Protocol | Storage | Egress | Notes |
|---------|----------|---------|--------|-------|
| Backblaze B2 | S3 | $6/TB/month | $0.01/GB | Cheapest S3-compatible. Good restic/kopia target. |
| Wasabi | S3 | $6.99/TB/month | Free | No egress fees. 90-day minimum storage policy. |
| Hetzner Storage Box | SFTP/Borg | €3.29/TB/month | Included | Native BorgBackup support. EU-hosted. |
| BorgBase | Borg SSH | From $2/month (100 GB) | Included | Managed Borg hosting. Append-only support. |

---

## Recommendation: Restic

Restic is the strongest fit for this stack:

1. **Single Go binary** — `ansible.builtin.get_url` downloads the binary.
   No Python runtime, no .NET, no FUSE dependency. Same install path on macOS
   and Linux.

2. **Backend flexibility** — Start with SFTP to a NAS, add B2 for offsite
   later. No tool change needed. Borg's SSH-only limitation is a meaningful
   constraint for future flexibility.

3. **`--host` flag** — Purpose-built for the "unique backup per-workstation"
   requirement. Multiple machines can share one repo while keeping snapshots
   isolated.

4. **365-day retention** — Direct mapping to requirements:
   ```
   restic forget \
     --keep-daily 365 \
     --keep-weekly 52 \
     --keep-monthly 24 \
     --keep-yearly 5 \
     --host "$(hostname)" \
     --prune
   ```

5. **Ansible integration** — The role would:
   - Install the restic binary (platform-appropriate).
   - Template a wrapper script with repo URL, password, and exclude patterns.
   - Install a systemd timer (Linux) or launchd plist (macOS).
   - Store the repo password as a SOPS-encrypted variable.

6. **Complements existing stack** — Timeshift handles system rollback
   (different cadence, different purpose). Backblaze handles "I lost my
   Mac entirely." Restic handles "I need the version of this file from 8
   months ago" on both platforms.

### Why not Kopia?

Kopia is a credible alternative and could be revisited if restic proves
insufficient. The main reasons to prefer restic today:

- Restic's larger community means more Ansible roles, more blog posts, more
  Stack Overflow answers for edge cases.
- Kopia's built-in scheduler is nice but adds daemon management; systemd timers
  are already the convention in this repo for scheduled tasks.
- Restic's repo format is stable and well-documented; Kopia is still evolving.

### Why not Borg?

Borg's deduplication is marginally better, but the SSH-only backend is a real
constraint. If you already have a dedicated server running `borg serve`, it's
excellent. For a setup that might start with a NAS (SFTP) and add cloud later,
restic's backend flexibility wins.

---

## Suggested Ansible role structure

```
shared/roles/backups/tasks/
├── main.yml          # existing — add restic include
├── backblaze.yml     # existing (macOS)
├── timeshift.yml     # existing (Linux)
└── restic.yml        # new: cross-platform restic setup

shared/roles/backups/templates/
├── timeshift.json.j2         # existing
├── restic-backup.sh.j2       # new: wrapper script
├── restic-backup.timer.j2    # new: systemd timer (Linux)
├── restic-backup.service.j2  # new: systemd service (Linux)
└── com.restic.backup.plist.j2 # new: launchd plist (macOS)

shared/roles/backups/defaults/
└── main.yml          # new: restic_repo_url, restic_password_file, restic_excludes, restic_keep_*
```

---

## Next steps

1. **Choose a backend** — Do you have a NAS with SFTP, or prefer cloud (B2)?
   This determines the `restic_repo_url` format.
2. **Define exclude patterns** — What directories to skip (caches, node_modules,
   `.local/share/Trash`, etc.).
3. **Decide on wrapper** — Plain shell script vs. `resticprofile` (YAML config
   file that wraps restic commands).
4. **Implementation** — Create the Ansible role tasks, templates, and defaults.
   This could become a PRD if the implementation is non-trivial, or go straight
   to implementation if the scope is clear.

---

## References

- Restic documentation: https://restic.readthedocs.io/
- Restic GitHub: https://github.com/restic/restic
- Kopia documentation: https://kopia.io/docs/
- BorgBackup documentation: https://borgbackup.readthedocs.io/
- Borgmatic documentation: https://torsion.org/borgmatic/
- Backblaze B2 pricing: https://www.backblaze.com/cloud-storage/pricing
- Wasabi pricing: https://wasabi.com/pricing
