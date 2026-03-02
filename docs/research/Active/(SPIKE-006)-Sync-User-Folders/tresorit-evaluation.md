# Tresorit evaluation for cross-platform file sync

**Date:** 2026-02-25
**Context:** Evaluated as a candidate for Part B (ongoing sync) of the
sync-user-folders research. Tresorit is a proprietary, zero-knowledge
E2E-encrypted cloud storage and sync service, now owned by Swiss Post.

---

## 1. Delta sync

**Tresorit does NOT support block-level (delta) sync.** Any modification to a
file requires the entire file to be re-encrypted and re-uploaded. This is a
fundamental architectural choice -- Tresorit attributes it to their encryption
design, though the ETH Zurich researchers note that zero-knowledge encryption
and block-level sync are not inherently incompatible (Seafile, for example,
does both).

Impact: Editing a single byte in a 500 MB file triggers a full 500 MB upload.
This is a significant bandwidth and time penalty for large files that change
frequently (databases, disk images, PST archives, large spreadsheets).

Competitors with block-level sync: Dropbox, OneDrive, pCloud, Seafile,
Syncthing, Resilio Sync.

Sources:
- https://support.tresorit.com/hc/en-us/articles/360005460033-The-basics-of-synchronization
- https://www.cloudwards.net/block-level-file-copying/

---

## 2. Linux client quality

### Distribution format

Tresorit provides three packaging options for Linux:

- **`.run` universal installer** -- the recommended method. Runs as user (no
  root required). Installs to `~/.local/share/tresorit/`.
- **`.deb`** -- for Debian/Ubuntu/Mint.
- **`.rpm`** -- for Fedora/RHEL/SUSE.

There is no AppImage, Flatpak, or Snap package.

### Supported distributions

Ubuntu 14+, Mint 17+, Debian 7.8+, Fedora, Arch, Gentoo, SUSE, CentOS.
Minimum supported version as of 2025-02-17: 3.5.1239.4340.

### Self-updating binary problem

Tresorit's Linux client auto-updates itself within the user's home directory
(`~/.local/share/tresorit/`). It also sometimes updates its downloadable blob
without release notes. This creates serious problems for Linux packaging:

- **AUR (Arch) package was orphaned** because the maintainer could not solve
  persistent checksum validation failures. Tresorit modifies released binaries,
  breaking sha512sum verification. The workaround had to be applied "practically
  always," which the maintainer called "not workable."
- The `check_signature.sh` script was removed from Tresorit's servers, breaking
  the PKGBUILD signature verification.
- Tresorit themselves advise against system-level installation (`/usr`, `/opt`).

### Tresorit Drive NOT available on Linux

Tresorit Drive (virtual filesystem / cloud-only file access without
downloading) is available on Windows and macOS only. Linux users must sync
files locally or use the CLI. This is a significant feature gap.

### Three executables

The installer provides:
- `tresorit` -- GUI client
- `tresorit-cli` -- command-line interface
- `tresorit-daemon` -- background daemon (used by both GUI and CLI)

### Real-world Linux reports

- One user running Tresorit on 9 Linux machines + 1 Windows PC reported a
  "patchy" experience: weeks of smooth operation punctuated by glitches. On one
  occasion, all Tresorit Drive files vanished.
- A November 2025 blog post (insanityworks.org) reported the Linux app as "rock
  solid" after 2 months of daily use syncing ~400 GB across multiple folders.
- Files containing special characters (e.g., `|`) will not sync. Tresorit is
  aware of this and has not fixed it over several years.

### Status

Tresorit for Linux exited beta in July 2025. It is actively maintained with
regular changelogs.

Sources:
- https://support.tresorit.com/hc/en-us/articles/216114157-Tresorit-for-Linux-FAQ
- https://support.tresorit.com/hc/en-us/articles/215858608-Changelogs-Linux
- https://aur.archlinux.org/packages/tresorit
- https://www.insanityworks.org/randomtangent/2025/11/1/using-tresorit-to-sync-files-on-linux
- https://www.trustpilot.com/review/www.tresorit.com

---

## 3. macOS client quality

### Current version

3.5.3376.4650 (released 2025-09-10). Regular updates with changelogs.

### Finder integration

Tresorit Drive integrates with macOS Finder for cloud-only file access. Recent
releases fixed icon badge display issues and improved drag-and-drop (holding
Option now copies instead of moves).

### Known macOS issues

- **App freezing:** Freezes often, sometimes freezing the entire Mac. Maxing
  out storage triggers freezes shortly after launch.
- **Sync failures with special characters:** Files containing `|` and similar
  characters will not sync (same as Linux).
- **Context menu unreliable:** Share link creation via context menu is "hit or
  miss."
- **No macOS tag support:** Tags are not preserved when syncing between Macs.
- **Third-party integration gaps:** Less ecosystem support than Dropbox/Google
  Drive due to smaller market share.

### Positive aspects

- Familiar folder structure in Finder.
- Cloud-only access via Tresorit Drive (unlike Linux).
- Regular updates addressing bugs.
- Overall Capterra rating: 4.8/5 (130 reviews), though Mac-specific complaints
  are present.

Sources:
- https://support.tresorit.com/hc/en-us/articles/216468567-Changelogs-macOS
- https://www.capterra.com/p/150689/Tresorit/reviews/

---

## 4. Device limits

| Plan | Max connected devices |
|------|----------------------|
| Basic (free) | 2 |
| Personal | 10 |
| Professional | 10 |
| Business | Per-policy (admin-controlled) |

Web access is available on any device without counting against the limit
(read/download/upload only, no sync or editing).

Sources:
- https://support.tresorit.com/hc/en-us/articles/229250267-Access-your-files-across-devices
- https://support.tresorit.com/hc/en-us/articles/227327447-Basic-plan-features-and-limits

---

## 5. Storage limits

| Plan | Storage | Max file size |
|------|---------|--------------|
| Basic (free) | 3 GB | 500 MB |
| Personal | 1 TB | Not specified (large) |
| Professional | 4 TB | Not specified (large) |
| Business Essential | 1 TB/user | Not specified |
| Business Advanced | 2 TB/user | Not specified |
| Enterprise | Custom | Custom |

Basic plan additional limits:
- 3 active tresors (main folders) at once.
- 10 active share links at once, max 250 MB per link.
- 10 file versions retained.

Note: Some third-party reviews claim 5 GB free, but Tresorit's own
documentation confirms 3 GB for the Basic plan.

Sources:
- https://support.tresorit.com/hc/en-us/articles/227327447-Basic-plan-features-and-limits
- https://tresorit.com/pricing

---

## 6. Conflict handling

**Strategy: preserve both versions (no silent overwrite).**

When a file is modified on two devices simultaneously:
- The first version to reach the server wins the canonical path.
- The conflicting version is saved as
  `<filename> (user@email.com's conflict).<ext>`.
- Manual resolution required (no merge support).

### Editing Badge (proactive conflict prevention)

Users can mark a file as "being edited" for 20 minutes, 1 hour, 3 hours, or
24 hours. Other tresor members see this badge and are warned before opening.
If they edit anyway, a conflict file is still created.

### Comparison

Similar to Syncthing, Nextcloud, and Seafile (all use rename-the-loser). No
interactive merge like Unison. No automatic resolution policies like rclone
bisync's `--conflict-resolve newer`.

Sources:
- https://support.tresorit.com/hc/en-us/articles/216114327-What-is-a-conflict-file
- https://support.tresorit.com/hc/en-us/articles/360007675820-Avoid-conflict-files-with-an-Editing-Badge

---

## 7. File versioning

| Plan | Versions retained |
|------|------------------|
| Basic (free) | 10 |
| Personal | 100 |
| Professional | 100 |

Access via: right-click file -> "See versions" -> download any previous version.

Without block-level delta sync, every version is a full copy of the file (same
as Nextcloud, worse than Seafile which stores only changed blocks).

Sources:
- https://support.tresorit.com/hc/en-us/articles/227327447-Basic-plan-features-and-limits
- https://cms.tresorit.com/blog/keep-file-versions-file-versioning-tresorit-pro-and-business

---

## 8. LAN sync capability

**Tresorit does NOT support LAN sync.** All synchronization goes through
Tresorit's cloud servers. There is no peer-to-peer or local network discovery.

This means two machines on the same LAN transferring a large file will:
1. Upload the full file from machine A to Tresorit's servers.
2. Download the full file from Tresorit's servers to machine B.

Combined with the lack of delta sync, this makes Tresorit particularly
inefficient for large-file workflows on a local network compared to Syncthing
(LAN discovery + block-level delta) or Unison (direct SSH + rolling checksum
delta).

Tresorit does support NAS/network drive sync targets, but this is still
cloud-mediated (sync a cloud tresor to a local NAS path), not direct
device-to-device.

Sources:
- https://support.tresorit.com/hc/en-us/articles/360005460033-The-basics-of-synchronization
- https://support.tresorit.com/hc/en-us/articles/115003636713-NAS-syncing-in-Tresorit

---

## 9. Encryption details

### End-to-end encryption (E2EE)

All encryption and decryption happens client-side. Files are encrypted before
upload. At no point are encryption keys or unencrypted files visible to
Tresorit's servers or staff.

### Algorithms

| Purpose | Algorithm |
|---------|-----------|
| File encryption | AES-256 (AES-GCM authenticated, or AES-CFB + SHA2 HMAC) |
| Key exchange | RSA-4096 with OAEP padding (RFC 2437) |
| Key derivation | scrypt + PBKDF2 |
| Hashing | SHA-512 (no SHA-1 or MD5) |
| Profile encryption | AES-256-CFB (same mode as PGP) |

Each file gets its own unique encryption key. Each tresor has a "group key
file" (GKF) that grants cryptographic access to members.

### Zero-knowledge

- Login uses a zero-knowledge challenge-response protocol. The server never
  sees the password or derived key.
- Tresorit staff cannot access file contents, file names, or encryption keys.
- All encrypted data is cryptographically authenticated (HMAC or AEAD) to
  prevent tampering.

### Security audits

| Auditor | Date | Scope | Result |
|---------|------|-------|--------|
| Ernst & Young | Historical | Penetration testing + code review | Confirmed zero-knowledge claims |
| ETH Zurich (Hofmann & Truong) | 2024 | E2EE protocol analysis of 5 providers | Tresorit "mostly unaffected" -- best of the 5 |
| TUV Rheinland | Ongoing | ISO 27001:2022 certification | Certified |
| Independent (annual from 2025) | 2025 | Full pentest (E2EE, web, mobile, desktop) | 1 medium-severity server-side race condition (not affecting E2EE) |

### ETH Zurich findings (October 2024)

The paper "End-to-End Encrypted Cloud Storage in the Wild: A Broken Ecosystem"
examined Sync, pCloud, Icedrive, Seafile, and Tresorit. Four of five providers
had severe vulnerabilities. Tresorit was the exception:

> "Tresorit's design is mostly unaffected by our attacks due to a comparably
> more thoughtful design and an appropriate choice of cryptographic primitives."

Remaining issues (minor):
- Public key authentication relies on server-controlled certificates. A
  malicious server could substitute keys to access shared files.
- No out-of-band public key verification (planned for 2025 roadmap).

### Jurisdiction

Swiss law. Not subject to US CLOUD Act. Swiss Post (owner) is a Swiss
government entity, which some privacy advocates view as a concern (government
ownership) while others view as a benefit (Swiss privacy protections).

### Encryption whitepaper

Full technical details: https://cdn.tresorit.com/202208011608/tresorit-encryption-whitepaper.pdf

Sources:
- https://tresorit.com/features/zero-knowledge-encryption
- https://tresorit.com/security
- https://tresorit.com/blog/independent-security-test-eth-zurich-puts-tresorits-e2ee-cloud-solution-to-the-test
- https://www.bleepingcomputer.com/news/security/severe-flaws-in-e2ee-cloud-storage-platforms-used-by-millions/
- https://tresorit.com/blog/tresorits-security-validated-again-by-independent-third-party-auditor-2025-pentest-results

---

## 10. Known issues, dealbreakers, and Linux user complaints

### Dealbreaker-tier issues

1. **No delta sync.** Every file change triggers a full re-upload. For large
   files that change frequently, this is a severe bandwidth and time penalty.
2. **No LAN sync.** All traffic goes through Tresorit's cloud. Two machines on
   the same desk must round-trip through Switzerland.
3. **Tresorit Drive not available on Linux.** Cloud-only file access (without
   downloading everything) is Windows/macOS only.
4. **Closed source.** Cannot audit the client. Must trust Tresorit's claims and
   third-party audits.

### Significant issues

5. **Special character filenames break sync.** Files with `|` and similar
   characters will not sync. Known for years, unfixed.
6. **Self-updating binary breaks packaging.** Tresorit modifies released
   binaries, breaking checksums. The Arch AUR package was orphaned. Installing
   via system package managers is "not a good solution" per Tresorit themselves.
7. **No macOS tag preservation.** Tags are lost when syncing between Macs.
8. **macOS freezing.** Multiple reports of the app freezing, sometimes freezing
   the entire Mac.
9. **Customer support responsiveness.** Multiple reports of tickets being
   ignored for months. One user reported 6 months of ignored tickets while
   paying "several hundred dollars a year."

### Minor issues

10. **Closed-source + government ownership.** Swiss Post (a Swiss government
    entity) is the sole owner. Some privacy advocates are uncomfortable with
    this combination.
11. **No interactive merge.** Conflict resolution is rename-only, no diff/merge
    tooling.
12. **Version history costs full storage.** Without delta sync, every version is
    a full copy.

---

## 11. Cost of paid plans

All prices are per month, billed annually (approx. 20% discount vs. monthly):

### Individual plans

| Plan | Storage | Price (monthly billing) | Price (annual billing) |
|------|---------|------------------------|----------------------|
| Basic | 3 GB | Free | Free |
| Personal | 1 TB | ~$13.99/mo | ~$11/mo |
| Professional | 4 TB | ~$33.99/mo | ~$27/mo |

### Business plans (minimum 3 users)

| Plan | Storage | Price per user/month (annual) |
|------|---------|------------------------------|
| Business Essential | 1 TB/user | ~$18/user/mo |
| Business Advanced | 2 TB/user | ~$24/user/mo |
| Enterprise (50+ users) | Custom | Contact sales |

Email encryption add-on: $7.50/user/month on top of any business plan.

**Price comparison:** Tresorit is expensive relative to storage provided.
Dropbox Plus offers 2 TB for ~$10/mo. Google One offers 2 TB for ~$10/mo.
pCloud offers 2 TB lifetime for ~$400. However, none of these match Tresorit's
zero-knowledge E2EE.

Sources:
- https://tresorit.com/pricing
- https://tresorit.com/pricing/business
- https://www.cloudwards.net/tresorit-review/

---

## 12. Ownership

### Founded

2011 in Budapest, Hungary by Istvan Lam, Szilveszter Szebeni, and Gyorgy
Szilagyi. Backed by European VCs including 3TS Capital Partners, PortfoLion,
Euroventures, and DayOne Capital.

### Acquired by Swiss Post

**July 6, 2021:** Swiss Post (Die Schweizerische Post / La Poste Suisse)
acquired a majority stake. Purchase price undisclosed. Swiss Post is now the
**sole shareholder**.

Tresorit retained its brand, management team (founders remained as
shareholders initially), and operates as an independent entity within the
Swiss Post group. Headquarters in Zurich; offices also in Munich and Budapest
(~100 employees).

### Current CEO

Istvan Hartung (appointed June 2023). Co-founder Istvan Lam moved to Director
of Corporate Development and Board member.

### Jurisdiction implications

Swiss Post is owned by the Swiss Confederation (federal government). Tresorit
operates under Swiss data protection law (FADP/nDSG). Not subject to EU GDPR
directly but voluntarily complies. Not subject to US CLOUD Act.

Sources:
- https://cms.tresorit.com/blog/tresorits-majority-of-stakes-acquired-by-swiss-post
- https://techcrunch.com/2021/07/08/swiss-post-acquires-e2e-encrypted-cloud-services-provider-tresorit/
- https://en.wikipedia.org/wiki/Tresorit

---

## 13. API/CLI availability

### CLI (Linux)

Tresorit provides `tresorit-cli`, a command-line interface that communicates
with `tresorit-daemon`. Available commands:

| Command | Purpose |
|---------|---------|
| `login` | Authenticate with email + password + 2FA |
| `list tresors` | List main folders with sync status and local paths |
| `sync --start <tresor> --path <path>` | Start syncing a tresor to a local path |
| `sync --stop <tresor>` | Stop syncing a tresor |
| `drive --enable` / `--disable` | Enable/disable Tresorit Drive (requires libfuse2) |
| `transfers` | Show current sync status, files remaining, errors |
| `status` | Report on daemon, Drive, and session state |
| `proxy` | Configure proxy settings |

The CLI is suitable for headless servers and automation. The daemon persists
settings across restarts.

### Public REST API

Tresorit does not appear to offer a documented public REST API for third-party
integrations. The CLI is the primary programmatic interface. There is no SDK
for building custom applications on top of Tresorit storage.

### ZeroKit (discontinued)

Tresorit previously offered ZeroKit, a developer SDK for adding E2EE to
third-party applications. It has been discontinued and the GitHub repositories
are archived.

### GitHub presence

https://github.com/tresorit -- mostly archived utility repositories and the
defunct ZeroKit project. No active public SDK or API client libraries.

Sources:
- https://support.tresorit.com/hc/en-us/articles/360009330614-Using-Tresorit-CLI-for-Linux
- https://github.com/tresorit

---

## Assessment for this project

### Fit for sync-user-folders use case

Tresorit is being evaluated for ongoing sync of user data folders (Documents,
Pictures, Music, Videos) across 2-3 Linux/macOS workstations.

| Criterion | Tresorit | Assessment |
|-----------|----------|------------|
| Cross-platform Linux + macOS | Yes (but Linux is second-class) | Acceptable with caveats |
| Delta sync | No (whole file) | **Disqualifying for large files** |
| LAN sync | No | **Significant penalty** |
| Conflict handling | Rename-the-loser | Adequate |
| E2EE / zero-knowledge | Yes (best-in-class) | Excellent |
| FOSS | No (closed source) | Negative |
| Self-hosted option | No | Negative |
| CLI / automation | Basic CLI, no API | Minimal |
| Ansible installable | Manual .run installer | Poor |
| Cost for 1 TB | ~$14/mo | Expensive |
| Device limit | 10 (paid) | Adequate |
| File versioning | 100 versions (paid) | Good |
| Tresorit Drive on Linux | No | Negative |

### Verdict

**Not recommended as primary sync tool for this project.** The lack of delta
sync and LAN sync are disqualifying for the intended use case (syncing
potentially large user data folders across local and remote machines). The
closed-source nature and lack of a proper Linux packaging story (self-updating
binary, orphaned AUR package) conflict with this project's preferences.

Tresorit's strongest value proposition -- zero-knowledge E2EE audited by ETH
Zurich -- is genuinely best-in-class, but this project can achieve equivalent
security through other means:

- **Syncthing** with untrusted-device encryption for cloud relay.
- **Seafile** with encrypted libraries for self-hosted cloud sync.
- **rclone crypt** overlay for encrypting data on any cloud backend.
- **Cryptomator** vaults on top of any cloud storage.

If the primary need were secure cloud backup (not bidirectional sync), Tresorit
would merit stronger consideration. For ongoing bidirectional sync of user
folders, Syncthing, Unison, or Seafile remain superior choices.
