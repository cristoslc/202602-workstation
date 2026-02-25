# MEGAsync (MEGA cloud sync client) evaluation

**Date:** 2026-02-25
**Context:** Evaluated as a potential cross-platform (Linux + macOS) cloud-based file
sync solution for user data folders, as part of the
[sync-user-folders](README.md) research.

---

## 1. Delta sync

**MEGAsync does NOT support block-level (delta) sync.** When any part of a file
changes, the entire file is re-uploaded to MEGA's cloud servers.

This is a significant limitation for large files (VMs, databases, disk images,
large archives). Competitors that do support block-level sync include:

- **Dropbox** -- block-level delta sync (proprietary)
- **Seafile** -- Content-Defined Chunking (CDC), block-level
- **Syncthing** -- 128 KiB - 16 MiB block-based sync
- **pCloud** -- block-level sync

MEGAsync does use **chunked upload** for reliability with large files, but this
is not delta sync -- the entire file content is still transmitted.

**Verdict:** Dealbreaker for workflows involving large files that change
incrementally.

---

## 2. Linux client quality

### Package availability

MEGA maintains an official apt repository at `https://mega.nz/linux/repo/`
with builds for:

- **Debian** (stable releases, not development)
- **Ubuntu** (stable releases, not development)
- **Linux Mint** (Debian-based builds)
- **Fedora** (RPM)
- **openSUSE** (RPM)
- **Arch Linux** (AUR)
- **elementary OS**

Installation requires adding the GPG key and repository manually:

```bash
curl -fsSL https://mega.nz/linux/repo/Debian_12/Release.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/mega.nz.gpg

echo "deb [arch=amd64,arm64 signed-by=/etc/apt/keyrings/mega.nz.gpg] \
  https://mega.nz/linux/repo/Debian_12/ ./" \
  | sudo tee /etc/apt/sources.list.d/mega.nz.list > /dev/null
```

Available packages: `megasync` (GUI), `megacmd` (CLI), plus file manager
integrations for Nautilus, Nemo, Dolphin, and Thunar.

### NOT available via

- **Snap:** No snap package found.
- **Flatpak/Flathub:** The unofficial Flatpak was **archived and marked EOL on
  2025-07-02**. The Flathub repo (`flathub/nz.mega.MEGAsync`) is read-only.
  MEGA has not published an official replacement Flatpak.

### Development activity

The MEGAsync GitHub repository (`meganz/MEGAsync`) is actively maintained:

- Version 6.1.1.0 released 2026-01-16
- Version 6.1.0.2 released 2025-12-24
- Commits visible through late 2025 / early 2026
- 1.8k stars, 294 forks
- RPM Fusion rebuilt for Fedora 44 on 2026-02-02
- Client code is open source (C++, Qt)

### Known Linux issues (2024-2025)

1. **VPN/proxy conflicts:** Login failures when system proxy settings are
   modified by a VPN. Workaround: manually configure proxy in MEGAsync settings.

2. **Flatpak instability:** Freezing when adding sync folders. The Flatpak
   version was chronically behind the native package. Now archived entirely.

3. **`.megaignore` modification bug (2025-05):** On cross-platform syncs
   (Windows <-> Linux), the `.megaignore` file is silently modified on the
   Linux side -- the `+sync:.megaignore` entry gets commented out and a symlink
   negation rule is appended.

4. **Dependency conflicts on Mint:** `libmediainfo0v5` version mismatches from
   third-party repositories.

5. **Arch Linux build failures:** Periodic breakage from library updates.

6. **Poor customer support:** Multiple reports of weeks-long response times or
   no response at all.

**Verdict:** The native `.deb` package is reasonably well-maintained and
actively updated. Avoid the Flatpak (dead) and Snap (nonexistent). Arch users
may hit periodic build issues. The Linux client is functional but has a history
of rough edges.

---

## 3. macOS client quality

### Apple Silicon support

- Native Apple Silicon (arm64) support since MEGAsync v4.7.2.
- Fully compatible with M1/M2/M3 as of v4.9.5+.
- Latest tracked version on "Does It ARM": v5.4.1.

### Known macOS issues

1. **Code signature crashes:** Recurring `EXC_BAD_ACCESS (Code Signature
   Invalid)` / SIGKILL on launch across multiple versions (v4.11.0, v5.x).
   Reinstalling does not always fix.

2. **Launch failures on Big Sur:** v5.4 reported unable to open on macOS Big
   Sur with Intel chips.

3. **Crash loop:** Reports of systematic crashes ~5 minutes after start,
   consuming high CPU and memory, with sync never completing.

4. **Abort trap failures:** v5.5.0 (2024-10) failing to launch on older macOS
   versions.

**Verdict:** The macOS client has a long history of stability problems spanning
both Intel and Apple Silicon, across multiple macOS versions. Quality is
inconsistent -- some users report it working fine, others cannot get it to
launch at all. Not confidence-inspiring for a critical sync tool.

---

## 4. Device limits

**No device limits on any plan.** MEGA does not restrict the number of devices
that can use an account. You can install MEGAsync on all personal machines
(Linux, macOS, Windows, iOS, Android) without additional fees or per-device
caps.

This applies to both free and paid tiers.

---

## 5. Storage and transfer limits

### Storage

| Plan | Storage | Monthly price (approx.) | Annual price (approx.) |
|------|---------|------------------------|----------------------|
| **Free** | 20 GB (15 GB permanent + 5 GB temporary bonus) | Free | Free |
| **Pro I** | 2 TB | ~EUR 9.99/mo | ~EUR 99.99/yr |
| **Pro II** | 8 TB | ~EUR 19.99/mo | ~EUR 199.99/yr |
| **Pro III** | 16 TB | ~EUR 29.99/mo | ~EUR 299.99/yr |
| **Pro Flexi** | Starting 3 TB (pay-per-use) | Variable | Variable |
| **Business** | Flexible | EUR 10/user/mo (min 3 users) | N/A |

Note on free tier: MEGA formerly offered 50 GB free. This was reduced to 20 GB
(with 35 GB of the original 50 GB being a 30-day bonus that expires). Effective
permanent free storage is **15 GB**. Additional temporary bonuses are available
through "achievements" (installing apps, inviting friends), but these expire.

### Transfer quota

**Free accounts:**

- Upload: unlimited (does not count against quota).
- Download: ~5 GB per 6-hour rolling window, enforced by IP address.
- Exact limits are dynamic and vary by server load, time of day, ISP, and
  country. MEGA does not publish exact numbers.
- Once exhausted, downloads are blocked with "quota exceeded" until the window
  rolls over.
- Quota tracking is per-IP, not per-account. Logging out does not reset it.

**Paid accounts:**

- Pro I: 2 TB/month transfer.
- Pro II: 8 TB/month transfer (matches storage).
- Pro III: 16 TB/month transfer (matches storage).
- Pro Flexi / Business: no set transfer quota.
- Paid accounts receive prioritized bandwidth allocation.

Transfer quotas reset on the first of each calendar month at 00:00 UTC.

**Verdict:** Free tier is workable for light sync of small document folders but
the opaque, IP-based download throttling is a real friction point. Paid tiers
are competitively priced per TB but the transfer quota model (especially on
free) is a significant usability concern.

---

## 6. Conflict handling

MEGAsync uses a "Stalled Issues System" for conflict detection and resolution.

### Automatic ("smart mode") resolution

- **Name conflicts:** Remove duplicated files, merge same-name folders, rename
  to avoid collisions.
- **Local/remote conflicts:** Choose the most recently modified version.

### Manual resolution

When automatic resolution is insufficient, conflicts are presented to the user
as "stalled issues" requiring manual intervention via the MEGAsync GUI.

### Known issues with conflict handling

- The system is desktop-GUI-dependent. No CLI conflict resolution via MEGAcmd.
- No three-way merge or interactive merge tool integration.
- Fundamentally a "rename the loser" strategy, similar to Syncthing and
  Seafile, but less transparent than Unison's interactive mode.

**Verdict:** Adequate for casual use. Worse than Unison (interactive merge) but
comparable to Syncthing/Seafile (rename conflict files). The GUI dependency
makes it unsuitable for headless/automated workflows.

---

## 7. File versioning

MEGAsync supports file versioning, which is **enabled by default** and can be
disabled in settings (option added in v3.5.8).

### How it works

- When a file changes, the previous version is stored in MEGA's cloud.
- Previous versions count against storage quota.
- Versions are accessible via the MEGA web interface.

### Known issues

- **No global version management:** To delete old versions, you must browse
  into each folder individually in the web UI and delete versions per-file.
  There is no global "delete all old versions" or "limit version retention"
  setting.
- **Backup versioning mismatch:** The backup feature stores file versions that
  are not accessible to the user (web app shows 0 bytes, client shows nonzero).
- **mega-put creates duplicates:** When file versioning is disabled, uploading
  via `mega-put` (MEGAcmd) creates duplicate copies instead of overwriting.
- **No deduplication across backups:** Identical files in separate backup sets
  are uploaded again (no server-side dedup).
- **Folder renames trigger full re-upload:** Renaming a synced folder causes
  all files within it to be re-uploaded from scratch.

**Verdict:** Basic file versioning exists but the management tools are
primitive. No per-folder retention policies, no global cleanup, no
storage-efficient block-based versioning (unlike Seafile). Versioning can
silently consume large amounts of storage quota.

---

## 8. LAN sync capability

**MEGAsync does NOT support LAN sync.** There is no peer-to-peer, local
network, or direct device-to-device transfer mechanism.

All data synced by MEGAsync must traverse MEGA's cloud servers, even when two
devices are on the same local network. This means:

- Doubled bandwidth usage (upload from device A to cloud, download from cloud
  to device B) for every change.
- Transfer speed limited by internet upload bandwidth, not LAN speed.
- Sync latency includes round-trip to MEGA servers.

Services that do support LAN sync or P2P transfer:

| Service | LAN sync |
|---------|----------|
| Dropbox | Yes (LAN Sync feature) |
| Syncthing | Yes (local discovery + direct P2P) |
| Resilio Sync | Yes (BitTorrent protocol, P2P) |
| Seafile | No (client-server only) |
| Nextcloud | No (client-server only) |
| **MEGAsync** | **No** |

**Verdict:** Significant limitation for multi-machine setups on the same
network. All sync traffic goes through the cloud.

---

## 9. E2E encryption details

### Architecture

MEGA implements **client-side, zero-knowledge encryption**. Data is encrypted
on the user's device before upload and decrypted only after download. MEGA
(the company) does not have access to user encryption keys or file contents.

### Technical details

- **Symmetric encryption:** AES-128 (variant called AES-CCM* -- deviates from
  RFC 3610; effectively Encrypt-and-MAC rather than Encrypt-then-MAC).
- **Asymmetric encryption:** RSA for key exchange when sharing files between
  users.
- **Key derivation:** Master key derived from user password, strengthened with
  entropy from mouse movements and keystroke timings.
- **Authentication:** Server sends encrypted RSA private key; client decrypts
  with password-derived key. Server never receives the password.
- **Sharing:** File/folder keys encrypted with recipient's RSA public key
  before transmission.
- **2FA:** TOTP-based (standard, compatible with Google Authenticator etc.).
- **Recovery:** If you lose your password AND recovery key, your data is
  permanently inaccessible. MEGA cannot reset passwords.
- **Infrastructure:** MEGA owns and operates its own server infrastructure in
  Europe, New Zealand, and Canada. No third-party VPS.
- **Open source:** All client-side code is published on GitHub for public
  inspection.

### 2022 vulnerability (ETH Zurich)

In June 2022, ETH Zurich researchers published five attacks against MEGA's
encryption:

1. **RSA key recovery attack** -- extract user's RSA private key after
   observing ~512 login attempts.
2. **Plaintext recovery attack** -- decrypt file contents using recovered RSA
   key.
3. **Framing attack** -- insert attacker-controlled files that pass client
   authenticity checks.
4. Two additional integrity-related attacks.

**Exploitability:** Very high bar. Requires either:
- Control of MEGA's server infrastructure, OR
- Successful MITM on the user's TLS connection to MEGA.

And the user must have logged in at least 512 times (session resumptions do
not count). MEGA states they are not aware of any accounts compromised via
these vulnerabilities.

**Root causes:**

- AES-ECB used for key ciphertexts (no integrity protection).
- Non-standard RSA padding (not RSA-OAEP).
- Key reuse across cryptographic contexts.

**MEGA's fix:** Patched the RSA key recovery and plaintext recovery attacks in
all clients (June 2022). Mitigated the framing attack. Did NOT address the
underlying systemic issues (key reuse, lack of integrity checks). The
researchers recommended a complete cryptographic redesign, which MEGA has not
undertaken (would require re-encrypting 1000+ petabytes of data).

**Current assessment:** The most critical attack vectors are patched, but the
cryptographic architecture has known structural weaknesses. MEGA's encryption
is significantly better than no encryption (Google Drive, OneDrive, etc.) and
better than Nextcloud's broken E2EE, but it is no longer considered
theoretically zero-knowledge after the 2022 disclosure. The fixes are
pragmatic patches rather than the full redesign the researchers recommended.

**Verdict:** Real client-side encryption that works in practice. Meaningfully
more private than mainstream cloud providers. But the 2022 audit revealed
structural weaknesses that MEGA chose to patch rather than redesign. If you
need encryption you can fully trust, use a tool with audited, modern
cryptography (Cryptomator, rclone crypt, Seafile encrypted libraries) on top
of any storage backend.

---

## 10. Known issues, dealbreakers, and Linux user complaints

### Potential dealbreakers

1. **No delta sync.** Whole-file re-upload on every change. Unacceptable for
   large files.
2. **No LAN sync.** All traffic through cloud servers. Doubled bandwidth for
   same-network machines.
3. **Transfer quotas.** Free tier throttled to ~5 GB/6 hours. Opaque,
   IP-based enforcement.
4. **Flatpak removed.** Only native packages remain. Distros without official
   MEGA repos have no supported install path.
5. **macOS stability.** Recurring crash-on-launch and code-signing issues
   across multiple versions and macOS releases.
6. **Cryptographic architecture concerns.** 2022 vulnerabilities patched but
   underlying design not redesigned.
7. **Customer support.** Multiple reports of weeks-long or no response.

### Linux-specific complaints (from forums and GitHub issues)

- VPN/proxy conflicts causing login failures.
- `.megaignore` silently modified on Linux in cross-platform syncs.
- Dependency hell on Linux Mint with third-party repos.
- Arch Linux build breakage after library updates.
- Flatpak version was chronically buggy before being EOL'd entirely.
- Folder renames trigger full re-upload of all contained files.
- Duplicate file uploads after folder renames (not deduplicated).
- No headless/CLI conflict resolution (requires GUI).

### What works well

- Unlimited devices on all plans.
- Generous free storage (20 GB, effectively 15 GB permanent).
- Real client-side encryption (despite structural concerns).
- Active open-source development.
- Native apt repository with file-manager integrations.
- MEGAcmd provides a capable CLI/scripting layer.
- Competitively priced paid plans.

---

## 11. Cost of paid plans

Prices as of early 2026 (vary by region/currency):

| Plan | Storage | Transfer/mo | Monthly | Annual (per month) |
|------|---------|-------------|---------|-------------------|
| **Free** | 20 GB* | ~5 GB/6hr | Free | Free |
| **Pro I** | 2 TB | 2 TB | EUR 9.99 | EUR 8.33 (EUR 99.99/yr) |
| **Pro II** | 8 TB | 8 TB | EUR 19.99 | ~EUR 16.66 |
| **Pro III** | 16 TB | 16 TB | EUR 29.99 | ~EUR 24.99 |
| **Pro Flexi** | 3 TB+ | Pay-per-use | Variable | Variable |
| **Business** | Flexible | Unlimited | EUR 10/user (min 3) | N/A |

*Free tier: 15 GB permanent + 5 GB temporary bonus. Additional temporary
storage via "achievements" program (expires).

Annual billing saves ~2 months (pay for 10, get 12).

MEGA also includes a VPN with paid plans (or purchasable separately at
~EUR 5.75/month).

No lifetime plans available.

---

## 12. API/CLI availability for automation

### MEGAcmd (official CLI)

MEGAcmd is MEGA's official command-line interface. It is a separate package
from MEGAsync (the GUI sync client).

**Architecture:** Client-server model.

- `mega-cmd-server`: persistent background process that maintains the MEGA SDK
  session.
- `mega-cmd` / `MEGAcmdShell`: interactive shell with tab completion.
- Individual command binaries (e.g., `mega-ls`, `mega-get`, `mega-put`,
  `mega-sync`, `mega-backup`): non-interactive scriptable commands.

**Platforms:** Linux (`/usr/bin/mega-*`), macOS (requires adding install path
to `$PATH`), Windows.

**Key capabilities:**

- File operations: `mega-ls`, `mega-get`, `mega-put`, `mega-mkdir`, `mega-rm`,
  `mega-cp`, `mega-mv`, `mega-find`, `mega-export`
- Sync: `mega-sync` (add/remove/list synced folders)
- Backup: `mega-backup` (configure scheduled backups)
- Sharing: `mega-share`, `mega-export` (public links)
- WebDAV server: `mega-webdav` (expose MEGA folders as WebDAV)
- Session management: `mega-login`, `mega-logout`, `mega-whoami`, `mega-session`
- 80+ commands total

**Scriptability:** Commands can be chained in bash scripts. Supports regex
patterns in remote paths. Example:

```bash
mega-find --pattern="*.mp4" /Videos | while read f; do
  mega-export -a "$f"
done
```

**Installation:** `sudo apt install megacmd` (from MEGA's apt repo).

### MEGA C++ SDK

Official SDK on GitHub (`meganz/sdk`). C++ library for building custom
integrations. This is what MEGAsync and MEGAcmd are built on.

### Third-party libraries

- **megajs** (npm): Unofficial JavaScript/Node.js SDK. Handles MEGA encryption,
  file operations, and networking. v1.3.9, 34 dependents.
- **MEGAcmd4J**: Open-source Java wrapper around MEGAcmd CLI.
- **go-mega**: Go library used by rclone's MEGA backend.

### rclone MEGA backend

rclone has a built-in MEGA backend using the `go-mega` library. Supports:

- `rclone copy`, `rclone sync`, `rclone mount` (FUSE)
- Can mount MEGA as a local filesystem
- Performance caveat: significantly slower than native MEGAsync (1-2 MB/s vs
  30 MB/s reported by users)
- Session management differs from native client (stateless, may cause login
  churn)
- WebDAV-via-MEGAcmd workaround available but buggy (whitespace in paths,
  crashes)

### MEGA S4 (S3-compatible object storage)

MEGA also offers S4, an S3-compatible object storage service, which works with
rclone and standard S3 tooling. This is separate from the sync service and
targeted at different use cases.

**Verdict:** MEGAcmd provides a solid CLI for scripting and automation.
Combined with the apt-installable package, it is Ansible-friendly for
installation. However, configuration automation (setting up sync folders,
managing conflicts) still requires GUI interaction for many operations.

---

## Overall assessment for this repo's use case

### Context

This repo provisions 2-3 workstations (Linux + macOS) and needs:

1. One-time migration of user data folders
2. Ongoing sync of Documents, Pictures, Music, Videos, Downloads

### MEGAsync fit

| Requirement | MEGAsync | Assessment |
|-------------|----------|------------|
| Cross-platform (Linux + macOS) | Yes | OK but macOS stability concerns |
| Delta sync | No (whole file) | **Poor** -- bandwidth waste |
| LAN sync | No | **Poor** -- all traffic through cloud |
| Conflict resolution | GUI-only stalled issues | **Mediocre** -- no CLI, no merge |
| File versioning | Basic, quota-consuming | **Mediocre** |
| E2E encryption | Real but structurally flawed | **Acceptable** with caveats |
| CLI/automation | MEGAcmd, good | **Good** |
| Free tier usable | 15-20 GB, throttled transfers | **Marginal** for ongoing sync |
| Device limits | Unlimited | **Good** |
| Ansible-friendly install | apt repo + brew cask | **Good** |

### Recommendation

**MEGAsync is not recommended as the primary sync solution for this repo.**

The lack of delta sync and LAN sync are the primary disqualifiers. For a
workstation setup syncing user data folders across 2-3 machines -- where
machines are often on the same LAN and files can be large -- these are
fundamental architectural mismatches.

MEGAsync could serve as:

- **Offsite encrypted backup** of critical folders (leveraging the E2E
  encryption), if you accept the transfer quota constraints and whole-file
  re-upload costs.
- **Quick file sharing** between machines when direct SSH/Syncthing is not
  available.

For the primary sync role, the tools already evaluated in the parent research
document (Syncthing, Unison, Seafile) are substantially better fits:

| | MEGAsync | Syncthing | Unison | Seafile |
|---|---|---|---|---|
| Delta sync | No | Block-based | rsync rolling | Block-level CDC |
| LAN sync | No | Yes (P2P) | Yes (SSH/LAN) | No (server) |
| No cloud dependency | No | Yes | Yes | Self-hosted |
| Conflict handling | GUI rename | Rename | Interactive merge | Rename |
| Encryption | Built-in E2E | TLS + untrusted device | SSH | Per-library AES |
| Free | 15 GB cloud | Unlimited (P2P) | Unlimited (P2P) | Self-hosted |

---

## Sources

### MEGAsync general
- [MEGAsync GitHub repository](https://github.com/meganz/MEGAsync)
- [MEGAsync releases](https://github.com/meganz/MEGAsync/releases)
- [MEGA Desktop App download](https://mega.io/desktop)
- [Cloudwards MEGA review 2026](https://www.cloudwards.net/review/mega/)
- [CyberInsider MEGA review 2026](https://cyberinsider.com/cloud-storage/reviews/mega/)
- [cloudstorageinfo.org MEGA review 2025](https://cloudstorageinfo.org/mega-cloud-storage-review)

### Delta sync
- [Cloudwards: block-level file copying](https://www.cloudwards.net/block-level-file-copying/)
- [Cloudwards: best cloud storage with sync](https://www.cloudwards.net/best-cloud-storage-with-sync/)

### Linux packaging
- [MEGA Linux apt repo sources](https://github.com/Danrancan/megasync-linux-debian-sources-list)
- [how2shout: install MEGAsync on Linux](https://www.how2shout.com/how-to/megasync-client-how-to-install-it-on-linux-to-sync-files.html)
- [It's FOSS: install MEGA on Linux](https://itsfoss.com/install-mega-cloud-storage-linux/)
- [Flathub MEGAsync repo (archived)](https://github.com/flathub/nz.mega.MEGAsync)
- [GitHub issue #993: Flatpak distribution request](https://github.com/meganz/MEGAsync/issues/993)

### macOS
- [GitHub issue #634: Apple Silicon support](https://github.com/meganz/MEGAsync/issues/634)
- [Does It ARM: MEGAsync](https://doesitarm.com/app/megasync)
- [GitHub issue #875: macOS crash](https://github.com/meganz/MEGAsync/issues/875)
- [GitHub issue #1007: macOS launch failure](https://github.com/meganz/MEGAsync/issues/1007)

### Encryption and security
- [MEGA Security White Paper (2020)](https://www.voilatranslate.com/wp-content/uploads/SecurityWhitepaper.pdf)
- [ETH Zurich: MEGA Malleable Encryption Goes Awry (2022)](https://mega-awry.io/)
- [ETH Zurich paper (ePrint)](https://eprint.iacr.org/2022/959.pdf)
- [BleepingComputer: MEGA fixes critical flaws](https://www.bleepingcomputer.com/news/security/mega-fixes-critical-flaws-that-allowed-the-decryption-of-user-data/)
- [Cloudwards: MEGA security flaw review](https://www.cloudwards.net/mega-security-flaw/)
- [MEGA security update (PR Newswire)](https://www.prnewswire.com/news-releases/mega-security-update-301571692.html)
- [Global Encryption Coalition: MEGA](https://www.globalencryption.org/2022/09/mega/)
- [GitHub webclient discussion #124: encryption verification](https://github.com/meganz/webclient/discussions/124)

### File versioning and conflicts
- [GitHub issue #138: versioning and folders](https://github.com/meganz/MEGAsync/issues/138)
- [GitHub issue #792: versioning in backups](https://github.com/meganz/MEGAsync/issues/792)
- [GitHub issue #1003: duplicate uploads](https://github.com/meganz/MEGAsync/issues/1003)
- [MEGAcmd issue #381: mega-put duplicates](https://github.com/meganz/MEGAcmd/issues/381)
- [DeepWiki: MEGAsync stalled issues system](https://deepwiki.com/meganz/MEGAsync/2.3-stalled-issues-system)

### Transfer quotas
- [Cloudwards: bypass MEGA download limit](https://www.cloudwards.net/bypass-mega-download-limit/)
- [megacloudstorage.net: free transfer quota](https://megacloudstorage.net/mega-cloud-storage/mega-cloud-english/what-is-the-free-transfer-quota-for-mega-cloud/)

### CLI and API
- [MEGAcmd GitHub repository](https://github.com/meganz/MEGAcmd)
- [MEGAcmd User Guide](https://github.com/meganz/MEGAcmd/blob/master/UserGuide.md)
- [DeepWiki: MEGAcmd overview](https://deepwiki.com/meganz/MEGAcmd/1-overview-and-introduction)
- [MEGA C++ SDK](https://github.com/meganz/sdk)
- [megajs npm package](https://www.npmjs.com/package/megajs)
- [rclone MEGA backend](https://rclone.org/mega/)
- [rclone forum: MEGA performance issues](https://forum.rclone.org/t/performance-issues-mounting-mega/39240)

### Linux issues
- [GitHub issue #1075: .megaignore modified on Linux](https://github.com/meganz/MEGAsync/issues/1075)
- [Linux Mint Forums: login issue](https://forums.linuxmint.com/viewtopic.php?t=435868)
- [Linux Mint Forums: freezing](https://forums.linuxmint.com/viewtopic.php?t=414219)
- [Linux Mint Forums: dependency issue](https://forums.linuxmint.com/viewtopic.php?t=409657)
- [Arch Linux Forums: build failure](https://bbs.archlinux.org/viewtopic.php?id=255357)
