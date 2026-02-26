# Branch-aware code sync with Unison

**Status:** Active
**Date:** 2026-02-26
**Scope:** Design for using Unison to sync git working trees between workstations
via a hub server, with branch-level isolation. This is the **primary** mechanism
for transferring working state (including uncommitted changes) between machines.
Forgejo/git remotes become secondary (commit history and CI only).

**Depends on:** [unison-known-issues.md](unison-known-issues.md),
[syncthing-git-repos.md](syncthing-git-repos.md)

---

## Problem

You work on the same code across 2-3 machines (desktop, laptop, possibly
macOS). You need:

1. **Uncommitted work transfers** — `git push/pull` requires committing first.
   WIP commits are noisy and lose staging state.
2. **Branch isolation** — machines may be on different branches. General file
   sync tools (Syncthing, Dropbox) garble working trees when branches diverge
   (see [syncthing-git-repos.md](syncthing-git-repos.md), section 5).
3. **Sleep/wake resilience** — laptop sleeps, desktop continues working. When
   the laptop wakes, it should catch up automatically or with a single command.
4. **No git corruption** — `.git/` must never be synced between machines.

Git push/pull solves (2) and (4) but fails (1) and (3). Syncthing solves (1)
and (3) but fails (2) and risks (4). Neither is a complete solution.

## Design

### Core idea

Route working trees through a hub server, using the **branch name** as a
directory key. Two machines on the same branch converge to the same server
directory. Machines on different branches sync to different directories. `.git/`
never leaves the machine.

### Server-side layout

```
/srv/code-sync/
  <repo-name>/
    <branch>/
      <working tree files, excluding .git/>
```

Example:

```
/srv/code-sync/
  workstation/
    main/
      shared/
      linux/
      Makefile
      ...
    feature-tui-refactor/
      shared/
      linux/
      Makefile
      ...
  side-project/
    develop/
      src/
      README.md
```

Each `<repo>/<branch>/` directory is a complete working tree snapshot (minus
`.git/`). The server doesn't run git — it's a dumb file store.

### Sync flow

```
workstation A                    hub server                    workstation B
~/code/repo/  ──── Unison ────> /srv/code-sync/repo/main/ <──── Unison ──── ~/code/repo/
  (branch: main)                                                (branch: main)
  (.git/ excluded)                                              (.git/ excluded)
```

1. Wrapper script walks configured code directories, finds git repos.
2. For each repo, reads the current branch (`git symbolic-ref --short HEAD`).
3. Invokes Unison: local working tree ↔ `hub:/srv/code-sync/<repo>/<branch>/`.
4. Excludes `.git/`, build artifacts, dependency directories.

### On-demand invocation

This is **not** a daemon. Sync is triggered:

- **Explicitly:** `wsync` (all repos) or `wsync <repo>` (one repo).
- **On wake:** systemd unit triggered by `suspend.target` / macOS `sleepwatcher`.
- **Optionally on branch switch:** git `post-checkout` hook calls `wsync <repo>`.

No background process, no battery drain, no resource usage when idle.

---

## Unison profile generation

The wrapper script generates or selects a Unison profile per repo+branch pair.
Profiles can be templated or constructed dynamically.

### Static profile template (`~/.unison/code-sync.prf`)

```
# Base profile — included by per-repo profiles
batch     = true
auto      = true
prefer    = newer
times     = true
perms     = 0
owner     = false
group     = false
rsrc      = false

# Exclude .git/ and common build artifacts
ignore = Path {.git}
ignore = Name {.DS_Store}
ignore = Name {._*}
ignore = Name {*.pyc}
ignore = Name {__pycache__}
ignore = Name {node_modules}
ignore = Name {.tox}
ignore = Name {.eggs}
ignore = Name {*.egg-info}
ignore = Name {.venv}
ignore = Name {venv}
ignore = Name {build}
ignore = Name {dist}
ignore = Name {target}
ignore = Name {.cache}
ignore = Name {*.swp}
ignore = Name {*~}
```

### Dynamic invocation

Rather than generating a `.prf` file per repo+branch, the wrapper passes
roots and includes the base profile on the command line:

```bash
unison \
  /home/user/code/my-project \
  ssh://hub//srv/code-sync/my-project/feature-auth \
  -include code-sync \
  -batch -auto
```

This avoids proliferating profile files. The base `code-sync.prf` handles
all shared settings. The roots (local path and remote path with branch) are
the only dynamic parts.

---

## Wrapper script (`wsync`)

### Behavior

```
wsync              # sync all configured repos
wsync <repo>       # sync one repo by name
wsync --status     # show branch and last-sync time for each repo
```

### Pseudocode

```bash
#!/usr/bin/env bash
# wsync — branch-aware code sync via Unison

SYNC_HUB="${WSYNC_HUB:-hub}"
SYNC_ROOT="${WSYNC_ROOT:-/srv/code-sync}"
CODE_DIRS=("$HOME/code" "$HOME/Documents/code")  # configurable

find_repos() {
    for dir in "${CODE_DIRS[@]}"; do
        [[ -d "$dir" ]] || continue
        for repo in "$dir"/*/; do
            [[ -d "$repo/.git" ]] && echo "$repo"
        done
    done
}

get_branch() {
    git -C "$1" symbolic-ref --short HEAD 2>/dev/null || \
    git -C "$1" rev-parse --short HEAD  # detached HEAD fallback
}

sync_repo() {
    local repo_path="$1"
    local repo_name
    repo_name="$(basename "$repo_path")"
    local branch
    branch="$(get_branch "$repo_path")"

    # Sanitize branch name for filesystem (replace / with --)
    local safe_branch="${branch//\//__}"

    local remote_path="${SYNC_ROOT}/${repo_name}/${safe_branch}"

    echo "syncing ${repo_name} (${branch}) → ${SYNC_HUB}:${remote_path}"

    unison \
        "$repo_path" \
        "ssh://${SYNC_HUB}/${remote_path}" \
        -include code-sync \
        -batch -auto \
        -logfile "$HOME/.local/log/wsync.log"
}

# Main
if [[ -n "$1" ]]; then
    # Sync specific repo by name
    for dir in "${CODE_DIRS[@]}"; do
        if [[ -d "$dir/$1/.git" ]]; then
            sync_repo "$dir/$1"
            exit $?
        fi
    done
    echo "repo not found: $1" >&2
    exit 1
else
    # Sync all repos
    while IFS= read -r repo; do
        sync_repo "$repo"
    done < <(find_repos)
fi
```

### Branch name sanitization

Git branch names can contain `/` (e.g., `feature/auth`). These must be
sanitized for the server-side directory path. The wrapper replaces `/` with
`__`:

| Git branch | Server directory |
|---|---|
| `main` | `main/` |
| `feature/auth` | `feature__auth/` |
| `bugfix/issue-42` | `bugfix__issue-42/` |

---

## Scenario walkthroughs

### Normal workflow: sequential editing

1. Work on desktop (branch `main`), edit files, don't commit.
2. Run `wsync` (or it triggers on sleep/lock). Desktop → hub.
3. Walk to laptop. Open laptop (wake). `wsync` triggers on wake.
4. Hub → laptop. Working tree now matches desktop's state.
5. Continue editing on laptop.
6. Run `wsync`. Laptop → hub.
7. Back to desktop. `wsync` on wake. Hub → desktop.

At each step, only one machine has newer changes. Unison propagates them
cleanly. No conflicts.

### Branch switching

1. Desktop is on `main`, syncing to `hub:repo/main/`.
2. Desktop runs `git checkout feature-x`. Working tree changes.
3. `wsync` triggers (post-checkout hook or manual). Now syncing to
   `hub:repo/feature-x/`.
4. `hub:repo/main/` retains the last-synced `main` state.
5. Laptop (still on `main`) syncs with `hub:repo/main/` — unaffected.

If the laptop also checks out `feature-x`, its next `wsync` pulls from
`hub:repo/feature-x/`, picking up the desktop's changes. Clean handoff.

### Both machines on same branch, conflicting edits

Rare in practice (sequential workflow), but possible if you forget to sync
before switching machines.

1. Desktop edits `src/app.py` on `main`. Does NOT sync.
2. Laptop edits `src/app.py` on `main`. Syncs to hub.
3. Desktop syncs. Unison detects conflict: local `app.py` differs from
   hub's `app.py`, and both changed since last sync.
4. With `prefer = newer`: the more recent edit wins.
5. With `prefer = <root>`: the configured side wins.
6. With no `prefer`: Unison skips the file and reports the conflict.
   Run `unison` interactively (without `-batch`) to resolve.

The losing version is preserved if `backup = Name *` is set in the profile.

### Detached HEAD / non-branch state

If git is in detached HEAD (e.g., checking out a tag or specific commit),
`git symbolic-ref` fails. The wrapper falls back to the short commit hash:

```
hub:/srv/code-sync/repo/a1b2c3d/
```

This is intentional — detached HEAD states are transient and shouldn't
overwrite branch directories.

### New repo, first sync

The hub directory doesn't exist yet. Unison creates it automatically on the
remote side (the SSH user needs write permission to `/srv/code-sync/`).
First sync transfers the full working tree. Subsequent syncs are incremental.

---

## What Forgejo becomes

With Unison handling working-state transfer, Forgejo's role shrinks:

| Function | Before (Forgejo primary) | After (Unison primary) |
|---|---|---|
| Transfer uncommitted work | Not possible | Unison handles it |
| Transfer committed work | `git push/pull` | `git push/pull` (unchanged) |
| Branch isolation | Git handles it | Directory-based on hub |
| Sleep/wake continuity | Manual push/pull | Automatic via wake trigger |
| CI/CD | Forgejo Actions | Forgejo Actions (unchanged) |
| Code review / PRs | Forgejo web UI | Forgejo web UI (unchanged) |
| Backup of committed history | Forgejo repos | Forgejo repos (unchanged) |

Forgejo is still useful for committed history, CI, and code review. But it's
no longer the mechanism you reach for when switching machines mid-task.

---

## Server-side setup

### Directory structure and permissions

```bash
# On the hub server
sudo mkdir -p /srv/code-sync
sudo chown $USER:$USER /srv/code-sync
```

No special software on the server — just SSH access and Unison installed.
Unison runs the server-side process over SSH automatically (`unison -server`
is spawned by the SSH connection).

### Unison version matching

Both machines and the hub must run Unison 2.52+. The 2.52+ wire protocol
eliminates the old OCaml-version-matching requirement (see
[unison-known-issues.md](unison-known-issues.md), section 6).

### Disk usage

Each branch of each repo gets a full working tree copy on the server (minus
`.git/`). For a typical project this is tens of megabytes. Even with many
branches, disk usage is modest. Stale branch directories can be pruned
periodically:

```bash
# Find branch directories not modified in 30+ days
find /srv/code-sync -mindepth 2 -maxdepth 2 -type d -mtime +30
```

---

## Exclusion patterns

### What to exclude

| Pattern | Why |
|---|---|
| `.git` | Entire git metadata — never sync |
| `node_modules` | Reinstallable, massive |
| `__pycache__`, `*.pyc` | Python bytecode |
| `.venv`, `venv` | Python virtual environments |
| `build`, `dist`, `target` | Build output |
| `.tox`, `.eggs`, `*.egg-info` | Python packaging artifacts |
| `.cache` | Various tool caches |
| `.DS_Store`, `._*` | macOS metadata |
| `*.swp`, `*~` | Editor swap/backup files |

### What NOT to exclude

| File type | Why it should sync |
|---|---|
| Untracked source files | New files not yet `git add`-ed — this is the whole point |
| `.env` files | Per-project environment — part of working state |
| IDE config (`.vscode/`) | Workspace settings, launch configs |
| Lock files (`package-lock.json`, etc.) | Part of project state |

### Per-repo overrides

If a specific repo needs additional exclusions, add an `ignore` file:

```
# ~/code/my-project/.wsync-ignore
ignore = Name {.terraform}
ignore = Name {*.tfstate}
ignore = Name {.vagrant}
```

The wrapper can pass `-addincludefile .wsync-ignore` if the file exists.

---

## Risk assessment

### Unison-specific risks

Documented in [unison-known-issues.md](unison-known-issues.md). Key mitigations
for code sync:

| Risk | Severity | Mitigation |
|---|---|---|
| OCaml 5 silent corruption | Critical | Use pre-built binary (OCaml 4.14). Brew cask on macOS, GitHub release on Linux. |
| No macOS fsmonitor | N/A | On-demand invocation — no fsmonitor needed |
| Memory scaling | Low | Code repos are small (thousands of files, not hundreds of thousands) |
| Version mismatch | Low | Pin 2.53.x everywhere via Ansible |

### Architecture risks

| Risk | Severity | Mitigation |
|---|---|---|
| Simultaneous edits on same branch | Medium | Sequential workflow discipline. `prefer = newer` auto-resolves. Unison backup preserves losing version. |
| Stale server directories | Low | Periodic pruning cron job |
| Hub server unavailable | Medium | Fall back to `git push/pull` for committed work. Uncommitted work stays local until hub returns. |
| Branch name collisions after sanitization | Very low | `__` delimiter is unlikely in branch names. Document the convention. |
| Sensitive files syncing to hub | Medium | Hub is your own server (same trust as SSH access). Add `.wsync-ignore` for truly sensitive per-machine files. |

### Compared to alternatives

| Approach | Uncommitted work? | Branch-safe? | Sleep/wake? | Corruption risk? |
|---|---|---|---|---|
| **Unison code sync (this design)** | Yes | Yes (directory isolation) | Yes (wake trigger) | None (`.git/` excluded) |
| Git push/pull | No (must commit) | Yes | No (manual) | None |
| Syncthing (full repo) | Yes | No (breaks `.git/`) | Yes | **High** |
| Syncthing (`.git/` excluded) | Yes | No (garbles working tree) | Yes | Medium |
| rsync both directions | Yes | With scripting | With scripting | Low (no conflict detection) |

---

## Implementation path

1. **Install Unison 2.53.x** on all machines and hub via Ansible role.
   macOS: `brew install --cask unison-app` (OCaml 4.14 binary).
   Linux: GitHub release binary or distro package (verify OCaml version).
   Hub: same as Linux workstation.

2. **Create base Unison profile** (`~/.unison/code-sync.prf`) via Ansible
   template. Shared settings, exclusion patterns.

3. **Write `wsync` wrapper script.** Shell script in `shared/dotfiles/bin/`
   (deployed via Stow). Handles repo discovery, branch detection, Unison
   invocation.

4. **Set up hub directory** (`/srv/code-sync/`). Ansible task on the server
   role.

5. **Wire up wake trigger.** Linux: systemd unit after `suspend.target`.
   macOS: `sleepwatcher` + `~/.wakeup` script.

6. **Optional: git post-checkout hook.** Auto-sync on branch switch.
   Place in `shared/dotfiles/git/hooks/` or configure via
   `core.hooksPath`.

7. **Optional: pruning cron.** Remove branch directories older than N days.

---

## Open questions

1. **Config file for repo list vs. auto-discovery.** The pseudocode above
   walks `~/code/*/`. A config file (`~/.config/wsync/repos`) would be more
   explicit but requires maintenance. Auto-discovery is zero-config but may
   find repos you don't want to sync. Leaning toward auto-discovery with an
   opt-out ignore file.

2. **Conflict policy default.** `prefer = newer` is simple and works for
   sequential editing. But if you edit the same file on two machines without
   syncing, you silently lose one version. Alternative: no `prefer`, let
   Unison skip conflicts, require interactive resolution. The backup mechanism
   preserves the losing version either way.

3. **Depth of repo discovery.** Should the wrapper find nested repos
   (`~/code/org/repo/`)? One level is simple. Recursive discovery adds
   complexity and may find submodules. Start with one level, make depth
   configurable.

4. **Server-side deduplication.** Multiple branches of the same repo share
   most files. The server stores full copies of each branch directory. For
   small-to-medium repos this is fine. For very large repos, could use
   filesystem-level dedup (btrfs, ZFS) or accept the storage cost.
