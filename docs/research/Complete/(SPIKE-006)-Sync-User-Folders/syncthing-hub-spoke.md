# Syncthing hub-and-spoke topology deep dive

**Status:** Active
**Date:** 2026-02-25
**Scope:** Evaluate Syncthing in a self-hosted hub-and-spoke (star) topology for
ongoing sync of user data folders across 2-3 workstations, with a home server as
the always-on hub. Covers topology configuration, conflict handling mechanics,
folder type strategies, and operational tradeoffs.

**Context:** The parent [README.md](README.md) evaluates Syncthing as one of
several ongoing-sync candidates. This document goes deeper on the specific
deployment model under consideration: a trusted (unencrypted) central hub with
spoke clients that only connect to the hub, not to each other.

---

## 1. Hub-and-spoke topology

### Can spokes be restricted to hub-only connections?

**Yes.** Syncthing does not require full mesh. The core principle, stated by
maintainer Jakob Borg:

> "There is no need for all devices to know about each other, as long as there
> is a 'path' from one device to another via any number of intermediate devices."

### Configuration

**On the hub (home server):**

- Add all spoke devices as peers.
- Share desired folders with each spoke.
- Set listening address to `tcp://0.0.0.0:22000`.
- Optionally disable Global Discovery, Local Discovery, and Relaying for a
  fully private network.

**On each spoke (workstation):**

- Add only the hub as a peer. Do **not** add other spokes.
- Set the hub's address explicitly: `tcp://<hub-ip>:22000` (not `dynamic`).
- Remove or invalidate listening addresses to prevent inbound connections from
  other devices. The Syncthing maintainer suggests removing listening addresses
  entirely. Workaround for the GUI resetting empty addresses to `dynamic`: use a
  dummy address like `tcp://0.0.0.0:0`.

### Data flow

Changes propagate through the hub: if device A modifies a file, the hub receives
the change, then pushes it to device B. Devices A and B never communicate
directly.

---

## 2. The introducer feature

The [Introducer feature](https://docs.syncthing.net/users/introducer.html)
simplifies device management in a hub topology. When the hub is marked as
"introducer" on each spoke:

- New spokes added to the hub are automatically introduced to existing spokes
  (for mutual folders).
- Removing a spoke from the hub automatically removes it from all other devices.
- Device relationships are configured in one place (the hub).

### Warnings

- **Never set two devices as introducers to each other.** The docs explicitly
  warn this causes removed devices to be constantly re-introduced.
- **Introducer status is transitive.** An introducer's introducer becomes your
  introducer too.
- **Manually removed devices get re-added** on the next connection to the
  introducer.

### Introducer vs. strict star topology

The introducer feature can **undermine** a strict star topology. If the hub
introduces spoke A to spoke B (because they share mutual folders), the spokes
learn about each other and can form direct connections. To maintain strict hub-
only connections:

- **Option A:** Do not use the introducer feature. Manage device relationships
  manually on each spoke.
- **Option B:** Use the introducer but carefully control which folders are shared
  with which devices so mutual folder overlap does not cause unwanted
  introductions.

For a 2-3 workstation setup, Option A is manageable and more predictable.

---

## 3. Conflict detection

### Version vectors

Syncthing uses **version vectors** (a form of vector clock) defined in the
[BEP v1 specification](https://docs.syncthing.net/specs/bep-v1.html):

```protobuf
message Vector {
    repeated Counter counters = 1;
}

message Counter {
    uint64 id    = 1;  // First 64 bits of the device ID
    uint64 value = 2;  // Incrementing counter, starting at zero
}
```

Each file carries a `version` field. When a device modifies a file, it
increments its own counter. The combination of `{Folder, Name, Version}`
uniquely identifies a file's contents at a given point.

### How concurrency is detected

`Vector.Compare(a, b)` returns an ordering: Equal, Greater, Lesser,
ConcurrentLesser, or ConcurrentGreater. A conflict occurs when two vectors are
**concurrent** -- device A has changes B has not observed, and vice versa.

The system is **not content-aware** -- a conflict is declared whenever concurrent
version vectors exist, regardless of whether file content actually differs.
However, Syncthing checks whether content differs before creating a conflict
copy (identical content = no conflict copy needed).

### Filesystem change detection

Two mechanisms detect local changes:

1. **Filesystem watcher** (enabled by default) -- OS notifications (inotify on
   Linux, FSEvents on macOS).
2. **Full periodic rescan** (default: hourly) -- checks mtime, size, and
   permissions; rehashes with SHA-256 if any attribute changed.

---

## 4. Conflict resolution

### Winner selection algorithm

When concurrent version vectors are detected, Syncthing applies a deterministic
algorithm (the `WinsConflict` function on `FileInfo`):

1. **Modification vs. deletion (v2.0 change):**
   - Pre-2.0: Modified files always won; deletes were always resurrected.
   - Post-2.0: Deletes participate as normal versions. A delete can win,
     resulting in the losing file being moved to a conflict copy.

2. **Modification time:** The file with the **older** mtime is the loser (gets
   renamed). Newer file wins.

3. **Device ID tiebreaker:** If mtimes are equal, the file from the device with
   the **larger** first-63-bits device ID is the loser.

### Conflict file naming

```
<filename>.sync-conflict-<YYYYMMDD>-<HHMMSS>-<modifiedBy>.<ext>
```

- `<modifiedBy>`: 7-character base32 string from the first 64 bits of the
  losing device's ID.
- The original extension is preserved after the conflict metadata.
- Example: `notes.sync-conflict-20210507-080621-CEIVOCO.txt`

Case conflicts use a distinct pattern:
`<filename>.case-conflict-<timestamp>-<deviceID>.<ext>`

### Conflict copy propagation

Conflict copies are treated as normal files after creation -- they sync to all
devices in the cluster. This is intentional: the conflict was detected on one
device, but all devices had the same concurrent state.

---

## 5. Conflict settings

### maxConflicts (per-folder)

Controls the maximum number of conflict copies kept per file:

| Value | Behavior |
|-------|----------|
| `10` (default) | Keep up to 10 conflict copies per file |
| `-1` | Unlimited conflict copies |
| `0` | Disable conflict copies entirely (loser silently discarded) |

Configured in `config.xml` within the `<folder>` element:

```xml
<folder id="myfiles" ...>
    <maxConflicts>10</maxConflicts>
</folder>
```

This setting is **local to each device** -- must be configured on every device.

### What does NOT exist

- No global conflict priority setting.
- No per-device "always win" priority.
- No configurable resolution strategy beyond `maxConflicts`.
- No built-in merge tool, conflict list view, or resolution workflow.
- No conflict notification mechanism.

Users must manually find and resolve `.sync-conflict-*` files.

---

## 6. Send-only and receive-only folders

### Send Only ("folder master" pattern)

- Changes from other devices are **ignored**. Changes are received (folder may
  show "out of sync") but never applied locally.
- A red **"Override Changes"** button appears when out of sync. Clicking it
  enforces local state on the entire cluster: remote modifications overwritten,
  files not present locally deleted everywhere.
- **Conflicts do not arise** on the send-only device.
- This is the intended mechanism for a "reference copy" or "master copy."

### Receive Only

- Local changes are not distributed to other devices.
- If a locally modified file is subsequently modified by the cluster, a conflict
  occurs. The **cluster version always wins**.
- A **"Revert Local Changes"** button deletes local additions and re-syncs from
  the cluster.

### Master copy pattern for hub-and-spoke

To create a topology with one authoritative source:

1. Set the master device's folder to **Send Only**.
2. Set spoke folders to **Receive Only** (or Send & Receive if bidirectional
   sync is needed).
3. Use "Override Changes" on the master to push its state when conflicts
   accumulate.

**For our use case** (bidirectional sync of user folders across workstations),
all devices including the hub should use **Send & Receive** -- the hub is a
relay, not an authority.

---

## 7. Conflict prevention strategies

### From official documentation and community consensus

1. **Keep devices online and connected.** The primary cause of conflicts is
   divergent edits while disconnected. Continuous connectivity propagates changes
   before conflicts arise.

2. **Use a star topology.** Routing all sync through a central always-on hub
   reduces the window for concurrent edits (single serialization point).

3. **Avoid editing the same file on multiple devices** before sync completes.
   For user data folders (Documents, Pictures, etc.) this is naturally the case
   -- users typically work on one machine at a time.

4. **Enable file versioning** (Staggered recommended) to retain previous
   versions as merge bases for manual resolution.

5. **For text files, use three-way merge tools.** Community tools leverage
   `git merge-file` with Syncthing's `.stversions/` backups as the common
   ancestor. See
   [Rafael Epplee's article](https://www.rafa.ee/articles/resolve-syncthing-conflicts-using-three-way-merge/)
   and [syncthing-resolve-conflicts](https://github.com/dschrempf/syncthing-resolve-conflicts).

6. **For rapidly-changing files** (database files, lock files), set
   `maxConflicts=0` or use `.stignore` to exclude them.

### Hub-and-spoke advantage for conflicts

A star topology with an always-on hub naturally reduces conflicts because:

- The hub is always available to accept changes immediately.
- Changes are serialized through the hub -- spoke A's edit reaches the hub
  before spoke B can create a concurrent version (assuming spoke B is also
  connected).
- The conflict window shrinks to: the propagation delay from spoke A → hub →
  spoke B (typically seconds on a LAN).

---

## 8. .stignore and conflict file management

### Ignoring conflict files

```
(?d)*.sync-conflict-*
```

The `(?d)` prefix allows Syncthing to delete these files if they block directory
deletion.

### Shared patterns across devices

`.stignore` is **never synced** between devices. Use `#include` with a synced
file:

```
# .stignore (not synced)
#include .stglobalignore
```

```
# .stglobalignore (this IS synced)
(?d)*.sync-conflict-*
(?d)*.case-conflict-*
```

### Caveat

Adding an ignore pattern after conflict files exist stops future syncing of
them, but existing conflict files on each device remain and must be manually
deleted.

---

## 9. Directory-level conflicts and edge cases

### File addition vs. directory deletion

File additions and directory deletions are tracked as separate file-level
operations. Post-2.0 (where deletes can win), the outcome depends on version
vector comparison -- the delete may win, creating a conflict copy of the added
file.

### .stfolder marker

If the `.stfolder` marker is deleted (e.g., by cleaning software), Syncthing
assumes the folder has encountered an error and stops syncing. When `.stfolder`
reappears, all locally missing files are treated as deletions and propagated.
**This is a known footgun.**

### No move detection

Syncthing treats file moves as delete + create. Depending on scan order, this
can cause full re-downloads rather than local moves.

### Case sensitivity across platforms

When syncing between case-sensitive (Linux ext4) and case-insensitive (macOS
APFS default) filesystems, case-only renames (e.g., `foo.txt` → `Foo.txt`) can
cause persistent sync issues and `.case-conflict-*` files. The `caseSensitiveFS`
advanced option enables safety checks but does not eliminate all edge cases.

### Symlinks

Syncthing syncs the symlink pointer but not the target content on Linux/macOS.
On Windows, symlinks are not synced at all. Cross-platform symlink sync
frequently leads to "out of sync" states.

---

## 10. Running the hub on a home server

This is a widely practiced and community-recommended configuration. The critical
requirement: the hub must be **always on** -- if the hub is offline, no syncing
happens between any spokes.

### Recommended setup

| Component | Configuration |
|-----------|--------------|
| Hub | Always-on home server (NAS, RPi, VM, Docker) |
| Listening address | `tcp://0.0.0.0:22000` on hub; `tcp://<hub-ip>:22000` on spokes |
| Discovery | Disable Global Discovery on all devices for fully private network |
| Relay | Disable relaying on LAN; or run private `strelaysrv` with `-pools="" -token=<random>` for remote access |
| Introducer | Optional; skip for strict star topology with 2-3 devices |
| File versioning | Enable Staggered on hub (canonical data copy) |
| Systemd | `Restart=always` for reliability |
| Docker | Persistent volumes for config/certs; `--restart=always` |

### Fully private network (no public infrastructure)

Following [Brandon Rozek's guide](https://brandonrozek.com/blog/private-syncthing-network/):

1. Run your own private relay server with a token.
2. Disable Global Discovery on all devices.
3. Hardcode device addresses with static IPs (or Tailscale IPs).
4. Optionally disable Local Discovery for maximum isolation.

### Integration with Tailscale

For devices behind NAT (laptop on the road), use Tailscale IPs in device
addresses instead of LAN IPs. Since the repo already provisions Tailscale via
`shared/roles/vpn/`, this is a natural fit: `tcp://<tailscale-ip>:22000`.

---

## 11. Tradeoffs: hub-and-spoke vs. full mesh

| Dimension | Hub-and-spoke | Full mesh |
|-----------|--------------|-----------|
| **Configuration complexity** | Low -- only configure the hub | High -- every device must know every other |
| **Single point of failure** | Yes -- hub down = no syncing | No -- alternate paths exist |
| **Conflict window** | Narrow (serialized through hub) | Wider (concurrent edits more likely) |
| **Bandwidth on hub** | High -- all traffic flows through it | Distributed across devices |
| **Initial sync speed** | Slower -- spokes cannot pull from peers | Faster -- pull from multiple peers |
| **Device management** | Centralized | Distributed |
| **Scalability** | Hub bandwidth is bottleneck | Scales more naturally |

### Hybrid approach for resilience

Multiple community members and Syncthing developers suggest using 2-3 always-on
"hub" devices rather than a single hub. For example, a home server + a VPS both
serve as hubs, with spokes connecting to both. This gives most of the simplicity
of hub-and-spoke while eliminating the single point of failure.

---

## 12. Comparison with Seafile conflict handling

| Dimension | Syncthing | Seafile |
|-----------|-----------|---------|
| **Detection** | Version vectors (concurrent = conflict) | First-to-server-wins |
| **Winner selection** | Newer mtime wins, device ID tiebreak | First upload wins |
| **Conflict naming** | `.sync-conflict-<date>-<time>-<device>` | `(SFConflict <email> <timestamp>)` |
| **Content-aware** | Yes (skips identical content) | No (identical content still conflicts) |
| **Merge support** | No (community tools exist) | No (explicitly will not be added) |
| **Max conflicts** | Configurable per folder | No limit setting |
| **Folder types** | Send-only, receive-only, send-receive | Read-only libraries |
| **File locking** | No | Yes (but locks entire library) |

**Key difference:** Syncthing's version vector approach is more principled and
detects true concurrency. Seafile's first-to-server-wins is simpler but depends
on upload timing. For a hub-and-spoke topology where the hub serializes changes,
both approaches converge in practice -- the conflict window is narrow either way.

---

## 13. Limitations and known issues

1. **No merge capability.** Syncthing picks a winner and renames the loser. No
   content-aware merge, even for text files.

2. **No conflict notification.** No alert mechanism. Must manually find
   `.sync-conflict-*` files or use external monitoring.

3. **No conflict resolution UI.** Frequently requested, not implemented.

4. **Conflict copies retain the original extension.** Applications that scan
   directories by extension will process conflict copies as normal files.

5. **Database retention for deletes.** Deleted items forgotten after six months
   (configurable via `--db-delete-retention-interval`). Devices reconnecting
   after >6 months may not receive delete propagation.

6. **No file move detection.** Moves treated as delete + create. Can cause
   unnecessary re-downloads.

7. **Memory scales with file count.** Millions of files can use 1-8 GB RAM. For
   2-3 machines syncing tens of thousands of files: manageable.

8. **v2.0 delete behavior change.** Deletes can now win conflict resolution,
   potentially surprising users who relied on "modifications always win."

---

## 14. Relevance to our use case

### What we're syncing

User data folders: Documents, Pictures, Music, Videos, Downloads. These are
characterized by:

- **Low conflict risk.** Users typically work on one machine at a time.
- **Large files.** Photos, videos, music. Block-level delta sync matters.
- **Infrequent same-file edits.** Unlike code repos or note-taking apps,
  user data folders rarely have the same file open on multiple machines.

### Why hub-and-spoke works well here

- Home server is always on -- no syncing gaps.
- 2-3 spokes is trivially manageable without the introducer feature.
- Tailscale provides NAT traversal for remote devices.
- Conflict risk is already low for this file profile; the hub further reduces it
  by serializing changes.
- The hub doubles as a canonical backup copy.

### What we do NOT need

- Untrusted device encryption (hub is self-hosted and trusted).
- The introducer feature (too few devices to justify the complexity).
- Full mesh (adds complexity without meaningful benefit for 2-3 devices).
- Git repo syncing (managed by git itself; explicitly warned against by
  community). See [syncthing-git-repos.md](syncthing-git-repos.md) for the
  full analysis of why, including the "different branches" scenario.

---

## Sources

### Official documentation

- [Understanding Synchronization](https://docs.syncthing.net/users/syncing.html)
- [Folder Types](https://docs.syncthing.net/users/foldertypes.html)
- [Syncthing Configuration](https://docs.syncthing.net/users/config.html)
- [Ignoring Files (.stignore)](https://docs.syncthing.net/users/ignoring.html)
- [Block Exchange Protocol v1](https://docs.syncthing.net/specs/bep-v1.html)
- [Introducer Configuration](https://docs.syncthing.net/users/introducer.html)
- [Untrusted (Encrypted) Devices](https://docs.syncthing.net/users/untrusted.html)
- [Relay Server](https://docs.syncthing.net/users/strelaysrv.html)
- [FAQ](https://docs.syncthing.net/users/faq.html)
- [caseSensitiveFS Advanced Option](https://docs.syncthing.net/advanced/folder-caseSensitiveFS.html)

### Source code and protocol

- [Syncthing lib/protocol Go Package](https://pkg.go.dev/github.com/syncthing/syncthing/lib/protocol)
- [PR #10207 -- Allow deleted files to win conflict resolution](https://github.com/syncthing/syncthing/pull/10207)
- [Issue #7405 -- Mark sync-conflict files with both participating devices](https://github.com/syncthing/syncthing/issues/7405)

### Community forum

- [Running Syncthing in a Star Topology](https://forum.syncthing.net/t/running-syncthing-in-a-star-topology/18096)
- [Hub & Spoke vs Mesh](https://forum.syncthing.net/t/hub-spoke-vs-mesh/452)
- [Is a "Hub and Spoke" Model Less Prone to Conflicts?](https://forum.syncthing.net/t/is-a-hub-and-spoke-model-less-prone-to-conflicts/21533)
- [Can I Set Up Syncthing Nodes as Hub/Spoke?](https://forum.syncthing.net/t/can-i-set-up-syncthing-nodes-as-hub-spoke-network/14611)
- [How Does Conflict Resolution Work?](https://forum.syncthing.net/t/how-does-conflict-resolution-work/15113)
- [2.0 Conflict Changes](https://forum.syncthing.net/t/2-0-conflict-changes/24786)
- [Sync-Conflicts](https://forum.syncthing.net/t/sync-conflicts/14400)

### Third-party resources

- [How to Set Up a Private Syncthing Network (Brandon Rozek)](https://brandonrozek.com/blog/private-syncthing-network/)
- [Resolve Syncthing Conflicts Using Three-Way Merge (Rafael Epplee)](https://www.rafa.ee/articles/resolve-syncthing-conflicts-using-three-way-merge/)
- [syncthing-resolve-conflicts (script)](https://github.com/dschrempf/syncthing-resolve-conflicts)
- [Syncthing-Ignore-Patterns (community)](https://github.com/M-Mono/Syncthing-Ignore-Patterns)
