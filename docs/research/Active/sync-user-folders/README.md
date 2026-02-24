# Sync user folders: migration and ongoing sync

**Status:** Active
**Date:** 2026-02-24
**Scope:** Evaluate tools and approaches for (A) non-destructively migrating
user data folders between machines after bootstrap, and (B) keeping user data
folders in ongoing sync across 2-3 workstations.

**In scope:** Documents, Pictures, Music, Videos, Downloads, and similar
user-created content folders.

**Out of scope:** Dotfiles (managed by Stow), system configuration (managed by
Ansible), package installation, secrets (managed by SOPS/age).

---

## Context

After `make bootstrap` provisions a new workstation, two data-transfer needs
remain:

1. **One-time migration** — Bulk-copy user folders from the old machine to the
   new one. The target already has a working OS, a user account, and all
   tooling installed via Ansible.

2. **Ongoing sync** — Keep user folders in sync across 2-3 machines (e.g.,
   desktop + laptop, Linux + macOS) as the user works on either.

These are distinct problems with different tool requirements. Migration
prioritizes throughput, resume, and metadata fidelity. Ongoing sync prioritizes
conflict resolution, bandwidth efficiency, and low-overhead operation.

### Current repo capabilities

The repo already handles:

- **Dotfiles:** GNU Stow with 4-layer deployment + `local.*` overrides
- **Secrets:** SOPS/age encryption + magic-wormhole key transfer
- **Config migration:** Pre-existing dotfiles backed up to
  `~/.workstation-backup/` and migrated to `local.*` overrides
- **SSH keys:** Provisioned by bootstrap (available for rsync/Unison transport)
- **Tailscale VPN:** Installed via `shared/roles/vpn/` (NAT traversal)

What is **not** handled: user data folder migration or sync.

---

## Part A: One-time migration

### Tool evaluations

#### 1. rsync

The standard Unix file-copying tool. Transfers deltas at the block level over
SSH.

**Non-destructive guarantees:**

- No `--delete` by default. Files on the destination that do not exist on the
  source are left untouched.
- Atomic writes. Without `--inplace`, rsync writes to a temporary file first,
  then renames atomically. An interrupted transfer never leaves a half-written
  file at its final path.
- `--dry-run` (`-n`) previews every action without touching disk.
- Every transferred file is verified with a post-transfer checksum regardless
  of whether `--checksum` was passed. The `--checksum` flag only controls the
  *skip heuristic* (checksum vs. size+mtime).

**Resume capability:**

- `--partial` keeps partially transferred files so the next run can delta from
  them instead of restarting.
- `--partial-dir=.rsync-partial` stashes partials in a hidden directory.
- `-P` is shorthand for `--partial --progress`.
- `--append-verify` resumes by appending, then full-file checksums; falls back
  to `--inplace` retransfer on mismatch.

**Cross-platform (Linux <-> macOS):**

- Works natively on both. macOS ships rsync 2.6.9 (ancient); Homebrew rsync
  3.2+ is required for `--info=progress2`, `--xattrs`, and modern protocol.
- `-a` preserves owner, group, permissions, timestamps, symlinks.
- `-X` (`--xattrs`) preserves extended attributes on both platforms.
- `-A` (`--acls`) preserves POSIX ACLs. macOS uses NFSv4-style ACLs, so
  cross-platform ACL transfer is lossy. Rarely matters for user data.
- macOS resource forks / Finder metadata: `--fake-super` encodes these as
  xattrs on Linux, but for user data this is usually unnecessary.

**Bandwidth / progress:**

- `--info=progress2` shows overall transfer progress (rsync 3.1+).
- `--no-inc-recursive` forces a full file-list scan up front for accurate
  percentage.
- `--bwlimit=RATE` caps bandwidth.

**Ansible integration:**

- First-class support via `ansible.posix.synchronize` (see section below).
- Fully scriptable with well-defined exit codes.

**Recommended invocation:**

```bash
rsync -ahAX \
  --info=progress2 --no-inc-recursive \
  --partial-dir=.rsync-partial \
  --checksum \
  -e ssh \
  user@old-machine:/home/user/{Documents,Pictures,Music,Videos,Downloads}/ \
  /home/user/
```

Add `--dry-run` for preview. Add `--bwlimit=50m` to cap bandwidth.

---

#### 2. Unison

Bidirectional file synchronizer written in OCaml. Detects changes on both
sides and propagates non-conflicting updates in both directions.

**Non-destructive guarantees:**

- Interactive by default. Shows every planned action and waits for
  confirmation. Strongest preview model of any tool evaluated.
- `-batch` mode propagates non-conflicting changes, skips conflicts.
- `-confirmbigdel` prevents catastrophic one-sided wipes.
- Backup copies enable three-way merge and safe conflict resolution.

**Resume:** Resilient to crashes at the state level, but no partial-file
resume. Retransfers whole files if interrupted mid-file. Uses rsync-like
compression for delta transfers of changed regions within large files.

**Cross-platform:** Available via Homebrew (macOS) and distro packages (Linux).
Version 2.52+ eliminated the client/server version-matching requirement.
No xattr or ACL support (syncs content, permissions, timestamps only).

**Best for:** Ongoing bidirectional sync (see Part B). Overkill for one-time
migration.

---

#### 3. rclone

Command-line program for cloud storage management. Also supports local-to-local
and SFTP transfers. Multi-threaded.

**Non-destructive:** `rclone copy` never deletes destination files. `bisync`
is experimental/beta and can lose data on misconfiguration.

**Resume:** File-level skip on re-run (identical files are not retransferred),
but no partial-file resume. Interrupted large files restart from scratch.

**Cross-platform:** Single static binary for both platforms. Metadata
preservation (`--metadata`) is limited: file-only (not directories), no ACLs,
no hard links. Mac extended attributes have reported issues.

**Performance:** Multi-threaded transfers (4x faster than rsync on 10 Gbps+
per Jeff Geerling's testing), but whole-file only (no block-level deltas).

**Best for:** Cloud storage operations, or high-bandwidth local transfers
where metadata fidelity is not critical.

---

#### 4. tar + SSH pipeline

Streaming archive directly through an SSH tunnel:

```bash
tar czf - /source/ | ssh user@dest "cd /destination && tar xzf -"
```

**Non-destructive:** Additive only (creates files, does not delete). No
dry-run. No checksum verification.

**Resume:** None. Interrupted transfers restart from scratch.

**Cross-platform:** GNU tar vs. BSD tar flag differences. Install GNU tar via
Homebrew on macOS for `--xattrs` and `--acls` support.

**Best for:** One-shot bulk seed on a reliable LAN (avoids rsync's
file-list-building overhead), followed by rsync for verification and
incremental sync.

---

#### 5. macOS Migration Assistant

**Not applicable.** No Linux support in either direction. GUI-only, no
scriptability, coarse-grained categories, no resume, no dry-run.

---

#### 6. Ansible-native approaches

**ansible.posix.synchronize** (rsync wrapper) is the recommended module:

| Parameter | Default | Notes |
|-----------|---------|-------|
| `archive` | `true` | Equivalent to rsync `-a` |
| `delete` | `false` | Non-destructive by default |
| `checksum` | `false` | Use checksums instead of size+mtime |
| `compress` | `true` | Compress during transfer |
| `rsync_opts` | `[]` | Pass arbitrary rsync flags |

Non-destructive by default. Forces `--delay-updates` for consistency.
Supports `--check` mode for dry-run. Requires passwordless sudo and
`use_ssh_args: true` for non-standard SSH configurations.

**ansible.builtin.copy** is unsuitable for bulk data: does not scale beyond
hundreds of files (10x+ slower), loads files into memory, no resume, no delta
transfer, no progress.

---

### Part A comparison matrix

| Criterion | rsync | Unison | rclone | tar+ssh | synchronize |
|---|---|---|---|---|---|
| **Non-destructive default** | Yes | Yes (interactive) | Yes (`copy`) | Yes (additive) | Yes |
| **Dry-run / preview** | `--dry-run` | Interactive | `--dry-run` | No | `--check` mode |
| **Checksum verification** | Always post-transfer | Checksum-based | `--checksum` flag | No | Yes |
| **Partial-file resume** | `--partial` | No | No | No | Via `rsync_opts` |
| **Block-level delta** | Yes | Yes | No (whole file) | No | Yes (rsync) |
| **Linux <-> macOS** | Yes | Yes | Yes | Yes | Yes |
| **Permissions/xattrs/ACLs** | Full (`-aAX`) | Perms+times only | Limited | GNU tar only | Via `rsync_opts` |
| **Progress reporting** | `--info=progress2` | Per-file | `-P` | `pv` pipe | Via `rsync_opts` |
| **Bandwidth limiting** | `--bwlimit` | No | `--bwlimit` | `pv` | Via `rsync_opts` |
| **Ansible-native** | Via synchronize | No | No | Shell only | Yes |

### Part A recommendation

**Primary tool: rsync** (via `ansible.posix.synchronize` or a `make` target).
Clear winner across every criterion: non-destructive by default, partial-file
resume, block-level delta transfer, full metadata preservation, cross-platform,
first-class Ansible integration.

**Secondary: tar+ssh** for optional one-shot seed of very large datasets on a
fast LAN, followed by rsync for verification.

---

## Part B: Ongoing sync

### Tool evaluations

#### 1. Syncthing

Peer-to-peer continuous file synchronization. FOSS (MPL-2.0), written in Go.

**Architecture:** Fully decentralized. No cloud server required. Devices
discover each other via global discovery servers, local broadcast, or static
addresses. Data flows directly between devices (or via encrypted relays when
direct connection fails). All relay traffic remains end-to-end encrypted.

**Conflict resolution:** When both sides modify the same file, Syncthing
renames the older version to
`<filename>.sync-conflict-<date>-<time>-<modifiedBy>.<ext>`. No interactive
merge. Manual inspection required.

**Bandwidth efficiency:** Block-based transfer (128 KiB - 16 MiB blocks).
Only changed blocks are transferred. Does NOT use rolling checksums like rsync,
so prepended data causes full re-upload (rare for typical user files).

**Encryption:** TLS with perfect forward secrecy in transit. Device
authentication via cryptographic certificates. "Untrusted device" mode
encrypts data at rest on remote nodes. No local at-rest encryption (relies on
OS-level LUKS/FileVault).

**File versioning:** Four built-in strategies per folder:

| Strategy | Behavior |
|----------|----------|
| Trashcan | Moves to `.stversions`, optional age-based cleanup |
| Simple | Keeps N timestamped copies |
| Staggered | Decaying schedule: many recent, fewer old |
| External | Delegates to user-provided script |

**Selective sync:** `.stignore` files with glob patterns, negation (`!`),
case-insensitive matching, `#include` directives.

**Ansible installability:** Official apt repo with GPG key (Linux), `brew
install syncthing` (macOS). Multiple community Ansible roles exist.
Configuration is XML-based (`config.xml`) and manageable via REST API.

**Resource usage:** Main weakness. Memory scales with file count (millions of
files can use 1-8 GB RAM). CPU spikes during hashing and periodic scans.
Tunable: increase `fsWatcherDelayS`, disable scan progress, set `GOMEMLIMIT`.
For 2-3 machines syncing tens of thousands of files: manageable.

**NAT traversal:** Built-in global discovery, local discovery, UPnP/NAT-PMP,
relay pool. Self-hostable. Works behind NAT out of the box.

---

#### 2. Unison

Bidirectional file synchronizer. FOSS (GPL-3.0), written in OCaml.

**Architecture:** Replica-to-replica over SSH. No daemon, no server component.
Runs on demand (cron, systemd timer, or manual).

**Conflict resolution:** Strongest of all tools evaluated. In interactive mode:
keep left, keep right, skip, or merge. In batch mode: `prefer = newer` or
`prefer = <root>` auto-resolves. External merge tools configurable (diff3,
kdiff3). Detects "false conflicts" (both sides changed identically).

**Bandwidth efficiency:** Excellent. Uses rsync-like rolling-checksum algorithm
for delta transfers. Only changed blocks of large files are transmitted.

**Encryption:** No built-in. Relies on SSH for transport. No at-rest
encryption (use OS-level).

**File versioning:** No built-in. `backup` and `backuplocation` preferences
keep copies of overwritten files.

**Selective sync:** Profile-based (`~/.unison/`) with `path` directives
(explicit inclusion) and `ignore` patterns.

```
root = /home/user
root = ssh://otherhost//home/user
path = Documents
path = Pictures
path = Music
path = Videos
ignore = Name *.tmp
ignore = Name .DS_Store
```

**Ansible installability:** `apt install unison` (Debian/Ubuntu), `brew
install unison` (macOS). Profile files are plain text, easy to template.

**Resource usage:** Minimal. Not a daemon. CPU and memory only used during
active sync. No battery impact when idle.

**NAT traversal:** None. Requires direct SSH access. Pair with
Tailscale/WireGuard for machines behind NAT.

---

#### 3. rclone bisync

Bidirectional sync built into rclone. FOSS (MIT).

**Architecture:** CLI tool, runs on demand. No daemon. Supports 40+ backends
(local, SFTP, S3, Google Drive, etc.).

**Conflict resolution:** Keeps both versions with `.path1`/`.path2` suffixes.
`--conflict-resolve` options: `newer`, `older`, `larger`, `smaller`, `path1`,
`path2`. Safety: `--check-access` verifies marker files, `--max-delete`
prevents mass deletions.

**Bandwidth efficiency:** Whole-file transfers only (no block-level delta).
Multi-threaded.

**Encryption:** `crypt` remote provides client-side encryption at rest
(NaCl SecretBox: XSalsa20 + Poly1305). File and directory names encryptable.
Transit depends on backend.

**File versioning:** No built-in. `--backup-dir` moves replaced files to
dated backup directory.

**Selective sync:** Powerful `--filter`, `--include`, `--exclude` with glob
patterns and filter files.

**Resource usage:** Lightweight (on-demand, no daemon). Lock files prevent
concurrent runs.

---

#### 4. Nextcloud

Self-hosted cloud sync. Server is AGPL-3.0, client is GPL-2.0.

**Architecture:** Client-server. Server runs on Linux (PHP + DB + web server).
Desktop clients for Linux (AppImage, distro packages, Flatpak), macOS, Windows.

**Conflict resolution:** Server version is canonical. Local conflicts renamed
to `<file> (conflicted copy <date> <time>).ext`. No merge tool.

**Bandwidth efficiency:** No block-level delta sync. Entire files re-uploaded
on change. Notable gap for large files.

**File versioning:** Built-in server-side versioning with staggered retention.
Browsable in web UI.

**Verdict for 2-3 personal machines:** Overkill. Requires maintaining a full
server stack (PHP, MariaDB/PostgreSQL, Nginx, Redis). Justified only if web
access or collaboration features are needed.

---

#### 5. Seafile

Self-hosted cloud sync. Community Edition is AGPL-3.0. Server written in C
(much lighter than Nextcloud).

**Key advantages over Nextcloud:** Block-level delta sync and deduplication.
Better performance (benchmarks: 11 GB in 6 minutes at 30% server resources
vs. Nextcloud at 80%). Strong client-side encryption (AES-256/CBC per
library).

**Verdict:** Better than Nextcloud for pure file sync, but still requires
server infrastructure.

---

#### 6. Resilio Sync

Peer-to-peer sync using modified BitTorrent protocol. **Proprietary.**

Block-level delta transfer and built-in NAT traversal, but closed source,
depends on vendor tracker servers, and limited conflict resolution.

**Verdict:** Functionally similar to Syncthing without FOSS guarantees. Not
recommended.

---

#### 7. Cloud-native (Dropbox, Google Drive, OneDrive)

| | Dropbox | Google Drive | OneDrive |
|---|---|---|---|
| **Linux client** | Official | No official | No official |
| **Block-level sync** | Yes | No | Yes |
| **Self-hosted** | No | No | No |
| **Free tier** | 2 GB | 15 GB | 5 GB |

**Verdict:** Only Dropbox has an official Linux client. None are self-hosted.
Useful as offsite backup targets (via rclone) but not primary sync for a
privacy-conscious workstation setup.

---

### Part B comparison matrix

| Criterion | Syncthing | Unison | rclone bisync | Nextcloud | Seafile | Resilio |
|---|---|---|---|---|---|---|
| **FOSS** | Yes (MPL-2.0) | Yes (GPL-3.0) | Yes (MIT) | Yes (AGPL) | Yes (AGPL) | No |
| **P2P / no server** | Yes | Yes (SSH) | Depends | No | No | Yes |
| **Always-on daemon** | Yes | No (on-demand) | No (on-demand) | Client+server | Client+server | Yes |
| **Delta sync** | Block-based | rsync rolling checksum | No (whole file) | No | Block-level dedup | BitTorrent blocks |
| **Conflict handling** | Rename conflict file | Interactive/auto resolve | Keep both + flags | Rename conflict file | Rename conflict file | Keep newest |
| **At-rest encryption** | Untrusted device mode | No | crypt overlay | Experimental E2EE | AES-256/library | AES-128 |
| **File versioning** | 4 strategies | No (backup pref) | No (backup-dir) | Staggered server-side | Built-in per-library | Basic |
| **Selective sync** | `.stignore` | `path`/`ignore` | `--filter` | Folder-level + VFS | Per-library | Per-folder |
| **apt installable** | Yes (official repo) | Yes | Yes | Client: yes | Yes | No |
| **brew installable** | Yes | Yes | Yes | Yes (cask) | Yes | Yes (cask) |
| **Resource usage** | Moderate-high | Very low | Low | Server: moderate | Server: low | Low-moderate |
| **NAT traversal** | Built-in | None (needs SSH) | N/A | N/A (client-server) | N/A | Built-in |
| **Setup complexity** | Low-medium | Low (+ cron) | Medium (config+cron) | High (server stack) | Medium-high | Low |

---

## Integration with this repo

### Existing patterns to build on

| Pattern | Where | Reusable for |
|---------|-------|-------------|
| Magic wormhole transport | `scripts/transfer-key.sh` | Could extend to small data transfers |
| Make target convention | `Makefile` (noun-first: `key-send`) | `data-pull`, `data-sync` targets |
| SSH key provisioning | Bootstrap flow | rsync/Unison SSH transport |
| Tailscale VPN | `shared/roles/vpn/` | NAT traversal for Unison |
| Ansible role structure | `shared/roles/` | `sync` or `data-migration` role |
| Phase playbooks | `linux/plays/`, `macos/plays/` | Post-bootstrap data phase |
| GPG key idempotency pattern | Various roles | Syncthing apt repo key |

### Ansible integration sketch

#### Migration role (rsync via synchronize)

```yaml
# shared/roles/data-migration/tasks/main.yml
- name: Migrate user data folders from source machine
  ansible.posix.synchronize:
    src: "{{ data_migration_source_user }}@{{ data_migration_source_host }}:{{ item }}/"
    dest: "{{ ansible_env.HOME }}/{{ item | basename }}/"
    archive: true
    checksum: true
    compress: "{{ data_migration_compress | default(true) }}"
    mode: pull
    use_ssh_args: true
    rsync_opts:
      - "--partial-dir=.rsync-partial"
      - "--info=progress2"
      - "--no-inc-recursive"
      - "--human-readable"
  loop: "{{ data_migration_folders }}"
  tags: [data-migration]

# shared/roles/data-migration/defaults/main.yml
data_migration_source_host: ""
data_migration_source_user: "{{ ansible_user_id }}"
data_migration_folders:
  - "{{ ansible_env.HOME }}/Documents"
  - "{{ ansible_env.HOME }}/Pictures"
  - "{{ ansible_env.HOME }}/Music"
  - "{{ ansible_env.HOME }}/Videos"
  - "{{ ansible_env.HOME }}/Downloads"
data_migration_compress: true
```

#### Sync role (Syncthing installation)

```yaml
# shared/roles/sync/tasks/debian.yml
- name: Check Syncthing GPG keyring
  ansible.builtin.stat:
    path: /usr/share/keyrings/syncthing-archive-keyring.gpg
  register: syncthing_keyring

- name: Download Syncthing GPG key
  when: not syncthing_keyring.stat.exists
  ansible.builtin.shell: >
    curl -fsSL https://syncthing.net/release-key.gpg |
    gpg --dearmor -o /usr/share/keyrings/syncthing-archive-keyring.gpg
  become: true

- name: Add Syncthing apt repository
  ansible.builtin.apt_repository:
    repo: >-
      deb [signed-by=/usr/share/keyrings/syncthing-archive-keyring.gpg]
      https://apt.syncthing.net/ syncthing stable
    filename: syncthing
    state: present
  become: true

- name: Install Syncthing
  ansible.builtin.apt:
    name: syncthing
    state: present
  become: true

- name: Enable Syncthing user service
  ansible.builtin.systemd:
    name: "syncthing@{{ ansible_user_id }}"
    enabled: true
    state: started
    scope: system
  become: true

# shared/roles/sync/tasks/darwin.yml
- name: Install Syncthing (macOS)
  community.general.homebrew:
    name: syncthing
    state: present

- name: Start Syncthing service (macOS)
  community.general.homebrew_service:
    name: syncthing
    state: started
```

### Make targets sketch

```makefile
# ── Data migration (one-time) ───────────────────────────────────────
data-pull:  ## Pull user folders from another machine (SOURCE=host)
	@test -n "$(SOURCE)" || { echo "Usage: make data-pull SOURCE=hostname"; exit 1; }
	rsync -ahAX --info=progress2 --no-inc-recursive \
	  --partial-dir=.rsync-partial --checksum \
	  -e ssh $(SOURCE):~/"{Documents,Pictures,Music,Videos,Downloads}/" ~/

data-pull-dry:  ## Preview data-pull without transferring
	@test -n "$(SOURCE)" || { echo "Usage: make data-pull-dry SOURCE=hostname"; exit 1; }
	rsync -ahAX --info=progress2 --no-inc-recursive \
	  --partial-dir=.rsync-partial --checksum --dry-run \
	  -e ssh $(SOURCE):~/"{Documents,Pictures,Music,Videos,Downloads}/" ~/
```

---

## Recommendations

### For one-time migration (Part A): rsync

**Use rsync** (directly or via `ansible.posix.synchronize`). Wins across every
criterion: non-destructive by default, partial-file resume, block-level delta
transfer, full metadata preservation, cross-platform, first-class Ansible
integration.

**Implementation path:**

1. Add `make data-pull SOURCE=hostname` and `make data-pull-dry` targets
2. Optionally, create `shared/roles/data-migration/` using
   `ansible.posix.synchronize` for the Ansible flow
3. Ensure Homebrew rsync 3.2+ is installed on macOS (system rsync is ancient)
4. SSH key authentication is already provisioned by bootstrap
5. Use Tailscale hostnames for machines behind NAT

### For ongoing sync (Part B): Syncthing or Unison

**Primary recommendation: Syncthing**

Best overall for 2-3 personal workstations:

- Zero infrastructure (no server to maintain)
- Works behind NAT out of the box (relay, UPnP, discovery)
- Continuous real-time sync (daemon)
- Staggered file versioning for accidental deletion recovery
- Strong selective sync via `.stignore`
- FOSS, actively maintained, large community
- Installable via apt and brew (Ansible-friendly)
- Existing GPG key idempotency pattern in repo is directly reusable

Main tradeoff: higher resource usage than on-demand tools. Tunable for typical
user folder volumes.

**Alternative: Unison**

Best if you prefer explicit sync triggers over always-on daemon:

- Near-zero resource usage (no background process)
- Best-in-class conflict resolution (interactive + auto modes)
- True rsync-like rolling-checksum delta transfer
- Profile-based config is clean and templatable
- Requires SSH access (pair with Tailscale for NAT traversal)
- No file versioning (layer restic or similar for backups)

**Hybrid option: Syncthing + rclone**

Combine Syncthing for real-time P2P sync between workstations and rclone for
periodic encrypted offsite backups to a cloud backend (B2, S3, or
crypt-wrapped Google Drive).

### What to avoid

| Tool | Why |
|------|-----|
| Nextcloud/Seafile/ownCloud | Server infrastructure burden for 2-3 machines |
| SparkleShare | Git-based storage is wrong for large binary files |
| Resilio Sync | Proprietary, vendor-dependent |
| macOS Migration Assistant | No Linux support, no scriptability |
| ansible.builtin.copy | Never for bulk data migration |

### Decision matrix summary

| Need | Tool | Why |
|------|------|-----|
| One-time migration | rsync | Resume, delta, metadata, Ansible-native |
| Ongoing sync (always-on) | Syncthing | P2P, NAT traversal, versioning, zero infra |
| Ongoing sync (on-demand) | Unison | Lightweight, best conflict resolution, SSH |
| Offsite backup | rclone + crypt | 40+ backends, client-side encryption |
| Initial LAN seed | tar+ssh | Avoids file-list overhead for first bulk copy |

---

## Implementation notes

1. **Homebrew rsync on macOS.** System rsync (2.6.9) lacks modern features.
   Ensure the `packages` role or a pre-task installs Homebrew rsync 3.2+.

2. **SSH key authentication.** Already provisioned by bootstrap. Both rsync
   and Unison transport over SSH.

3. **Tailscale for NAT traversal.** Already installed via `shared/roles/vpn/`.
   Use Tailscale hostnames (e.g., `make data-pull SOURCE=desktop`) for
   machines behind NAT.

4. **No `--delete` in defaults.** Migration and sync should never delete
   destination files unless the user explicitly opts in.

5. **Syncthing configuration management.** REST API at `localhost:8384`
   enables programmatic folder/device setup. Could be managed by an Ansible
   role post-install.

6. **Conflict resolution workflow.** For Syncthing: periodic `find ~/Documents
   -name '*.sync-conflict-*'` to surface conflicts. For Unison: interactive
   mode handles conflicts at sync time.

7. **Syncthing apt repo.** Follow the repo's GPG key idempotency pattern:
   guard download+dearmor with `ansible.builtin.stat`, set `filename:
   syncthing` on `apt_repository`.

---

## Sources

### rsync
- [rsync(1) man page](https://man7.org/linux/man-pages/man1/rsync.1.html)
- [rsync - ArchWiki](https://wiki.archlinux.org/title/Rsync)
- [Resume partially transferred files (OSTechNix)](https://ostechnix.com/how-to-resume-partially-downloaded-or-transferred-files-using-rsync/)
- [rsync overall progress (Dave Dribin)](https://www.dribin.org/dave/blog/archives/2024/01/21/rsync-overall-progress/)
- [rsync bandwidth limiting (nixCraft)](https://www.cyberciti.biz/faq/how-to-set-keep-rsync-from-using-all-your-bandwidth-on-linux-unix/)
- [rsync xattrs cross-platform (kernelcrash.com)](https://www.kernelcrash.com/blog/using-rsync-to-backup-from-osx-to-linux/2009/06/20/)

### Unison
- [Unison GitHub repository](https://github.com/bcpierce00/unison)
- [Unison - ArchWiki](https://wiki.archlinux.org/title/Unison)
- [Unison official site (UPenn)](https://www.cis.upenn.edu/~bcpierce/unison/)

### rclone
- [rclone bisync documentation](https://rclone.org/bisync/)
- [rclone copy documentation](https://rclone.org/commands/rclone_copy/)
- [rclone crypt documentation](https://rclone.org/crypt/)
- [rclone vs rsync - Jeff Geerling](https://www.jeffgeerling.com/blog/2025/4x-faster-network-file-sync-rclone-vs-rsync/)

### Syncthing
- [Syncthing documentation](https://docs.syncthing.net/)
- [Syncthing Block Exchange Protocol](https://docs.syncthing.net/specs/bep-v1.html)
- [Syncthing file versioning](https://docs.syncthing.net/users/versioning.html)
- [Syncthing ignoring files](https://docs.syncthing.net/users/ignoring.html)
- [Syncthing tuning](https://docs.syncthing.net/users/tuning.html)

### Nextcloud / Seafile
- [Nextcloud desktop client (GitHub)](https://github.com/nextcloud/desktop)
- [Nextcloud Ansible collection](https://github.com/nextcloud/ansible-collection-nextcloud-admin)
- [Seafile GitHub repository](https://github.com/haiwen/seafile)

### Ansible
- [ansible.posix.synchronize module](https://docs.ansible.com/projects/ansible/latest/collections/ansible/posix/synchronize_module.html)
- [ansible.builtin.copy module](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/copy_module.html)
- [Ansible copy vs synchronize (christopherburg.com)](https://www.christopherburg.com/blog/ansible-copy-versus-synchronize/)

### macOS Migration Assistant
- [Apple Support: Migration Assistant](https://support.apple.com/en-us/102613)
- [What Migration Assistant transfers (mactakeawaydata.com)](https://mactakeawaydata.com/what-does-migration-assistant-transfer/)
