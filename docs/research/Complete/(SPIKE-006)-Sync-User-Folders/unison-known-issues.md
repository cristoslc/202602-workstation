# Unison file synchronizer: known issues and real-world pain points

**Date:** 2026-02-24
**Scope:** Deep-dive on reliability, cross-platform gotchas, and operational pain
points of Unison (https://github.com/bcpierce00/unison) for ongoing bidirectional
sync of user folders (Documents, Pictures, Music, Videos) between 2-3 Linux + macOS
workstations.

**Current stable version:** 2.53.8 (released 2025-11-05)

---

## 1. macOS-specific issues

### 1.1 Sonoma / Sequoia / Ventura compatibility

No Sonoma- or Sequoia-specific breakage has been reported in Unison's issue tracker
or mailing lists as of February 2026. The 2.53.x binaries are properly signed,
avoiding Gatekeeper "damaged app" errors. However:

- **Quarantine flags:** Downloaded binaries may still need `xattr -cr Unison.app`
  to clear quarantine attributes on first launch.
- **Full Disk Access:** macOS privacy protections may prevent Unison from reading
  certain directories (Desktop, Documents, Downloads) unless the terminal emulator
  or Unison itself is granted Full Disk Access in System Settings > Privacy &
  Security.

### 1.2 Apple Silicon (ARM64)

Unison builds natively for ARM64 via Homebrew. No Rosetta needed. The Homebrew
formula (`brew install unison`) provides a universal build. No ARM64-specific bugs
have been reported in the Unison tracker itself (earlier "too many open files"
reports were from docker-sync/devspace wrappers, not Unison proper).

### 1.3 Homebrew packaging

Two install paths:

| Method | Command | Provides |
|--------|---------|----------|
| Formula | `brew install unison` | CLI binary only |
| Cask | `brew install --cask unison-app` | GUI app (lablgtk) |

The formula depends on `ocaml` as a build dependency. **As of February 2026,
Homebrew's `ocaml` formula is version 5.4.0.** This is problematic -- see
section 8 on OCaml 5.x risks. Homebrew also has `ocaml@4` (keg-only), but the
Unison formula does not use it by default.

The Homebrew cask installs a pre-built `.app` from the GitHub releases page, which
is compiled by the Unison project with OCaml 4.14.x. **The cask binary is safer
than a from-source Homebrew formula build** with respect to OCaml 5 issues.

### 1.4 GUI deprecation risk

The release notes for every 2.53.x version carry this warning:

> DEPRECATION MAY HAPPEN WITH LESS THAN TYPICAL NOTICE: lablgtk is difficult to
> use safely, and future maintenance is unclear. [...] it is possible that support
> for the unison GUI may end suddenly, on a particular platform, or on all
> platforms -- even in a micro release.

And specifically for macOS:

> MAINTENANCE WARNING: No one is contributing to verify that the Mac GUI continues
> to work -- so it might not.

**Practical impact:** Use the CLI (`unison -batch` or interactive text UI). Do not
depend on the GUI for any automated workflow.

### 1.5 Resource forks and .DS_Store

Unison has a `rsrc` preference to control resource fork synchronization:

- `rsrc = true` syncs resource forks. On non-HFS+ filesystems (ext4 on Linux),
  resource forks are stored as `._*` AppleDouble sidecar files.
- `rsrc = false` ignores resource forks entirely.

**Recommendation for Linux <-> macOS sync:** Set `rsrc = false` to avoid
polluting the Linux side with `._*` files, and add ignore rules:

```
rsrc = false
ignore = Name {.DS_Store}
ignore = Name {._*}
```

### 1.6 Case sensitivity (APFS vs ext4)

APFS is case-insensitive by default. ext4 is case-sensitive. Unison has an
`ignorecase` preference:

- `ignorecase = default` -- auto-detects based on platform. Treats filenames as
  case-insensitive if either host is macOS or Windows.
- `ignorecase = true` -- force case-insensitive.
- `ignorecase = false` -- force case-sensitive.

**Gotcha:** If you have two files on Linux whose names differ only in case (e.g.,
`README.md` and `Readme.md`), Unison will report an error and refuse to sync them
to the macOS side. There is no workaround other than renaming the files.

See also: [Issue #1054](https://github.com/bcpierce00/unison/issues/1054) --
Unison refuses to synchronize to a case-sensitive NTFS directory (analogous
issue).

---

## 2. Cross-platform sync issues (Linux <-> macOS)

### 2.1 Permissions mapping

Unison syncs Unix permissions via the `perms` preference. Default behavior syncs
the full permission bits. Cross-platform considerations:

- UID/GID numbers differ between machines. Unison syncs the numeric values but
  does **not** map usernames. If your UID is 1000 on Linux and 501 on macOS,
  files synced from Linux to macOS will have UID 1000 (which may map to a
  different user or nobody). **Workaround:** Use `owner = false` and
  `group = false` to skip ownership sync.
- `perms = 0` ignores permission changes entirely. Useful if permission
  differences between platforms cause spurious conflicts.

### 2.2 Timestamp precision

- ext4 supports nanosecond timestamps.
- APFS supports nanosecond timestamps.
- HFS+ supported only 1-second resolution (legacy, but still relevant if syncing
  with older macOS volumes or USB drives formatted HFS+).

Unison compares modification times to detect changes. The `fastcheck` preference
uses size + mtime for change detection (avoiding full content hashing). Precision
mismatches can cause:

- Spurious "changed" detection after initial sync if timestamps are truncated.
- Known issue with FAT32 (2-second resolution) and remounted volumes causing
  inode-number changes that defeat fastcheck.

**Mitigation:** Use `times = true` to propagate timestamps. For FAT32 targets,
use `fat = true`. For typical Linux <-> macOS sync over SSH, this is a
non-issue in practice.

**Known issue:** Directory timestamps may not match even when contents are
identical ([Issue #172](https://github.com/bcpierce00/unison/issues/172)).
The maintainers have stated this may never be fixed.

### 2.3 Symlink handling

- `links = true` (default on Unix) -- symlinks are synced as symlinks.
- `links = false` -- symlinks are ignored.
- `follow` preference -- dereferences symlinks and syncs the target content.

**Gotcha:** Using `follow` with `-repeat watch` (fsmonitor) causes crashes on
macOS ([Issue #79](https://github.com/bcpierce00/unison/issues/79)). Choose one
or the other.

### 2.4 Unicode normalization (NFC vs NFD)

macOS historically stored filenames in NFD (decomposed) form. Linux typically uses
NFC (composed). Unison has a `unicode` preference:

- `unicode = true` (default when one host is macOS) -- enables Unicode-aware
  filename comparison, including normalization-insensitive matching.
- A fix was merged to "compare filenames up to decomposition in case sensitive
  mode" when one host is macOS and `unicode = true`.

**Assessment:** This is handled reasonably well in current versions. The
`unicode = true` default should prevent most NFC/NFD mismatches. However:

- No external normalization tool is invoked. Unison does internal comparison
  only. Files with NFD names on macOS will retain NFD names on Linux, potentially
  confusing tools that expect NFC.
- If you create a file on Linux with a composed name and a file on macOS with the
  equivalent decomposed name, Unison should recognize them as the same file. But
  edge cases with unusual Unicode sequences may not be handled.

### 2.5 Extended attributes (xattrs)

Added in Unison 2.53.0. Enable with `xattrs = true`.

**Cross-platform behavior:**

- On Linux, `security.*` and `trusted.*` namespaces are ignored by default.
  `user.*` namespace attributes are synced.
- On macOS, xattrs like `com.apple.metadata:_kMDItemUserTags` (Finder tags),
  `com.apple.FinderInfo`, etc., are synced.
- Cross-platform xattr semantics differ significantly. An xattr from macOS
  (e.g., `com.apple.quarantine`) has no meaning on Linux but will be stored
  verbatim in the `user.*` namespace.

**Caveat:** Enabling xattrs changed the archive and wire format. Profiles created
before 2.53.0 will need archive rebuilds. Both sides must be 2.53.0+ to use
xattr sync.

### 2.6 Hard links

**Not supported.** Unison explicitly does not understand hard links. The
developers have stated this is an architectural limitation (filesystem tree vs.
graph model) that would require a fundamental redesign
([Hacker News discussion](https://news.ycombinator.com/item?id=39292638)).

**Workaround:** Convert hard links to symlinks, or use a post-sync script
(e.g., `jdupes --linkhard`) to recreate hard links on the destination.

---

## 3. Large directory performance

### 3.1 Initial sync / archive building

The first sync requires Unison to scan all files on both sides and build an
internal "archive" data structure. This is unavoidable and can be very slow for
large trees.

**Reported numbers:**

- Users with "several tens of thousands of files" report scans taking 20-30
  minutes.
- A user with 650,000 files reported memory exhaustion at ~5 kB per file,
  requiring ~3.5 GB RAM
  ([Issue #352](https://github.com/bcpierce00/unison/issues/352)).
- The root cause: all Lwt transport threads are created simultaneously and
  queued. None are garbage-collected until all complete. This is not fixed.

### 3.2 Subsequent scans

After the initial archive is built, subsequent scans compare the current
filesystem state against the cached archive. With `fastcheck = true` (default on
most platforms), only size and mtime are checked -- no content hashing. This
makes incremental scans fast (seconds to low minutes for tens of thousands of
files).

### 3.3 Memory usage

- Unison holds the entire file tree in memory during operation.
- For very large repositories, users have had to split into multiple profiles
  (e.g., one per top-level folder).
- Memory is **not** freed between sync cycles when using `-repeat`
  ([Issue #399](https://github.com/bcpierce00/unison/issues/399)). Memory from
  the previous scan is reused but not released.
- With `-repeat watch`, memory grew from 200 MB to 14 GB over time in one report
  ([Issue #329](https://github.com/bcpierce00/unison/issues/329)).

### 3.4 Practical guidance for user folders

For typical user folders (Documents, Pictures, Music, Videos) totaling tens of
thousands of files and tens to hundreds of gigabytes:

- **Initial sync will be slow** (30-60 minutes depending on file count and
  network). Seed with rsync first, then let Unison build its archive on already-
  identical trees for a faster first run.
- **Incremental scans are fast.** A cron job running every 5-15 minutes should
  complete in seconds.
- **Memory should be manageable.** Tens of thousands of files should not exhaust
  memory on a modern machine.
- **Ignore large binary directories** (e.g., video editing project caches,
  `.cache`, `node_modules`) to reduce scan time.

---

## 4. Reliability and data loss reports

### 4.1 Historical data loss

- **One confirmed data loss bug** in Unison 2.9.1 (circa 2003, FreeBSD). Caused
  by concurrent Unison processes synchronizing the same root to different hosts,
  where one process deleted `.unison.tmp` files used by another. The developers
  noted "Unison bugs that cause data loss have been very rare."
- No other confirmed data-loss bugs have been publicly reported in the modern
  (2.52+) codebase, **with the exception of OCaml 5.x compilation issues** (see
  section 8).

### 4.2 Files modified during sync

When a file changes while Unison is transferring it, Unison detects this and
aborts the transfer for that file. The file is skipped and other files continue
syncing. This is safe behavior -- no corruption occurs.

### 4.3 Silent temporary file deletion

Older versions of Unison silently deleted `.unison.tmp` files. A `purgetmpfiles`
preference was proposed but the current behavior silently cleans up temps.
Not a data loss vector for user files.

### 4.4 Crash resilience

The Unison project's claim of crash resilience is well-supported. The tool uses
a careful write-then-rename strategy for archive updates. Interrupted syncs can
be restarted without corruption. This is one of Unison's genuine strengths.

### 4.5 OCaml 5.x data loss risk

**This is the most serious current reliability concern.** See section 8 for
full details. In summary: Unison compiled with OCaml 5.x has exhibited
hard-to-reproduce bugs that can cause incorrect synchronization behavior.
The project explicitly refuses OCaml 5.x bug reports and recommends OCaml
4.14.x for production use.

---

## 5. fsmonitor / file watching

### 5.1 Architecture

Unison supports a `-repeat watch` mode that triggers re-sync when filesystem
changes are detected. This requires an external `unison-fsmonitor` helper
program that bridges OS-native filesystem events (inotify on Linux, FSEvents
on macOS) to Unison's internal protocol.

### 5.2 Linux status

On Linux, Unison ships a built-in fsmonitor that uses inotify. It works but has
known issues:

- **Self-triggering bug:** Unison's own fingerprint cache writes (`fp*` files in
  `~/.unison/`) trigger inotify events, causing the fsmonitor to fire every
  second even when no user files have changed
  ([Issue #1143](https://github.com/bcpierce00/unison/issues/1143)). This was
  resolved by ensuring the `~/.unison/` directory is excluded from monitoring.
  **Impact:** Prevents laptops from entering low-power mode, measurable battery
  drain.
- **inotify watch limits:** Large directory trees may exceed the default
  inotify watch limit (`/proc/sys/fs/inotify/max_user_watches`, typically
  8192). Must be increased (e.g., to 524288) via sysctl.
- The legacy `fsmonitor.py` script has been removed as of 2.53.8. The built-in
  OCaml fsmonitor is now the only option.

### 5.3 macOS status

**Unison does NOT ship an fsmonitor for macOS.** The `-repeat watch` option does
not work out of the box on macOS. You need a third-party adapter:

| Project | Language | Install |
|---------|----------|---------|
| [autozimu/unison-fsmonitor](https://github.com/autozimu/unison-fsmonitor) | Rust | `brew install autozimu/homebrew-formulas/unison-fsmonitor` or `cargo install` |
| [benesch/unison-fsmonitor](https://github.com/benesch/unison-fsmonitor) | Rust | cargo install |
| [patsoffice/mac-unison-fsmonitor](https://github.com/patsoffice/mac-unison-fsmonitor) | Go | manual build |

**Known issue with third-party fsmonitors:** If the main Unison process crashes
or is killed while the fsmonitor is running, the fsmonitor can enter an infinite
loop consuming all available system memory until macOS runs out of RAM
([Issue #1053](https://github.com/bcpierce00/unison/issues/1053)). This was
confirmed to be a bug in the third-party fsmonitor, not Unison itself, but it
affects anyone using `-repeat watch` on macOS.

### 5.4 Remote fsmonitor

There is no `-servercmd` equivalent for specifying the fsmonitor binary path on
the remote machine ([Issue #483](https://github.com/bcpierce00/unison/issues/483)).
If the fsmonitor is not on the remote SSH user's `PATH`, it won't be found.

### 5.5 Practical recommendation

**For reliability, use cron/systemd timers instead of `-repeat watch`.**

```
# Every 5 minutes
*/5 * * * * /usr/local/bin/unison -batch -silent my-profile
```

Or a systemd timer on Linux:

```ini
[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

The fsmonitor ecosystem is fragmented, has memory leak risks, and introduces
additional failure modes. Polling every 5 minutes is simple and reliable.

---

## 6. Version compatibility

### 6.1 The 2.52+ improvement

Prior to 2.52, Unison required:

1. Exact same Unison minor version on both endpoints (e.g., 2.48.x could not
   talk to 2.51.x).
2. Same OCaml compiler version used to build Unison on both endpoints.

This was the most frequently cited pain point in community discussions. Managing
matching versions across different Linux distributions (which package different
OCaml versions) and macOS (Homebrew) was a constant headache.

**Version 2.52 introduced a new wire protocol** that:

- Eliminates the OCaml version dependency (archive format no longer uses OCaml's
  raw marshalling).
- Allows cross-minor-version communication (2.52 can talk to 2.53).
- Archives are no longer compiler-version-dependent.

### 6.2 Caveats

- **One-time archive upgrade required.** The first run of 2.52+ on an existing
  archive triggers a full rescan. This is slow for large repositories.
- **2.52 <-> 2.48 interop** requires the OCaml compiler versions to still match
  AND the 2.52 executable on the server must be named `unison-2.48` for discovery
  to work. This is fragile and not recommended.
- **2.52 <-> 2.51 interop** requires matching OCaml compiler versions (same as
  pre-2.52 behavior).
- **2.52 <-> 2.53 interop works fully.** Both directions, any OCaml version.
  This is the intended steady state.
- **Feature gating:** If one side is 2.52 and the other is 2.53, features
  specific to 2.53 (xattrs, ACLs, reflinking) will not be available.

### 6.3 Distro packaging lag

Many distros still ship 2.51 or even 2.48. The Unison project explicitly does
not accept bug reports for these versions:

> You should use the most recent formal release, or a newer version from git.
> Earlier versions are no longer maintained, and bug reports are not accepted
> about these versions. This is true even though many packaging systems
> (including GNU/Linux distributions) continue to have 2.51 or even 2.48.

**Practical impact:** You may need to install from the GitHub releases page or
Homebrew rather than relying on `apt install unison` on Debian/Ubuntu stable.

---

## 7. Active maintenance

### 7.1 Team size

From the project's own documentation:

> Note that only a very small number of people are actively working on
> maintaining unison. An estimate is 2.5 people and 0.1 Full-Time Equivalents.

The primary maintainer is Tõivo Leedjärv (gildor478). Benjamin Pierce (the
original author) is still involved but at a high level.

### 7.2 Release cadence

| Year | Releases | Versions |
|------|----------|----------|
| 2023 | 4 | 2.53.1, 2.53.2, 2.53.3, 2.53.4 |
| 2024 | 3 | 2.53.5, 2.53.6, 2.53.7 |
| 2025 | 1 (as of Nov) | 2.53.8 |

Roughly 3-4 releases per year, all bugfix/maintenance within the 2.53.x line.
No minor version bump since 2.53.0 (2023). This is consistent with a mature,
slowly evolving project.

### 7.3 Issue responsiveness

Issues are triaged but response times are slow. Complex issues may sit for
months. The project is explicit about this:

> This has a substantial impact on the handling of bug reports and enhancement
> reports. Help in terms of high-quality bug reports, fixes, and proposed changes
> is very welcome.

### 7.4 GUI future

The macOS and Linux GUI (lablgtk-based) has no dedicated maintainer and carries
an explicit deprecation warning in every release. Alternative GUIs exist:

- **[Gunison](https://github.com/nicholasgasior/gunison):** Go + GTK3 wrapper
  around the CLI.
- CLI text UI remains fully functional and is the recommended interface.

### 7.5 Deprecations in progress

- **External rsync support** will be removed in 2.54.0. Unison's internal
  rsync-like transfer algorithm will be the only option.
- **fsmonitor.py** already removed in 2.53.8.

---

## 8. OCaml dependency

### 8.1 The OCaml 5 problem

**This is the single most important operational risk for Unison users in
2025-2026.**

Unison compiled with OCaml 5.x has exhibited hard-to-reproduce bugs that can
cause incorrect synchronization behavior. From the Arch Linux packaging
discussion
([Arch GitLab](https://gitlab.archlinux.org/archlinux/packaging/packages/unison/-/issues/1)):

> There have been reports of breakages with unison when compiled with OCaml 5.x
> [...] Because a file synchronizer is a sensitive piece of software and
> misbehavior may easily lead to severe data loss, the general advice seems to be
> that unison would better be compiled with OCaml 4.

The Unison project's official position (as of 2024-08):

> Bugs are only accepted when manifested with Unison built with OCaml 4.x,
> preferably 4.14.1. OCaml 5 seems to have unresolved trouble, and there is no
> one contributing to the Unison project who wants to debug in an OCaml 5
> environment.

The bug is described as "subtle" and "appears to manifest only when synchronizing
directories that have some not yet identified features (large? lots of files?)
and also depends on the previous synchronization state."

### 8.2 Packaging dilemma

| Platform | Default OCaml | Unison package status |
|----------|--------------|----------------------|
| Homebrew (macOS) | 5.4.0 | Formula builds with OCaml 5. Cask uses pre-built OCaml 4.14 binary. |
| Arch Linux | 5.x (OCaml 4 no longer in repos) | Official package may be compiled with OCaml 5. |
| Debian stable (bookworm) | 4.14.1 | Safe. |
| Ubuntu 24.04 | 4.14.1 | Safe. |
| Fedora 40+ | 5.x | Potentially affected. |

**Recommendation:**

1. **macOS:** Use `brew install --cask unison-app` (pre-built with OCaml 4.14)
   rather than `brew install unison` (builds from source with OCaml 5.4).
   Alternatively, download the binary directly from the
   [GitHub releases page](https://github.com/bcpierce00/unison/releases).
2. **Linux:** Use distro packages on Debian/Ubuntu (OCaml 4.14 in stable). On
   Arch/Fedora, download the pre-built binary from GitHub releases or build
   manually with OCaml 4.14.
3. **Verify your build:** Run `unison -version` to check. The output includes
   the OCaml compiler version used.

### 8.3 Homebrew ocaml@4

Homebrew does have an `ocaml@4` formula (keg-only), but the standard `unison`
formula does not reference it. Building Unison with `ocaml@4` requires manual
intervention (setting `PATH` and `OCAMLLIB` to point to the keg-only install).

### 8.4 Build from source

Building from source with OCaml 4.14 is straightforward:

```bash
# Install OCaml 4.14 via opam
opam switch create 4.14.2
eval $(opam env)

# Clone and build
git clone https://github.com/bcpierce00/unison.git
cd unison
git checkout v2.53.8
make
```

The resulting binary is self-contained (no OCaml runtime dependency).

---

## 9. Summary assessment

### What works well

- **Bidirectional sync algorithm:** Formally verified, 20+ years of production
  use. Conflict detection is excellent.
- **Crash resilience:** Archives are maintained in a consistent state even on
  abnormal termination.
- **Delta transfers:** rsync-like rolling checksums minimize bandwidth usage.
- **Low resource usage:** No daemon, no background process, no battery impact
  when idle.
- **Version compatibility (2.52+):** Cross-version, cross-compiler-version
  protocol is a huge improvement.
- **Cross-platform Unicode handling:** NFD/NFC normalization is built in.
- **xattr support (2.53+):** Extended attributes including Finder tags now sync.

### What does not work well

- **No fsmonitor on macOS** -- third-party adapters are fragmented and have
  memory leak bugs.
- **OCaml 5.x compilation risk** -- the most critical issue. Homebrew's default
  formula builds with OCaml 5, which the Unison project itself refuses to
  support. Silent data corruption is possible.
- **Memory scaling** -- initial sync of 650k+ files can exhaust memory. Not
  an issue for typical user folders (tens of thousands of files).
- **No hard link support** -- architectural limitation, will never be fixed.
- **GUI is dying** -- no maintainer for macOS GUI, explicit deprecation warnings.
- **Tiny maintainer team** -- 2.5 people at 0.1 FTE. Bus factor is extremely
  low.
- **No built-in NAT traversal** -- requires external SSH access (pair with
  Tailscale/WireGuard).
- **No real-time sync** -- polling or fragile fsmonitor are the only options.
- **Distro packaging lag** -- many distros ship ancient versions that are
  incompatible with current releases.

### Risk rating for the stated use case

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| OCaml 5 silent corruption | **Critical** | Medium | Use cask/pre-built binary with OCaml 4.14 |
| fsmonitor memory leak (macOS) | High | Medium | Use cron instead of `-repeat watch` |
| Memory exhaustion (large trees) | Medium | Low | Split profiles, ignore caches |
| GUI deprecation | Medium | High | Use CLI (batch mode or text UI) |
| Project abandonment | Medium | Low-Medium | Mature codebase, low change rate |
| Version mismatch across machines | Low | Low | Use 2.53.x everywhere |
| Unicode/case-sensitivity edge cases | Low | Low | `unicode = true`, `ignorecase = default` |

---

## Sources

- [Unison GitHub repository](https://github.com/bcpierce00/unison)
- [Unison releases page](https://github.com/bcpierce00/unison/releases)
- [2.52 Migration Guide](https://github.com/bcpierce00/unison/wiki/2.52-Migration-Guide)
- [OCaml versions wiki page](https://github.com/bcpierce00/unison/wiki/ocaml-versions)
- [Issue #1053 -- fsmonitor infinite memory](https://github.com/bcpierce00/unison/issues/1053)
- [Issue #1143 -- fsmonitor self-triggering on Linux](https://github.com/bcpierce00/unison/issues/1143)
- [Issue #352 -- 650k file memory exhaustion](https://github.com/bcpierce00/unison/issues/352)
- [Issue #329 -- memory leak with -repeat](https://github.com/bcpierce00/unison/issues/329)
- [Issue #399 -- caches retained indefinitely](https://github.com/bcpierce00/unison/issues/399)
- [Issue #291 -- xattr support request (resolved)](https://github.com/bcpierce00/unison/issues/291)
- [Issue #79 -- -follow + -repeat watch crash on macOS](https://github.com/bcpierce00/unison/issues/79)
- [Issue #483 -- no -servercmd for fsmonitor](https://github.com/bcpierce00/unison/issues/483)
- [Issue #1054 -- case-sensitivity refusal](https://github.com/bcpierce00/unison/issues/1054)
- [Issue #172 -- directory timestamp mismatch](https://github.com/bcpierce00/unison/issues/172)
- [Arch Linux OCaml 5 packaging issue](https://gitlab.archlinux.org/archlinux/packaging/packages/unison/-/issues/1)
- [ArchWiki -- Unison](https://wiki.archlinux.org/title/Unison)
- [Homebrew unison formula](https://formulae.brew.sh/formula/unison)
- [Homebrew OCaml formula](https://formulae.brew.sh/formula/ocaml)
- [autozimu/unison-fsmonitor (Rust)](https://github.com/autozimu/unison-fsmonitor)
- [Unison Hacker News discussion (Feb 2024)](https://news.ycombinator.com/item?id=39292638)
- [Lorenzo Bettini -- Unison on macOS via Homebrew](https://www.lorenzobettini.it/2025/07/using-unison-file-synchronizer-on-macos-now-available-via-homebrew/)
- [Unison FAQ -- Troubleshooting](https://alliance.seas.upenn.edu/~bcpierce/wiki/index.php?n=Main.UnisonFAQTroubleshooting)
- [Unison FAQ -- Tips](https://alliance.seas.upenn.edu/~bcpierce/wiki/index.php?n=Main.UnisonFAQTips)
