# pCloud evaluation: cross-platform file sync for Linux and macOS

**Status:** Active
**Date:** 2026-02-25
**Scope:** Evaluate pCloud as a cross-platform file sync solution for use across
Linux and macOS workstations, covering sync technology, client quality,
encryption, pricing, and operational concerns.

---

## 1. Delta sync (block-level vs. whole-file)

pCloud supports **true block-level (delta) sync**. When a file is modified, only
the changed blocks are uploaded rather than the entire file. pCloud claims this
reduces bandwidth usage by up to 90% for large modified files.

Key details:

- pCloud uses **smaller chunk sizes** for file differencing than Dropbox, which
  makes it more efficient for files that undergo frequent small changes (e.g.,
  databases, VM images).
- Block-level sync applies to **all files**, including those in the encrypted
  Crypto folder. pCloud has confirmed to Cloudwards that "block-level sync
  applies to any file edited on the cloud, no matter how it's encrypted."
- Block-level sync works through the **desktop client only**. Web uploads do
  not benefit from delta sync.
- **rclone does not leverage pCloud's block-level sync API**. There is an open
  feature request (rclone/rclone#7896) for upload-only block-level sync
  support. rclone currently uses the HTTP REST API; a separate issue
  (rclone/rclone#8036) discusses switching to pCloud's binary protocol for
  better performance.
- In practice, uploads with the desktop client average 8-10 MB/s on a 100 Mbps
  connection. Web uploads are slower (2-5 MB/s).

**Verdict:** Delta sync is genuinely block-level and works well through the
desktop client. The rclone gap matters if you rely on CLI-based workflows.

Sources:
- [pCloud help: block-level sync](https://www.pcloud.com/help/drive-help-center/does-pcloud-support-block-level-sync)
- [Cloudwards: block-level file copying](https://www.cloudwards.net/block-level-file-copying/)
- [rclone issue #7896](https://github.com/rclone/rclone/issues/7896)
- [rclone issue #8036](https://github.com/rclone/rclone/issues/8036)

---

## 2. Linux client quality

### Package format

The Linux client is distributed **exclusively as an AppImage**. There is no
official `.deb`, `.rpm`, or Flatpak package. The AUR has a community-maintained
`pcloud-drive` package, but its maintainer has expressed frustration with the
AppImage packaging and offered to hand it off.

### Current version

Version **2.0.3** (released 2026-02-11) introduced a new UI, a Photos feature,
AppImage Launcher beta support, and "better desktop integration." The 1.14.x
series through 2025 focused on bug fixes and stability.

### System requirements

Ubuntu 18.04+, Linux Mint 19+, Fedora 28+, Arch Linux, Debian 10+, or
derivative distributions.

### How it works

The client mounts a FUSE-based virtual drive at `~/pCloudDrive`. Files in this
mount do not consume local disk space unless marked for offline access. A
separate sync feature lets you bidirectionally sync local folders with pCloud
folders.

### Known issues (significant)

1. **AppImage compatibility** — Fails to launch on multiple distributions
   including Rocky Linux, CentOS, some CachyOS builds, and Debian Buster.
   Ubuntu 22.04+ requires manually installing `libfuse2` (not installed by
   default since the move to libfuse3).

2. **FUSE permission problems** — Users on Ubuntu-based systems (Zorin, etc.)
   report that permissions become inconsistent after initial setup. Root is
   denied permissions on the FUSE mount. This is a recurring, unresolved
   complaint.

3. **CLI crashes with large copies** — `cp` or `rsync` to the pCloud drive via
   terminal causes core dumps when transferring large numbers of files. This bug
   has been reported for 5+ years and remains unresolved.

4. **Sync delay** — pCloud takes approximately 60 seconds before detecting
   modified files, then another ~60 seconds to reflect changes. Users coming
   from Dropbox (near-instant sync) find this jarring.

5. **No native package management** — AppImage-only distribution means no
   automatic updates via `apt`/`dnf`/`pacman`, no dependency resolution, and
   no integration with system package managers.

6. **High CPU usage** — Fixed in 1.14.17 specifically for VPN scenarios, but
   general high CPU usage during sync has been reported by multiple reviewers.

### Console client (headless / CLI)

pCloud provides an official console client (`pcloudcc`) at
github.com/pcloudcom/console-client. It mounts pCloud via FUSE on headless
servers without a GUI. However:

- The official repo appears **largely inactive**.
- Active forks exist: `sergeyklay/pcloud-console-client` (v3.0.0) and
  `lneely/pcloudcc-lneely` (packages for AUR and Nix, targets linux/amd64 and
  aarch64).
- Building from source requires CMake, Boost, libfuse-dev, libudev-dev, and
  other dependencies.
- There is **no way to check pending transfer status** before stopping the
  daemon. Stopping mid-transfer breaks pending uploads.
- EU region users must set `PCLOUD_REGION_EU=true` as an environment variable.

**Verdict:** The Linux client works but has real quality problems. AppImage-only
distribution is a pain point. The FUSE mount and sync delay issues are the most
operationally significant. The console client exists but is community-maintained
and rough around the edges.

Sources:
- [pCloud Linux release notes](https://www.pcloud.com/release-notes/linux.html)
- [AUR pcloud-drive](https://aur.archlinux.org/packages/pcloud-drive)
- [Linux Mint AppImage issue](https://github.com/linuxmint/cinnamon/issues/12495)
- [pcloudcom/console-client](https://github.com/pcloudcom/console-client)
- [lneely/pcloudcc-lneely](https://github.com/lneely/pcloudcc-lneely)

---

## 3. macOS client quality

### Current version

Version **4.0.7** (released 2026-02-04). The 4.0.x series added macOS Tahoe
26.0 support, a new Photos feature, and Intel Mac stability improvements.

### How it works

Installs a virtual drive that appears in Finder alongside local disks. Files
dragged into the virtual drive are uploaded in the background. The virtual drive
does not consume local SSD space unless files are marked for offline access.

### Expert assessments

- Cloudwards (2026): "Apps display a high degree of polish and attention to
  detail that's rarely seen." Noted higher-than-expected CPU usage during
  testing.
- Gizmodo (2026): Experience was "nothing short of excellent, especially in
  terms of accessibility, speed, and security." Lacks productivity apps (no
  document editing) and customer support response times are average.

### Known issues

1. **Sync delays** — Same ~60 second detection delay as Linux. Some users
   report conflicted file versions or files that never sync if the machine
   sleeps/shuts down before upload completes.
2. **CPU usage** — Higher than expected during active sync operations.
3. **No real-time collaboration** — No Google Docs-style editing. pCloud is
   storage-only.

**Verdict:** The macOS client is noticeably more polished than the Linux client.
Finder integration is well-regarded. The sync delay exists but is less
operationally painful on macOS where sleep/wake cycles are more predictable.

Sources:
- [pCloud macOS release notes](https://www.pcloud.com/release-notes/mac-os.html)
- [Cloudwards pCloud review](https://www.cloudwards.net/review/pcloud/)
- [Gizmodo pCloud review](https://gizmodo.com/best-cloud-storage/pcloud)

---

## 4. Device limits

**No device limits on any plan**, including the free tier. You can connect
unlimited devices across Windows, macOS, Linux, iOS, and Android.

Source:
- [pCloud pricing page](https://www.pcloud.com/cloud-storage-pricing-plans.html)

---

## 5. Storage limits

| Plan | Storage | Price |
|------|---------|-------|
| Free | 10 GB (5 GB base + 5 GB for completing onboarding tasks) | $0 |
| Premium (monthly) | 500 GB | $4.99/mo |
| Premium (annual) | 500 GB | $49.99/yr |
| Premium Plus (monthly) | 2 TB | $9.99/mo |
| Premium Plus (annual) | 2 TB | $99.99/yr |
| Lifetime 500 GB | 500 GB | $199 one-time |
| Lifetime 2 TB | 2 TB | $399 one-time (often discounted to ~$279) |
| Lifetime 10 TB | 10 TB | $1,190 one-time (often discounted to ~$799) |
| Family Lifetime 2 TB | 2 TB shared across up to 5 users | $595 one-time |
| Business | 1 TB per user (min 3 users) | $7.99/user/mo (annual) |
| Business Pro | Unlimited per user (min 3 users) | $19.98/user/mo |

**Download link traffic limits** (for content others download via shared links):
- Free: 50 GB/month
- Premium: 500 GB/month
- Premium Plus: 2 TB/month

No upload bandwidth limits or throttling on any plan.

Sources:
- [pCloud pricing](https://www.pcloud.com/cloud-storage-pricing-plans.html)
- [Cloudwards pCloud pricing guide](https://www.cloudwards.net/pcloud-pricing/)
- [Gizmodo pCloud pricing](https://gizmodo.com/best-cloud-storage/pcloud/pricing)

---

## 6. Conflict handling

pCloud's conflict resolution is **basic**. When the same file is modified on
multiple devices before sync completes:

- pCloud creates a **conflicted copy** with `(conflicted)` or `[conflicted]`
  appended to the filename.
- There is **no interactive merge/resolve UI**. You must manually compare and
  reconcile conflicted copies.
- In some reported cases, the **last-synced version silently wins** without
  creating a conflicted copy, suggesting conflict detection is not fully
  reliable.
- pCloud advises against syncing frequently-modified system files (`.pst`,
  `.ost`, `.git` directories, hidden files, browser data).

A third-party tool exists for managing conflicts:
[rcfa/pCloudSync-deconflict](https://github.com/rcfa/pCloudSync-deconflict)
(macOS-focused).

**Verdict:** Conflict handling is a weakness. If you edit the same file on two
machines without giving sync time to complete (remembering the ~60 second
detection delay), you risk silent data loss or orphaned conflicted copies with
no tooling to resolve them.

Sources:
- [pCloud help: conflicted files](https://www.pcloud.com/help/drive-help-center/what-type-of-files-are-not-recommended-if-i-use-sync-backup-or-uploads)
- [LibreOffice forum: conflicted meaning](https://ask.libreoffice.org/t/what-does-conflicted-mean-in-synced-file-name-pcloud/55327)
- [pCloudSync-deconflict](https://github.com/rcfa/pCloudSync-deconflict)

---

## 7. File versioning

| Plan | Default retention | With Extended File History add-on |
|------|-------------------|----------------------------------|
| Free | 15 days | Up to 365 days |
| Premium / Lifetime | 30 days | Up to 365 days |
| Business | 180 days | Up to 365 days |

Key details:

- **No limit on the number of versions** — only the time window matters.
- **Extended File History (EFH)** is a paid add-on. Pricing is not prominently
  listed but it extends retention to 365 days.
- EFH is **not retroactive**. If a file was deleted more than 30 days ago
  before EFH was activated, it cannot be recovered.
- **pCloud Rewind** lets you browse your entire account state at a specific
  point in time within the retention window and restore or download files.
- Versioning applies to file revisions, trash recovery, and Rewind.

**Verdict:** 30 days of versioning is adequate for most use cases. The
unlimited version count is a strength. EFH as an add-on is reasonable but the
non-retroactive limitation means you need to buy it proactively.

Sources:
- [pCloud file versioning](https://www.pcloud.com/features/file-versioning.html)
- [pCloud Extended File History blog post](https://blog.pcloud.com/introducing-extended-file-history/)

---

## 8. LAN sync

pCloud supports **peer-to-peer LAN sync**. When multiple devices running pCloud
are on the same local network, files transfer directly between devices without
routing through cloud servers.

- **Enabled by default** in pCloud Drive settings.
- Uses P2P discovery on the local network.
- Significantly faster than cloud-routed sync for local transfers.

**Verdict:** LAN sync is present and works. It is not as configurable as
Syncthing's relay/discovery system, but it covers the common case of two
machines on the same network.

Source:
- [pCloud help: LAN sync](https://www.pcloud.com/help/drive-help-center/what-is-lan-sync)

---

## 9. Encryption (pCloud Crypto)

### Standard encryption (all plans)

All files are encrypted with **AES 256-bit** on pCloud's servers and in transit
via **TLS/SSL**. However, pCloud holds the encryption keys. This is
server-side encryption only.

### pCloud Crypto (E2E / zero-knowledge)

pCloud Crypto provides **client-side, zero-knowledge encryption** for files
placed in a special "Crypto" folder:

- Files are encrypted locally on your device before upload.
- Uses **4096-bit RSA** for user private keys and **256-bit AES** for file and
  folder keys.
- The Crypto Pass (decryption password) is known only to you. pCloud cannot
  access encrypted files. If you lose the password, data is unrecoverable.
- Encrypted files can only be accessed through the desktop or mobile apps while
  online. They **cannot be saved locally or synced for offline access**.

### Is Crypto included? No.

pCloud Crypto is a **paid add-on** for individual plans:

| Billing | Price |
|---------|-------|
| Monthly | $4.99/mo |
| Annual | $49.99/yr ($3.99/mo effective) |
| Lifetime | $150 one-time |

Crypto is **included at no extra cost** with Business and Business Pro plans.

### Limitations and concerns

1. **Extra cost** — Competitors like Sync.com include zero-knowledge encryption
   by default at no additional charge.
2. **Crypto folder only** — E2E encryption applies only to files in the Crypto
   folder, not your entire drive.
3. **No offline access for encrypted files** — Encrypted files require an
   online connection to access.
4. **Closed source** — The encryption implementation is not open source. There
   is no way to independently verify the absence of backdoors.
5. **Crypto folder download limitation** — You can bulk-upload to the Crypto
   folder, but downloads must be done one file at a time (reported by users).

**Verdict:** pCloud Crypto is real client-side E2E encryption, but it is
limited in scope (one special folder), costs extra, and is closed-source. For a
workstation sync use case where you want everything encrypted, you would need to
put all synced content in the Crypto folder and accept the offline-access
limitation. Alternatively, layer your own encryption (e.g., gocryptfs, age) on
top of the standard pCloud sync.

Sources:
- [pCloud Crypto pricing](https://www.pcloud.com/help/android-help-center/how-much-does-pcloud-encryption-cost)
- [Cloudwards: what is pCloud Crypto](https://www.cloudwards.net/what-is-pcloud-crypto/)
- [CyberInsider pCloud review](https://cyberinsider.com/cloud-storage/reviews/pcloud/)

---

## 10. Known issues, dealbreakers, and Linux user complaints

### Potential dealbreakers

1. **Data breach reports** — Multiple users on Reddit and Trustpilot have
   reported seeing **other users' files** appear on their machines. pCloud has
   not issued an official statement. This is the most alarming complaint.

2. **File disappearance / corruption** — Users report files vanishing after
   edit/rename/move operations. One user lost "literally thousands of files"
   after years of use. A Linux Mint Forums user called switching from Dropbox
   to pCloud a "big mistake."

3. **60-second sync detection delay** — pCloud does not use filesystem event
   monitoring (inotify/fsevents) for immediate detection. There is an
   approximately 60-second polling interval before changes are detected,
   followed by another delay before the remote reflects changes. Combined with
   the weak conflict handling, this creates a real window for data loss if you
   work on multiple machines.

4. **Cross-region sharing restriction** — You cannot share folders with users
   whose data is stored in a different region (EU vs. US). This is a hard
   limitation.

5. **Account deletion without warning** — Reports of accounts being deleted
   due to copyright claims with no prior notice or appeal process.

6. **Customer support quality** — Described as slow to respond. Users report
   week-long waits for resolution of data-affecting issues.

### Significant operational concerns

7. **Speed degradation over time** — Lifetime plan users report upload and
   download speeds dropping over months of use.

8. **No pending transfer visibility** — The console client (`pcloudcc`) has no
   way to check whether transfers are still in progress before shutdown.
   Stopping the daemon mid-transfer breaks pending uploads.

9. **AppImage-only on Linux** — No system package manager integration, no auto
   updates, dependency issues (`libfuse2`), launch failures on multiple
   distros.

10. **Crypto folder bulk download limitation** — Cannot bulk-download encrypted
    files.

Sources:
- [Trustpilot pCloud reviews](https://www.trustpilot.com/review/pcloud.com)
- [Linux Mint Forums: pCloud concerns](https://forums.linuxmint.com/viewtopic.php?t=327445)
- [linux.org: pCloud permissions issues](https://www.linux.org/threads/pcloud-permissions-issues-no-consistency-at-all.43829/)
- [CloudStorageInfo: pCloud review after 9 years](https://cloudstorageinfo.org/pcloud-review)

---

## 11. Cost of paid plans (including lifetime deals)

### Individual subscription plans

| Plan | Monthly | Annual | Effective monthly (annual) |
|------|---------|--------|---------------------------|
| Premium (500 GB) | $4.99 | $49.99 | $4.17 |
| Premium Plus (2 TB) | $9.99 | $99.99 | $8.33 |

### Lifetime plans (one-time payment)

| Plan | Regular price | Typical sale price |
|------|---------------|-------------------|
| 500 GB | $199 | ~$149 |
| 1 TB | $435 | ~$199 |
| 2 TB | $399-$599 | ~$279 |
| 10 TB | $1,190-$1,890 | ~$799 |

### Add-ons

| Add-on | Monthly | Annual | Lifetime |
|--------|---------|--------|----------|
| pCloud Crypto | $4.99/mo | $49.99/yr | $150 one-time |
| Extended File History | — | — | Not prominently priced |

### Family plans

| Plan | Price |
|------|-------|
| Family 2 TB Lifetime (5 users) | $595 one-time |

### What "lifetime" means

pCloud defines lifetime as **99 years or the lifetime of the account holder,
whichever is shorter**. There is no guarantee if the company ceases operations.
The lifetime plan breaks even versus annual pricing in approximately 3-4 years.

pCloud has operated since 2013 (~13 years) and claims 22+ million users as of
2025. They own their own data center infrastructure (not renting from
AWS/GCP/Azure), which reduces operational cost pressure.

Sources:
- [pCloud pricing](https://www.pcloud.com/cloud-storage-pricing-plans.html)
- [pCloud lifetime page](https://www.pcloud.com/lifetime/)
- [Cloudwards lifetime analysis](https://www.cloudwards.net/pcloud-lifetime/)
- [pCloud help: lifetime definition](https://www.pcloud.com/help/general-help-center/what-is-pcloud-lifetime)

---

## 12. Jurisdiction

- **Legal entity:** pCloud AG, registered in **Baar, Switzerland**.
- **Engineering office:** Sofia, Bulgaria.
- **EU data center:** **Luxembourg**.
- **US data center:** **Dallas, Texas**.
- **Data region choice:** Users choose EU or US at signup. Data stays in the
  chosen region. You cannot share across regions.
- **Infrastructure:** pCloud owns its data center infrastructure. They do not
  use AWS, GCP, or Azure.
- **Compliance:** ISO 27001:2013 (Information Security), ISO 9001:2008 (Quality
  Management), GDPR compliant, SSAE 18 SOC 2 Type II.
- **Privacy law:** Swiss Federal Act on Data Protection (FADP). Switzerland is
  not an EU member but has an adequacy decision from the European Commission,
  meaning Swiss privacy protections are considered equivalent to GDPR.

**Verdict:** The Swiss jurisdiction is a genuine privacy advantage. Own
infrastructure (no cloud IaaS dependency) is a positive signal for both privacy
and operational longevity.

Sources:
- [pCloud data regions](https://www.pcloud.com/data-regions/)
- [pCloud certification](https://www.pcloud.com/company/certification.html)
- [Wikipedia: pCloud](https://en.wikipedia.org/wiki/PCloud)
- [Cloudwards: pCloud EU server](https://www.cloudwards.net/pcloud-eu-server/)

---

## 13. API / CLI availability

### Official REST API

Full HTTP REST API documented at [docs.pcloud.com](https://docs.pcloud.com/).
Also supports a **binary protocol** (documented at
docs.pcloud.com/protocols/binary_protocol/) which is faster but not widely
adopted by third-party tools.

### Console client (pcloudcc)

Official: [pcloudcom/console-client](https://github.com/pcloudcom/console-client)
(largely inactive). Active forks:

- [sergeyklay/pcloud-console-client](https://github.com/sergeyklay/pcloud-console-client)
  (v3.0.0, cleaner build)
- [lneely/pcloudcc-lneely](https://github.com/lneely/pcloudcc-lneely)
  (active, AUR and Nix packages, linux/amd64 + aarch64)

The console client supports FUSE mounting, daemonization, crypto folder access,
and systemd integration. It requires building from source (CMake + Boost +
libfuse + dependencies) unless using AUR/Nix packages.

### Python library

[pcloud on PyPI](https://pypi.org/project/pcloud/) — updated November 2025.
`pip install pcloud`.

### rclone integration

rclone has a first-class pCloud backend. Configuration via `rclone config`.
Supports:

- Upload/download/sync/copy/move
- MD5 + SHA1 checksums (US region) or SHA1 + SHA256 (EU region)
- Modification time preservation (requires re-upload)
- Trash management via `rclone cleanup`

rclone does **not** support pCloud's block-level sync or binary protocol. All
operations go through the HTTP REST API.

### Filesystem client (FUSE)

[pcloudcom/pfs](https://github.com/pcloudcom/pfs) — a standalone FUSE
filesystem client for pCloud. Separate from the console client and the GUI
application.

**Verdict:** API coverage is good. The REST API is well-documented. CLI options
exist but are community-maintained. rclone is the most practical CLI tool for
pCloud but lacks delta sync. For an Ansible-managed workstation, rclone is the
most automatable integration path.

Sources:
- [pCloud developer docs](https://docs.pcloud.com/)
- [rclone pCloud docs](https://rclone.org/pcloud/)
- [pcloud PyPI](https://pypi.org/project/pcloud/)
- [pcloudcom/pfs](https://github.com/pcloudcom/pfs)
- [pcloudcom/console-client](https://github.com/pcloudcom/console-client)

---

## Overall assessment

### Strengths

- True block-level delta sync
- Unlimited devices on all plans
- Swiss jurisdiction with own infrastructure
- LAN sync (P2P) enabled by default
- Lifetime pricing with good value proposition
- Polished macOS client with Finder integration
- Good rclone support for automation
- 30-day file versioning with unlimited version count

### Weaknesses

- Linux client: AppImage-only, FUSE permission bugs, CLI crashes, 60s sync
  delay
- Conflict handling: basic conflicted-copy approach, no merge UI, reports of
  silent overwrites
- pCloud Crypto: extra cost, limited to one folder, no offline access, closed
  source
- Alarming (unconfirmed but multiple) reports of data breaches and file loss
- Console client effectively community-maintained
- Cross-region sharing impossible
- Customer support reportedly slow

### Comparison to alternatives for this use case

For a cross-platform Linux + macOS workstation sync scenario (the context of
the sync-user-folders research):

| Criterion | pCloud | Syncthing | Unison |
|-----------|--------|-----------|--------|
| Delta sync | Block-level | Block-level | File-level |
| Linux client | AppImage, rough | Native, excellent | CLI, excellent |
| macOS client | Polished | Native, good | CLI, good |
| Conflict handling | Basic (conflicted copies) | Configurable per-folder | Interactive merge |
| LAN sync | Yes (P2P) | Yes (relay + discovery) | Direct (SSH/socket) |
| Cloud storage | Included | None (device-to-device) | None (device-to-device) |
| E2E encryption | Extra cost, Crypto folder only | TLS between devices | SSH transport |
| Offline access | Limited for Crypto files | Full (local copies) | Full (local copies) |
| CLI/automation | rclone, pcloudcc (rough) | syncthing CLI, REST API | Native CLI |
| Device limits | Unlimited | Unlimited | N/A (point-to-point) |
| Cost | $0-$1190+ | Free | Free |
| Data sovereignty | Swiss servers | Your devices only | Your devices only |

pCloud's value proposition is **cloud-hosted storage with decent sync** rather
than **best-in-class sync tooling**. If the primary need is keeping folders in
sync across 2-3 workstations with strong conflict handling, Syncthing or Unison
remain stronger choices. pCloud adds value if you also need cloud backup, web
access, mobile access, or sharing links — features that device-to-device tools
do not provide.
