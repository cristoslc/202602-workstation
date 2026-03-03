---
title: "SPIKE-006: Sync User Folders"
artifact: SPIKE-006
status: Complete
author: cristos
created: 2026-02-24
last-updated: 2026-03-03
---

# SPIKE-006: Sync User Folders

**In scope:** Documents, Pictures, Music, Videos, Downloads, and similar
user-created content folders. Code repositories (working tree sync — see
[unison-code-sync.md](unison-code-sync.md)).

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
xattr and ACL support added in 2.53.0 (`xattrs = true`, `acl = true`).
See [unison-known-issues.md](unison-known-issues.md) for cross-platform caveats,
OCaml 5.x compilation risks, and fsmonitor fragmentation.

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

Self-hosted cloud sync and groupware platform. Server is AGPL-3.0, client is
GPL-2.0.

**Architecture:** Client-server. Server runs on Linux (PHP + DB + web server).
Docker AIO is the official deployment method, bundling Apache, MariaDB, Redis,
Collabora, and Borg backup into a managed multi-container stack. Desktop
clients for Linux (AppImage, PPA, Flatpak), macOS (`brew install --cask
nextcloud`), Windows. CLI client (`nextcloudcmd`) ships with desktop packages
-- performs a single sync run and exits (suitable for cron).

**Server requirements:** 2 cores, 2-4 GB RAM, SSD storage. Supports
MySQL/MariaDB (recommended), PostgreSQL, SQLite (testing only). Docker AIO
handles PHP, database, and reverse proxy (Caddy) in containers. Minimum
viable: a small VPS or home server.

**Sync performance:** **No block-level delta sync.** When any part of a file
changes, the entire file is re-uploaded. Chunked upload (10 MiB chunks) helps
reliability for large files but is ~21% slower than single-file upload due to
per-request overhead. Small-file sync is architecturally weak: each file
requires an HTTP WebDAV request + database transaction. Community reports:
~1,000 files at 10 MB total took ~7 minutes bidirectional; individual small
files have a floor of 1-2 seconds each.

**Conflict resolution:** Server version is canonical. Local conflicts renamed
to `<file> (conflicted copy <date> <time>).ext`. No merge support. No bulk
conflict resolution UI.

**End-to-end encryption:** Officially "production ready" since desktop client
3.0 (2020), but practically unreliable. Encrypted folders are read-only in
the web UI, cannot be shared, and must be created empty from a client app.
Community reports: sync errors, metadata corruption, disappearing files.
**Recommendation: use Cryptomator instead** if at-rest encryption is needed.

**Virtual File System (VFS):** Fully supported on Windows, supported on macOS
(separate `nextcloud-vfs` cask, macOS >= 12). **Rudimentary on Linux** --
appends `.nextcloud` suffix to placeholder files, no file manager integration.
VFS does not combine with selective sync (all remote files appear as
placeholders).

**File versioning:** Built-in server-side versioning with staggered retention.
Browsable in web UI. Versions never consume more than 50% of remaining free
space. Without delta sync, every version is a full file copy.

**Selective sync:** Folder-level in desktop client (check/uncheck top-level
folders). File pattern exclusions via Ignored Files Editor (glob patterns in
`sync-exclude.lst`). `nextcloudcmd` supports `--path`, `--exclude`, and
`--unsyncedfolders` for finer control.

**Ansible installability:** Official `nextcloud.admin` Ansible collection on
Galaxy (modules for `occ` commands, app management, user management; roles
for install and backup). Docker AIO has a manual Docker Compose method
designed for automation (template `.env` + `latest.yml`, deploy via
`community.docker.docker_compose_v2`). Client: PPA on Ubuntu
(`ppa:nextcloud-devs/client`), Homebrew cask on macOS.

**Server maintenance:** Cannot skip major versions (must step 30 -> 31 -> 32
etc.). PHP version requirements change between major versions. AIO simplifies
this significantly (containerized PHP, managed upgrades). No downgrade path --
always back up before upgrading. Two major releases/year, each supported ~1
year.

**Added value beyond sync:** Web UI for remote file access, file sharing
links, CalDAV calendar, CardDAV contacts, Nextcloud Office (Collabora),
Nextcloud Talk (video calls), Deck (kanban), Notes, 400+ app ecosystem,
mobile apps (iOS/Android). This is the main reason to choose Nextcloud over
pure-sync alternatives.

**Best for:** Users who want a self-hosted Google Workspace replacement that
also does file sync. Not optimal as a pure sync engine due to the lack of
delta sync and small-file performance limitations.

---

#### 5. Seafile

Self-hosted cloud sync. Community Edition is AGPL-3.0. Server written in C
(much lighter than Nextcloud).

**Architecture:** Client-server. Docker is the recommended deployment
(`seafileltd/seafile-mc`). Stack: Seafile server + MariaDB + Redis (v13+
replaced memcached) + Caddy for TLS. Desktop clients for Linux (AppImage --
primary since 9.0.7; also Flatpak on Flathub), macOS (`brew install --cask
seafile-client`). CLI client (`seaf-cli`) available on Linux only (AppImage).

**Server requirements:** 2 cores, 2 GB RAM for Community Edition. Runs
comfortably on a Raspberry Pi or low-end VPS. SSD recommended. Creates 3
MariaDB databases (ccnet-db, seafile-db, seahub-db). Pro Edition is free for
up to 3 users.

**Sync performance: block-level delta sync.** This is Seafile's defining
feature. Files are stored as blocks using **Content-Defined Chunking (CDC)**.
Block boundaries are determined by data content (rolling hash), so insertions
don't shift all boundaries. Only changed blocks are transferred. Benchmarks:
11 GB folder synced in 6 minutes at 30% server CPU (vs. Nextcloud at 80% for
equivalent workload). LAN downloads: ~100 MB/s on Gigabit Ethernet. A USENIX
FAST '18 paper found CDC-based sync 2-8x faster than rsync-based approaches,
supporting 30-50% more concurrent clients. Deduplication: identical blocks
(same content hash) stored only once across files, versions, and libraries.

**Conflict resolution:** First-to-server-wins, rename-the-loser. Conflicts
renamed to `<file> (SFConflict <email> <timestamp>).<ext>`. No merge support
(explicitly will not be added per developers). Known issue: identical-content
conflicts are not auto-resolved. A locked file blocks the entire library.

**Client-side encryption ("encrypted libraries"):** AES-256-CBC with
two-layer key scheme. File key (random 32 bytes) encrypted with
password-derived key (PBKDF2-SHA256, 1000 iterations; newer versions offer
Argon2id). Encryption is **per-library** -- can mix encrypted and unencrypted
libraries. Server operator cannot read encrypted data (password never stored
server-side). **Caveat:** file/directory names and sizes are NOT encrypted
(metadata leaks). Web browser access decrypts server-side (password
transmitted to server). True client-side encryption only with desktop/SeaDrive
clients.

**File versioning:** Block-based storage means versions only store changed
blocks (storage-efficient). Per-library configurable retention via
`keep_days`. Library snapshots ("time machine") allow restoring files,
folders, or entire libraries to any point. **Must run garbage collection
manually** to reclaim space (CE requires stopping server during GC; Pro
supports online GC). Without GC, storage can balloon significantly (community
report: 5 TB disk for 600 GB active data).

**Selective sync:** Per-library sync (choose which libraries sync to each
machine). Sub-folder sync available but places sub-folders at sync root (not
in original tree structure). File pattern exclusion via `seafile-ignore.txt`
(glob patterns, one per line) at library root. Caveat: ignore rules only
prevent upload from client; web uploads bypass them.

**Ansible installability:** Official Docker images are template-friendly
(`.env` + YAML compose files). Community Ansible role:
`netzwirt/ansible-seafile`. Server: template `.env`/`seafile-server.yml`,
deploy via `community.docker.docker_compose_v2`, add cron for weekly GC.
Client (Linux): download AppImage, rename CLI to `seaf-cli`, configure via
`seaf-cli init/start/sync`. Client (macOS): `community.general.homebrew_cask`
-- no CLI on macOS, GUI config only.

**Known issues:** macOS client crashes reported on Ventura/Monterey (v9.0.4).
Linux CLI AppImage may require X server (headless issue). No official ARM
Docker images. Recommended soft limit of ~100k files per library. Client
v9.0.7 had a download speed regression (100 MB/s -> 10-30 MB/s).

**Best for:** Pure file sync with block-level delta efficiency, client-side
encryption, and low server resource usage. Clear winner over Nextcloud for
sync performance.

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
| **Delta sync** | Block-based | rsync rolling checksum | No (whole file) | No (whole file) | Block-level CDC | BitTorrent blocks |
| **Conflict handling** | Rename conflict | Interactive/auto | Keep both + flags | Rename conflict | Rename conflict | Keep newest |
| **At-rest encryption** | Untrusted device | No | crypt overlay | Unreliable E2EE | AES-256/library | AES-128 |
| **File versioning** | 4 strategies | No (backup pref) | No (backup-dir) | Staggered (full copies) | Block-level (efficient) | Basic |
| **Selective sync** | `.stignore` | `path`/`ignore` | `--filter` | Folder-level + VFS | Per-library + ignore | Per-folder |
| **Web UI** | Yes (admin) | No | No | Yes (full platform) | Yes (file mgmt) | Yes (basic) |
| **apt installable** | Yes (official repo) | Yes | Yes | Client: PPA | Client: AppImage | No |
| **brew installable** | Yes | Yes | Yes | Yes (cask) | Yes (cask) | Yes (cask) |
| **Server min spec** | N/A | N/A | N/A | 2 core / 4 GB | 2 core / 2 GB | N/A |
| **Resource usage** | Moderate-high | Very low | Low | Server: moderate | Server: low | Low-moderate |
| **NAT traversal** | Built-in | None (needs SSH) | N/A | N/A (client-server) | N/A (client-server) | Built-in |
| **Setup complexity** | Low-medium | Low (+ cron) | Medium | Medium (AIO Docker) | Medium (Docker) | Low |
| **Ansible collection** | No (community roles) | No | No | Yes (official) | No (community role) | No |
| **Beyond sync** | No | No | No | Calendar, contacts, office, talk, apps | No | No |

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

#### Sync role: Syncthing (P2P)

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

#### Sync role: Seafile server (Docker)

```yaml
# shared/roles/seafile-server/tasks/main.yml
- name: Create Seafile data directory
  ansible.builtin.file:
    path: "{{ seafile_data_dir }}"
    state: directory
    mode: "0755"
  become: true

- name: Template Seafile .env
  ansible.builtin.template:
    src: seafile.env.j2
    dest: "{{ seafile_data_dir }}/.env"
    mode: "0600"
  become: true

- name: Template Seafile Docker Compose
  ansible.builtin.template:
    src: seafile-server.yml.j2
    dest: "{{ seafile_data_dir }}/seafile-server.yml"
  become: true

- name: Deploy Seafile stack
  community.docker.docker_compose_v2:
    project_src: "{{ seafile_data_dir }}"
    files: [seafile-server.yml]
    state: present
  become: true

- name: Schedule weekly garbage collection
  ansible.builtin.cron:
    name: seafile-gc
    weekday: "0"
    hour: "3"
    minute: "0"
    job: >-
      docker exec seafile /scripts/gc.sh >> /var/log/seafile-gc.log 2>&1
  become: true

# shared/roles/seafile-server/defaults/main.yml
seafile_data_dir: /opt/seafile
seafile_version: "13.0-latest"
seafile_hostname: "seafile.example.com"
seafile_admin_email: ""
seafile_admin_password: ""  # no_log: true in task
seafile_keep_days: 90
```

#### Sync role: Seafile client

```yaml
# shared/roles/seafile-client/tasks/debian.yml
- name: Download Seafile client AppImage
  ansible.builtin.get_url:
    url: "{{ seafile_client_appimage_url }}"
    dest: /usr/local/bin/seafile-appimage
    mode: "0755"
  become: true

# shared/roles/seafile-client/tasks/darwin.yml
- name: Install Seafile client (macOS)
  community.general.homebrew_cask:
    name: seafile-client
    state: present
```

#### Sync role: Nextcloud server (Docker AIO)

```yaml
# shared/roles/nextcloud-server/tasks/main.yml
- name: Create Nextcloud AIO directory
  ansible.builtin.file:
    path: "{{ nextcloud_data_dir }}"
    state: directory
    mode: "0755"
  become: true

- name: Template AIO environment config
  ansible.builtin.template:
    src: nextcloud-aio.conf.j2
    dest: "{{ nextcloud_data_dir }}/sample.conf"
    mode: "0600"
  become: true

- name: Deploy Nextcloud AIO stack
  community.docker.docker_compose_v2:
    project_src: "{{ nextcloud_data_dir }}"
    files: [latest.yml]
    state: present
  become: true

# shared/roles/nextcloud-server/defaults/main.yml
nextcloud_data_dir: /opt/nextcloud-aio
nextcloud_hostname: "nextcloud.example.com"

# shared/roles/nextcloud-client/tasks/debian.yml
- name: Add Nextcloud client PPA
  ansible.builtin.apt_repository:
    repo: "ppa:nextcloud-devs/client"
    filename: nextcloud-client
    state: present
  become: true

- name: Install Nextcloud desktop client
  ansible.builtin.apt:
    name: nextcloud-desktop
    state: present
  become: true

# shared/roles/nextcloud-client/tasks/darwin.yml
- name: Install Nextcloud client (macOS)
  community.general.homebrew_cask:
    name: nextcloud
    state: present
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

### For ongoing sync (Part B)

The right tool depends on whether you want a server or not, and whether you
need features beyond pure file sync.

#### P2P path (no server): Syncthing

Best for real-time sync without infrastructure:

- Zero server to maintain
- Works behind NAT out of the box (relay, UPnP, discovery)
- Continuous real-time sync (daemon)
- Staggered file versioning for accidental deletion recovery
- Strong selective sync via `.stignore`
- FOSS, actively maintained, large community
- Installable via apt and brew (Ansible-friendly)

Main tradeoff: higher resource usage than on-demand tools. Tunable for typical
user folder volumes.

#### P2P path (no server, on-demand): Unison

Best if you prefer explicit sync triggers over always-on daemon:

- Near-zero resource usage (no background process)
- Best-in-class conflict resolution (interactive + auto modes)
- True rsync-like rolling-checksum delta transfer
- Profile-based config is clean and templatable
- Requires SSH access (pair with Tailscale for NAT traversal)
- No file versioning (layer restic or similar for backups)

#### Server path (pure sync): Seafile

Best if you have a server available and want optimal sync performance:

- **Block-level delta sync (CDC)** -- only changed blocks transferred, 2-8x
  faster than rsync-based approaches (USENIX FAST '18)
- Deduplication across files and versions (storage-efficient)
- Native client-side encryption (AES-256-CBC per library)
- Very low server requirements (2 cores, 2 GB RAM)
- Docker deployment with Caddy for TLS
- Block-based versioning (storage-efficient, per-library configurable)
- Web UI for remote file access without VPN
- Pro Edition free for up to 3 users

Main tradeoffs: no macOS CLI client (GUI only), recommended ~100k files per
library, must run manual garbage collection, metadata not encrypted in
encrypted libraries. Conflict resolution is rename-only (no merge).

#### Server path (platform): Nextcloud

Best if you want sync **plus** a self-hosted Google Workspace replacement:

- CalDAV calendar + CardDAV contacts (replaces Google/Apple services)
- Nextcloud Office (collaborative editing via Collabora)
- Nextcloud Talk (video calls, chat)
- File sharing links (send files without third-party services)
- Mobile apps (iOS/Android)
- 400+ app ecosystem, Deck (kanban), Notes, AI assistant
- Web UI for remote file access from any browser
- Official Ansible collection (`nextcloud.admin`)
- Docker AIO simplifies deployment and upgrades

Main tradeoffs: **no delta sync** (entire files re-uploaded on change),
architecturally slow with many small files, heavier server requirements
(4 GB+ RAM recommended), upgrade treadmill (cannot skip major versions),
E2EE is unreliable (use Cryptomator instead), VFS rudimentary on Linux.

#### Hybrid options

**Seafile + rclone:** Seafile for real-time sync between workstations, rclone
for periodic encrypted offsite backups to cloud (B2, S3, crypt-wrapped Google
Drive).

**Syncthing + Nextcloud:** Syncthing for P2P file sync (better performance),
Nextcloud for calendar/contacts/office/sharing only (disable Nextcloud file
sync). This avoids Nextcloud's sync performance issues while keeping its
groupware value.

**Seafile + Nextcloud (separate roles):** Seafile for file sync, Nextcloud
for groupware. More infrastructure, but each tool does what it's best at.

### What to avoid

| Tool | Why |
|------|-----|
| SparkleShare | Git-based storage is wrong for large binary files |
| Resilio Sync | Proprietary, vendor-dependent |
| macOS Migration Assistant | No Linux support, no scriptability |
| ansible.builtin.copy | Never for bulk data migration |
| Nextcloud E2EE | Unreliable -- use Cryptomator if encryption needed |
| ownCloud | Fragmented (Infinite Scale rewrite), community shrinking |

### Decision matrix summary

| Need | Tool | Why |
|------|------|-----|
| One-time migration | rsync | Resume, delta, metadata, Ansible-native |
| Ongoing sync (P2P, always-on) | Syncthing | NAT traversal, versioning, zero infra |
| Ongoing sync (P2P, on-demand) | Unison | Lightweight, best conflict resolution, SSH |
| Ongoing sync (server, pure sync) | Seafile | Block-level delta, encryption, low resources |
| Ongoing sync (server, platform) | Nextcloud | Calendar, contacts, office, sharing, mobile |
| Offsite backup | rclone + crypt | 40+ backends, client-side encryption |
| Initial LAN seed | tar+ssh | Avoids file-list overhead for first bulk copy |
| **Code repo working trees** | **Unison (branch-aware)** | **Uncommitted work, branch isolation, wake trigger** |

**Code sync note:** Code repositories need special handling — general file
sync tools break `.git/` internals or garble working trees across branches
(see [syncthing-git-repos.md](syncthing-git-repos.md)). The branch-aware
Unison design in [unison-code-sync.md](unison-code-sync.md) is the primary
mechanism for transferring working state between machines. Forgejo/git remotes
handle committed history and CI only.

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
   -name '*.sync-conflict-*'` to surface conflicts. For Seafile: `find
   ~/Documents -name '*SFConflict*'`. For Unison: interactive mode handles
   conflicts at sync time.

7. **GPG key idempotency.** Follow the repo's pattern for apt repo keys:
   guard download+dearmor with `ansible.builtin.stat`, set `filename:` on
   `apt_repository`. Applies to Syncthing and Nextcloud PPA.

8. **Seafile garbage collection.** Community Edition requires stopping the
   server during GC. Schedule weekly via cron during low-usage hours. Set
   `keep_days` in `seafile.conf` to prevent unbounded version growth.

9. **Seafile library sizing.** Keep libraries under ~100k files. Organize
   user folders as separate libraries (Documents, Pictures, Music, etc.)
   rather than one monolithic library.

10. **Nextcloud E2EE.** Do not use Nextcloud's built-in E2EE -- it is
    unreliable. If at-rest encryption is needed, use Cryptomator vaults that
    sync as regular files through Nextcloud or Seafile's encrypted libraries.

11. **Nextcloud server maintenance.** Cannot skip major versions. Docker AIO
    handles sequential upgrades. Back up before every upgrade (no downgrade
    path). Two major releases per year.

12. **Seafile no macOS CLI.** The `seaf-cli` is Linux-only. macOS clients
    require GUI configuration -- not fully automatable via Ansible.

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

### Nextcloud
- [Nextcloud desktop client (GitHub)](https://github.com/nextcloud/desktop)
- [Nextcloud AIO (GitHub)](https://github.com/nextcloud/all-in-one)
- [Nextcloud Ansible collection](https://github.com/nextcloud/ansible-collection-nextcloud-admin)
- [Nextcloud system requirements](https://docs.nextcloud.com/server/stable/admin_manual/installation/system_requirements.html)
- [nextcloudcmd documentation](https://docs.nextcloud.com/server/stable/admin_manual/desktop/commandline.html)
- [Nextcloud E2EE user manual](https://docs.nextcloud.com/server/latest/user_manual/en/files/using_e2ee.html)
- [Nextcloud macOS VFS docs](https://docs.nextcloud.com/server/latest/user_manual/en/desktop/macosvfs.html)
- [Nextcloud conflicts documentation](https://docs.nextcloud.com/desktop/3.3/conflicts.html)
- [Nextcloud version control](https://docs.nextcloud.com/server/latest/user_manual/en/files/version_control.html)
- [Nextcloud upgrade docs](https://docs.nextcloud.com/server/stable/admin_manual/maintenance/upgrade.html)

### Seafile
- [Seafile GitHub repository](https://github.com/haiwen/seafile)
- [Seafile Docker (GitHub)](https://github.com/haiwen/seafile-docker)
- [Seafile system requirements](https://haiwen.github.io/seafile-admin-docs/12.0/setup/system_requirements/)
- [Seafile Docker CE setup](https://manual.seafile.com/latest/setup/setup_ce_by_docker/)
- [Seafile security features](https://manual.seafile.com/latest/administration/security_features/)
- [How encrypted libraries work](https://github.com/haiwen/seadroid/wiki/How-does-an-encrypted-library-work%3F)
- [Encrypted libraries info leak (issue #350)](https://github.com/haiwen/seafile/issues/350)
- [Seafile file conflicts](https://help.seafile.com/syncing_client/file_conflicts/)
- [Seafile GC documentation](https://haiwen.github.io/seafile-admin-docs/12.0/administration/seafile_gc/)
- [Seafile excluding files](https://help.seafile.com/syncing_client/excluding_files/)
- [USENIX FAST '18 paper on delta sync](https://www.usenix.org/system/files/conference/fast18/fast18-xiao.pdf)
- [Seafile vs Nextcloud comparison (sesamedisk.com)](https://sesamedisk.com/self-hosted-cloud-storage-nextcloud-seafile-owncloud/)
- [XDA: Switched from Nextcloud to Seafile](https://www.xda-developers.com/completely-uprooted-nextcloud-server-switched-seafile-instead/)

### Ansible
- [ansible.posix.synchronize module](https://docs.ansible.com/projects/ansible/latest/collections/ansible/posix/synchronize_module.html)
- [ansible.builtin.copy module](https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/copy_module.html)
- [Ansible copy vs synchronize (christopherburg.com)](https://www.christopherburg.com/blog/ansible-copy-versus-synchronize/)

### macOS Migration Assistant
- [Apple Support: Migration Assistant](https://support.apple.com/en-us/102613)
- [What Migration Assistant transfers (mactakeawaydata.com)](https://mactakeawaydata.com/what-does-migration-assistant-transfer/)

### Lifecycle

| Phase | Date | Commit | Notes |
|-------|------|--------|-------|
| Active | 2026-02-26 | f14b1e7 | Initial creation |
