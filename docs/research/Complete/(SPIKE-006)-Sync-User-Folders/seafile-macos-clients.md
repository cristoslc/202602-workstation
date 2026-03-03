# Seafile client options on macOS

**Status:** Active
**Date:** 2026-02-25
**Scope:** Evaluate all available Seafile client options on macOS -- official GUI,
CLI clients, third-party tools, WebDAV, rclone, automation capabilities -- with
raw findings and sources for each.

---

## 1. Official Seafile GUI client for macOS

### Current version and release cadence

- **Seafile Sync Client v9.0.16** released 2026-01-09 (latest as of 2026-02-25).
  Prior releases: v9.0.15 (2025-08-22), v9.0.11 (2024-11-15), v9.0.9 (2024-10-29,
  later pulled back), v9.0.8 (2024-08-12), v9.0.7 (2024-08-05).
  [Releases](https://github.com/haiwen/seafile-client/releases) |
  [Changelog](https://manual.seafile.com/latest/changelog/client-changelog/)

- **SeaDrive 3.0.18** released 2025-12 (virtual drive client, macOS 12.1+).
  SeaDrive 2.0.26 for macOS below 12.1. All SeaDrive requires macOS >= 10.14.
  [Drive changelog](https://manual.seafile.com/latest/changelog/drive-client-changelog/)

- Both are available via Homebrew casks:
  `brew install --cask seafile-client` (v9.0.16, macOS >= 11)
  `brew install --cask seadrive` (v3.0.18, macOS >= 12)
  [seafile-client cask](https://formulae.brew.sh/cask/seafile-client) |
  [seadrive cask](https://formulae.brew.sh/cask/seadrive)

### Architecture

- The sync client is a Qt 6-based GUI. It is NOT a native Swift/AppKit app. Built
  with cmake, links against Qt6::Core, Qt6::Gui, Qt6::Widgets, Qt6::Network,
  Qt6::Core5Compat. Official macOS binaries ship with Qt 6.5.2 (since v9.0.4),
  though the CMakeLists.txt does not enforce a minimum Qt 6 minor version.
  [CMakeLists.txt](https://github.com/haiwen/seafile-client/blob/master/CMakeLists.txt)

- SeaDrive 3.0 on macOS is implemented as a Finder extension (no longer requires
  OSXFuse/macFUSE, unlike SeaDrive 2.x which depended on OSXFuse).

- Internally, the GUI launches `seaf-daemon` which manages the actual sync. The
  daemon uses ccnet for RPC. Config stored in `~/.ccnet/` by default.
  [seaf-cli source](https://github.com/haiwen/seafile/blob/master/app/seaf-cli)

### Features

- Per-library selective sync.
- Client-side encryption (password-protected libraries).
- Delta-only (block-level) transfers, resumable uploads.
- Conflict handling based on file history (not timestamp).
- Multi-server sync support.
- Offline access to synced files.
- File version history and library snapshots.
- SSO login via external browser (since v9.0.5).
- SOCKS5 proxy with username/password auth (since v9.0.6).

### Known macOS issues

- **Crash on launch (v9.0.4):** Users reported seafile-client-9.0.4.dmg crashing
  immediately after selecting destination folder on Ventura, Monterey, Catalina.
  [Forum thread](https://forum.seafile.com/t/problem-with-seafile-client-for-mac/19319)

- **v9.0.9 pulled back:** In November 2024, macOS client v9.0.9 appeared to have
  been removed from the download site; only v9.0.7 was available.
  [Forum thread](https://forum.seafile.com/t/was-seafile-macos-client-9-0-9-pulled-back/22624)

- **Discrete GPU usage:** Issue #984 reported the macOS client triggering the
  discrete GPU unnecessarily, affecting battery life on MacBook Pros.
  [GitHub issue](https://github.com/haiwen/seafile-client/issues/984)

- **Menu bar icon complaints:** Users report the green checkmark icon is
  distracting; most macOS apps use monochrome icons. No way to hide it entirely.
  [GitHub issue](https://github.com/haiwen/seafile-client/issues/1269) |
  [Forum thread](https://forum.seafile.com/t/macos-menu-bar-icon-please-make-it-optional/24848)

- **Apple Silicon support delays:** Native Apple Silicon support was reported as
  "in the works for a couple of years" before eventually shipping.
  [Forum thread](https://forum.seafile.com/t/support-for-apple-silicon/17420)

- **SeaDrive crash on first start on Apple Silicon** was fixed in a recent
  SeaDrive update.

- **SeaDrive multiple accounts after macOS 14.4 (Sonoma):** Required a fix in a
  recent SeaDrive update.

- **v9.0.7 download speed regression:** Community reports indicate download speeds
  dropped from ~100 MB/s to 10-30 MB/s starting with v9.0.7.

### Sources

- [haiwen/seafile-client GitHub](https://github.com/haiwen/seafile-client)
- [haiwen/seafile GitHub](https://github.com/haiwen/seafile)
- [Seafile download page](https://www.seafile.com/en/download/)
- [GitHub issues](https://github.com/haiwen/seafile-client/issues)

---

## 2. Why there is no official seaf-cli on macOS

### Finding: seaf-cli is Linux-only by policy, not by hard technical limitation

**seaf-cli is a Python 3 script** that wraps `seaf-daemon` via RPC. The script
itself is platform-agnostic (uses POSIX conventions, fcntl file locking). However
it hardcodes `platform = 'linux'` when generating auth tokens for the server.
[seaf-cli source](https://github.com/haiwen/seafile/blob/master/app/seaf-cli)

**The official macOS build instructions build the GUI only.** The build process
compiles libsearpc, the seafile daemon, and then `seafile-applet` (the Qt GUI).
The seaf-cli wrapper script is never mentioned in the macOS build docs. The
packaging script targets `seafile-applet` explicitly.
[macOS build docs](https://manual.seafile.com/12.0/develop/osx/)

**Distribution is Linux-only:**
- Since v9.0.7, seaf-cli is distributed as an AppImage (x86_64 Linux only).
- Also packaged in Debian/Ubuntu/Fedora repos and AUR.
- The official download page lists CLI only under Linux.
  [Download page](https://www.seafile.com/en/download/)

**Reasons (inferred, not officially stated):**
1. **Resource constraints.** Seafile team has explicitly stated: "due to our
   limited capacity, it's hard to update Linux clients for all the latest OS in a
   timely manner. The Linux clients are always a few versions behind Windows and
   macOS." CLI for macOS is apparently not a priority.
2. **Use case alignment.** CLI is designed for headless Linux servers/VMs where
   there is no desktop environment -- a much rarer scenario on macOS.
3. **macOS packaging gap.** No Homebrew formula for seaf-cli exists. The AppImage
   format is Linux-only.

**Could it be built for macOS?** Probably yes. The macOS build instructions
already compile `seaf-daemon` (the underlying sync engine) as part of building
the GUI client. The `seaf-cli` Python script should be able to communicate with
that daemon. The hardcoded `platform = 'linux'` string would need patching.
Dependencies (libsearpc, libevent, glib2, openssl, jansson, libwebsockets) are
all available via MacPorts/Homebrew.

**Forum thread on building seaf-cli** (Sep 2024): A user wanted to build
seaf-cli for ARM (no ARM package/AppImage). The only build instructions were
described as "a bit outdated." No macOS/Darwin discussion in that thread.
[Building seaf-cli](https://forum.seafile.com/t/building-seaf-cli/22463)

### Sources

- [seaf-cli source code](https://github.com/haiwen/seafile/blob/master/app/seaf-cli)
- [macOS build instructions](https://manual.seafile.com/12.0/develop/osx/)
- [Linux CLI docs](https://help.seafile.com/syncing_client/linux-cli/)
- [Building seaf-cli forum thread](https://forum.seafile.com/t/building-seaf-cli/22463)
- [seaf-cli man page](https://www.mankier.com/1/seaf-cli)

---

## 3. Third-party CLI clients for Seafile on macOS

### Finding: No third-party CLI client exists

There is no Homebrew formula for a Seafile CLI client (only the GUI cask).
There is no community-maintained macOS build of seaf-cli.
The AUR package is Linux-only.

**The `seafile-client` Homebrew cask installs the GUI app**, not a CLI tool.

### Workarounds for CLI access on macOS

1. **Docker container running seaf-cli (Linux):**
   - `flowgunso/seafile-client` Docker image runs seaf-cli inside a container.
   - Shares a single Seafile library as a volume at `/library/`.
   - Env vars: `SEAF_SERVER_URL`, `SEAF_USERNAME`, `SEAF_PASSWORD`,
     `SEAF_LIBRARY_UUID`.
   - Supports 2FA via `SEAF_2FA_SECRET`, SSL cert skip, custom UID/GID.
   - Known issue: adding files on client side requires container restart for
     sync to trigger.
   - [Docker Hub](https://hub.docker.com/r/flowgunso/seafile-client)
   - [Forum thread](https://forum.seafile.com/t/docker-client-to-sync-files-with-containers/8573)
   - Alpine-based fork: [halsbox/docker-seaf-cli](https://github.com/halsbox/docker-seaf-cli)

2. **Build seaf-daemon + seaf-cli from source on macOS:**
   - Dependencies available via MacPorts: `autoconf automake pkgconfig libtool
     glib2 libevent vala openssl git jansson cmake libwebsockets argon2`.
   - Build libsearpc, then seafile (with `--disable-fuse
     --enable-compile-universal=yes`), which produces `seaf-daemon`.
   - Copy `seaf-cli` Python script from `seafile/app/seaf-cli`, patch
     `platform = 'linux'` to `'darwin'` or `'macos'`.
   - Not officially supported or tested by Seafile team on macOS.
   - [Build instructions](https://manual.seafile.com/12.0/develop/osx/)
   - [Community wiki](https://github.com/ypid/seafile-wiki/blob/master/Build-and-use-seafile-client-from-source.md)

3. **Use the Seafile Web API directly (see section 7 below).**

### Sources

- [Homebrew seafile-client cask](https://formulae.brew.sh/cask/seafile-client)
- [flowgunso/seafile-client Docker](https://hub.docker.com/r/flowgunso/seafile-client)
- [halsbox/docker-seaf-cli](https://github.com/halsbox/docker-seaf-cli)
- [titoshadow/docker-seafile-client](https://github.com/titoshadow/docker-seafile-client)

---

## 4. Rclone Seafile backend

### Backend capabilities (from rclone overview table)

| Feature           | Support  |
|-------------------|----------|
| Hash              | None     |
| ModTime           | Read-only (R) -- set by server on upload, cannot be set to original |
| Purge             | Yes      |
| Copy              | Yes      |
| Move              | Yes      |
| DirMove           | Yes      |
| CleanUp           | Yes      |
| ListR             | Yes (v7+, `--fast-list`) |
| StreamUpload      | Yes      |
| MultithreadUpload | No       |
| LinkSharing       | Yes (non-encrypted libraries only) |
| About             | Yes      |
| EmptyDir          | Yes      |
| Case Insensitive  | No       |
| MIME Type          | None     |
| Metadata          | None     |

[rclone overview](https://rclone.org/overview/) |
[rclone seafile docs](https://rclone.org/seafile/)

### Configuration modes

1. **Root mode:** Point remote to server root, access as `remote:library/path`.
2. **Library mode:** Point remote to a specific library, access as
   `remote:path/to/dir`. Recommended for encrypted libraries and slightly faster.

### Supported versions and features

- Seafile 6.x, 7.x, 8.x, 9.x all supported.
- Encrypted libraries supported.
- 2FA-enabled users supported.
- Library API tokens NOT supported.
- SSO NOT supported (as of March 2024).
  [SSO issue](https://github.com/rclone/rclone/issues/7686)

### Critical limitations for sync

1. **No ModTime write support.** Seafile sets the mtime to upload time. Rclone
   cannot set it to the original file's mtime. This means sync comparisons fall
   back to file size only. Changes where content differs but size stays the same
   will NOT be detected.
   [ModTime feature request](https://forum.rclone.org/t/seafile-backend-support-for-modtime/23176)

2. **No hash/checksum support.** The Seafile API does not return file checksums.
   `--checksum` flag is ineffective because there is no hash to compare.
   [ModTime thread #3](https://forum.rclone.org/t/seafile-backend-support-for-modtime/23176/3)

3. **Seafile-to-Seafile sync bug (Jan 2025):** `rclone sync SeafileA:/src
   SeafileB:/dst` re-syncs files that are already identical on both sides. Reported
   on rclone v1.68.2 against Seafile 11.0.14/11.0.16.
   [GitHub issue](https://github.com/rclone/rclone/issues/8300)

4. **Encrypted library 1-hour timeout.** Encrypted libraries are decrypted
   server-side for 1 hour. Long-running rclone syncs to encrypted libraries fail
   after this window. No server-side setting to extend.
   [GitHub issue](https://github.com/rclone/rclone/issues/6662)

5. **Rename quirks.** rclone source code notes: "Seafile seems to be acting
   strangely if the renamed file already exists (some cache issue maybe?)" --
   workaround is to delete destination before rename.
   [Source code](https://github.com/rclone/rclone/blob/master/backend/seafile/seafile.go)

### Rclone mount with Seafile on macOS

- `rclone mount` works on macOS via macFUSE.
- Without `--vfs-cache-mode`, the mount is read-only on macOS when using NFS mount.
- macOS Finder will update file modification times when viewing files, potentially
  causing rclone to re-upload the entire file.
- Recommended flags: `--vfs-cache-mode full` or `--vfs-cache-mode writes`.
- [rclone mount docs](https://rclone.org/commands/rclone_mount/)

### Rclone bisync with Seafile

- No specific documentation or testing of `rclone bisync` with the Seafile
  backend exists.
- Given no ModTime write and no hash support, bisync would rely on size-only
  comparison, making it unreliable for detecting content changes where file size
  stays constant.
- The Hasher overlay backend could potentially provide cached checksums as a
  workaround. [rclone hasher](https://rclone.org/hasher/)

### Workaround: rclone Hasher backend

The Hasher overlay can cache checksums for backends that lack native support.
It computes hashes on upload/download and stores them in a bolt database under
`~/.cache/rclone/kv/`. This could improve sync accuracy for the Seafile backend.

### Sources

- [rclone Seafile backend docs](https://rclone.org/seafile/)
- [rclone overview table](https://rclone.org/overview/)
- [Re-sync bug #8300](https://github.com/rclone/rclone/issues/8300)
- [Encrypted library timeout #6662](https://github.com/rclone/rclone/issues/6662)
- [ModTime feature request](https://forum.rclone.org/t/seafile-backend-support-for-modtime/23176)
- [SSO not supported #7686](https://github.com/rclone/rclone/issues/7686)
- [Preserving modtime discussion](https://forum.rclone.org/t/preserving-modtime-metadata-when-copying-to-seafile/42400)
- [Problem syncing](https://forum.rclone.org/t/problem-syncing-to-from-seafile-source/39117)
- [rclone as seafuse replacement](https://forum.seafile.com/t/rclone-docker-plugin-as-replacement-for-seafuse/19699)

---

## 5. Other third-party tools for Seafile sync on macOS

### Cyberduck (file browser, not sync)

- Connects to Seafile via WebDAV (SeafDAV).
- **Browser only, not a sync tool.** Supports upload/download of individual files
  and folders. No continuous background sync.
- Free and open source (donation-ware).
- [Cyberduck Seafile docs](https://docs.cyberduck.io/protocols/webdav/seafile/)
- [Cyberduck website](https://cyberduck.io/)

### Mountain Duck (virtual drive with smart sync)

- From the same developers as Cyberduck.
- Mounts Seafile (via WebDAV) as a volume in Finder.
- **Smart Synchronization:** files can be marked for offline access. Changes sync
  in the background when the server is reachable. Conflict handling renames
  conflicting files with timestamps.
- Supports Cryptomator vaults for client-side encryption.
- Requires macOS Finder extension enabled in System Preferences > Extensions.
- Commercial software (paid license).
- Since it mounts as a local volume, you can use `rsync` or other tools on the
  mounted path.
- [Mountain Duck website](https://mountainduck.io/)
- [Mountain Duck sync docs](https://docs.duck.sh/mountainduck/sync/)

### GoodSync

- **Does NOT natively support Seafile.** Seafile is not in GoodSync's list of
  supported services.
- A user on the Seafile forum attempted to connect via WebDAV and encountered
  errors.
- [GoodSync supported services](https://help.goodsync.com/hc/en-us/articles/115003939492-Supported-Services)
- [Forum thread](https://forum.seafile.com/t/is-it-possible-to-set-up-seadrive-synchronization-in-goodsync/18007)

### Syncthing / Resilio Sync

- These are **peer-to-peer sync tools** that do not support the Seafile protocol.
  They are alternatives to Seafile, not clients for it.

### Sources

- [Cyberduck Seafile](https://docs.cyberduck.io/protocols/webdav/seafile/)
- [Mountain Duck](https://mountainduck.io/)
- [GoodSync supported services](https://help.goodsync.com/hc/en-us/articles/115003939492-Supported-Services)

---

## 6. Seafile WebDAV interface on macOS

### Server-side: SeafDAV

- Seafile ships a WebDAV server component called SeafDAV.
- Must be enabled in server configuration (not on by default in all deployments).
- [SeafDAV docs](https://haiwen.github.io/seafile-admin-docs/11.0/extension/webdav/)

### Known limitations (from official Seafile documentation)

1. **Slow bulk uploads.** "Uploading a large number of files at once is usually
   much slower than the syncing client, because each file needs to be committed
   separately."

2. **Excessive metadata requests.** "The access to the WebDAV server may be slow
   sometimes, because the local file system driver sends a lot of unnecessary
   requests to get the files' attributes."

3. **Not for regular sync.** "WebDAV is more suitable for infrequent file access.
   If you want better performance, please use the sync client instead."

### macOS Finder + WebDAV: officially not recommended

Direct quote from Seafile documentation: **"Finder's support for WebDAV is also
not very stable and slow. So it is recommended to use a WebDAV client software
such as Cyberduck."**

### Alternative WebDAV clients on macOS

- **Cyberduck** -- free, browser only (see section 5).
- **Mountain Duck** -- paid, mounts as drive with smart sync (see section 5).
- **Transmit** -- commercial FTP/WebDAV client for macOS.
- macOS Finder Connect to Server (WebDAV) -- functional but officially
  discouraged by Seafile.

### Verdict

WebDAV is a poor substitute for the native sync client for ongoing
synchronization. It lacks block-level delta transfers, has high overhead per
file, and macOS Finder's WebDAV implementation is specifically called out as
unreliable by Seafile's own documentation.

### Sources

- [SeafDAV documentation](https://haiwen.github.io/seafile-admin-docs/11.0/extension/webdav/)
- [Seafile WebDAV FAQ](https://help.seafile.com/faq/)

---

## 7. Community projects and API wrappers for CLI automation

### Official Python SDK: `python-seafile`

- Python library wrapping Seafile Web API.
- Supports authentication with username/password or API tokens.
- Can list libraries, upload/download files, manage shares.
- Platform-independent (works on macOS).
- Low maintenance cadence; no published GitHub releases. 38 stars, 47 forks.
- [GitHub](https://github.com/haiwen/python-seafile)

### Community fork: `python-seafile-api`

- Fork of the official SDK with additional features.
- Available on PyPI: `pip install python-seafile-api`.
- Inactive maintenance (no releases in 12+ months, ~100 weekly downloads).
- Newer alternative: `seafileapi2` (v2.0.1, Feb 2025) on PyPI.
- [GitHub](https://github.com/AshotS/python-seafile-api) |
  [PyPI](https://pypi.org/project/python-seafile-api/)

### `seaf-share.py` (community script)

- Python script for downloading/uploading via Seafile share links.
- Works in console/terminal without a browser.
- Supports password-protected links, single files, and directories.
- [GitHub](https://github.com/twei7/seaf-share)
- [Forum thread](https://forum.seafile.com/t/python-script-for-seafile-downloading-uploading-share-link/2605)

### SeaSync (community Swift client for macOS)

- A native Swift/SwiftUI macOS menu-bar app for Seafile (MIT license).
- Created to address official Qt client crashes on macOS 15 Sequoia and macOS 26
  Tahoe.
- Features: bidirectional sync, encrypted library support, FSEvents-based file
  change detection, macOS Keychain credential storage.
- Very early/experimental (few stars, last updated 2026-01-24).
- Owner: dvdcodez.
- [GitHub](https://github.com/dvdcodez/SeaSync)

### Seafile Web API v2.1

The REST API is comprehensive enough to build custom CLI sync tools:

- **Auth:** `POST /api2/auth-token/` with username+password returns an API token.
- **List libraries:** `GET /api2/repos/`
- **Download file:** `GET /api2/repos/{repo-id}/file/?p=/path`
- **Get upload link:** `GET /api2/repos/{repo-id}/upload-link/?p=/upload-dir`
- **Upload file:** `POST` to the upload link with multipart form data.
- **Resumable upload:** Large files can be uploaded in chunks; server indexes
  asynchronously (`need_idx_progress=true` returns a `task_id`).
- **Encrypted libraries:** Must decrypt the library first before upload/download.
- Python and JavaScript examples at
  [haiwen/webapi-examples](https://github.com/haiwen/webapi-examples).
- [API docs](https://haiwen.github.io/seafile-admin-docs/12.0/develop/web_api_v2.1/) |
  [File upload](https://cloud.seafile.com/published/web-api/v2.1/file-upload.md) |
  [File operations](https://download.seafile.com/published/web-api/v2.1/file.md) |
  [API manual mirror](https://github.com/seafile-data/seafile-web-api-manual)

### Sources

- [python-seafile](https://github.com/haiwen/python-seafile)
- [python-seafile-api](https://github.com/AshotS/python-seafile-api)
- [seaf-share](https://github.com/twei7/seaf-share)
- [Web API v2.1](https://haiwen.github.io/seafile-admin-docs/12.0/develop/web_api_v2.1/)
- [Seafile community topic](https://github.com/topics/seafile-community)

---

## 8. Official macOS GUI client automation

### Pre-configuration via `.seafilerc`

On macOS (and Linux), the admin can create `~/.seafilerc` in the user's HOME
directory to pre-configure the client. INI format with `[preconfigure]` section.

**Available keys:**

| Key | Description |
|-----|-------------|
| `PreconfigureServerAddr` | Default server URL |
| `PreconfigureUsername` | Preset username/email |
| `PreconfigureUserToken` | Seahub access API token |
| `PreconfigureShibbolethLoginUrl` | Shibboleth auth URL |
| `PreconfigureDirectory` | Seafile folder location (absolute path) |
| `PreconfigureServerAddrOnly` | Restrict to single server (1/0) |
| `HideConfigurationWizard` | Skip setup wizard (1/0) |
| `PreconfigureKeepConfigWhenUninstall` | Suppress uninstall dialog (1/0) |
| `PreconfigureSuppressLaunchAfterInstall` | Prevent auto-launch after install |
| `PreconfigureBlockSize` | File indexing block size in bytes (>1024) |

Example `~/.seafilerc`:
```ini
[preconfigure]
PreconfigureDirectory = ~/
PreconfigureUsername = user@example.com
PreconfigureUserToken = t0Ken
PreconfigureServerAddr = https://cloud.example.com
HideConfigurationWizard = 1
PreconfigureServerAddrOnly = 1
```

This is suitable for Ansible templating: deploy the `.seafilerc` file before the
user first launches the Seafile client.

[Seafile FAQ - preconfigure](https://help.seafile.com/faq/)

### What CANNOT be pre-configured

- **Specific library sync mappings** (which libraries sync to which local folders)
  cannot be set via `.seafilerc`. The user must configure these through the GUI
  or `seaf-cli` (which is not available on macOS).
- Copying `.config/seafile/` folder between machines is "not supported and likely
  cannot work" per Seafile developer daniel.pan.
  [Forum thread](https://forum.seafile.com/t/configure-client-gui-via-ansible/24707/4)

### macOS launchd integration

- The macOS GUI client registers a Login Item automatically (launches at login).
- No documented CLI flags for the `Seafile Client.app` binary.
- No documented plist configuration beyond what `.seafilerc` provides.
- No way to trigger sync actions from the command line via the GUI app.

### seaf-daemon paths on macOS (from crash/debug logs)

From a forum debug log, the macOS GUI client launches `seaf-daemon` with flags:
- `-c` pointing to the ccnet config dir (user-specific path)
- `-d` pointing to seafile-data dir
The exact paths are under `~/Library/` or `~/.ccnet/` depending on version.
[Forum thread](https://forum.seafile.com/t/mac-os-x-client-doesnt-sync/5697)

### SeaDrive CLI on macOS

SeaDrive CLI is Linux-only (distributed as AppImage since 3.0.12). The macOS
SeaDrive is GUI-only with no documented CLI flags or daemon mode.
[SeaDrive Linux CLI docs](https://help.seafile.com/drive_client/drive_client_for_linux/)

### Sources

- [Seafile FAQ / preconfigure](https://help.seafile.com/faq/)
- [Configure client GUI via Ansible](https://forum.seafile.com/t/configure-client-gui-via-ansible/24707/4)
- [macOS sync debug log](https://forum.seafile.com/t/mac-os-x-client-doesnt-sync/5697)
- [SeaDrive Linux docs](https://help.seafile.com/drive_client/drive_client_for_linux/)

---

## Summary matrix

| Option | Type | Sync? | CLI? | macOS native? | Reliability | Notes |
|--------|------|-------|------|---------------|-------------|-------|
| Seafile Sync Client | GUI | Yes (full) | No | Homebrew cask, Qt6 | Good (some crashes reported) | Best option for sync |
| SeaDrive 3.0 | GUI | Virtual drive | No | Finder extension | Good | macOS 12.1+ only |
| seaf-cli | CLI | Yes (full) | Yes | Linux only | Good on Linux | Not distributed for macOS |
| seaf-cli via Docker | CLI in container | Yes (single lib) | Yes | Docker Desktop | Fair (restart issues) | Workaround, not ideal |
| Build seaf-cli from source | CLI | Yes (full) | Yes | Possible but unsupported | Unknown | Requires patching, not tested |
| rclone (Seafile backend) | CLI | One-way copy/sync | Yes | Yes (Homebrew) | Poor for sync (no modtime/hash) | Use for backup, not bidirectional |
| rclone mount | Virtual drive | Via FUSE | Yes | macFUSE required | Fair | Finder mtime issues |
| Cyberduck | GUI | No (browser) | No | Yes | Good | File browsing only |
| Mountain Duck | GUI | Smart sync | No | Yes (Finder ext) | Good | Commercial, WebDAV-based |
| WebDAV (Finder) | Native | No (mount) | No | Yes | Poor (per Seafile docs) | Officially discouraged |
| python-seafile SDK | Library | Custom | Yes | Yes (pip) | API-dependent | Build your own tool |
| SeaSync (community Swift) | GUI | Bidirectional | No | Yes (native Swift) | Unknown (new, few stars) | Very early stage |
