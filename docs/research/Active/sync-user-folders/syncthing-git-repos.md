# Syncthing and git repositories: interaction analysis

**Status:** Active
**Date:** 2026-02-25
**Scope:** Detailed analysis of what happens when Syncthing syncs directories
containing git repositories. Covers `.git/` internals, failure modes,
community consensus, workarounds, the "different branches" scenario, and
alternatives.

---

## 1. What happens when Syncthing syncs a git repo on different branches

### What `git checkout` changes on disk

When you run `git checkout <branch>`, git modifies the following:

| File/directory | What changes | Format |
|---|---|---|
| `.git/HEAD` | Updated to `ref: refs/heads/<branch>` | Plain text, ~30 bytes |
| `.git/index` | Rebuilt to match the target commit's tree | Binary, can be several MB |
| `.git/logs/HEAD` | New reflog entry appended | Plain text, append-only |
| Working tree files | Added, modified, or deleted to match the branch | Various |

Files that do **not** change: `.git/refs/heads/*` (branch pointers stay put),
`.git/objects/*` (immutable content-addressed store).

### The collision sequence

Suppose Machine A is on `main` and Machine B is on `feature-branch`:

1. **Machine A checks out `main`.** Git writes `ref: refs/heads/main` into
   `.git/HEAD`, rebuilds `.git/index`, updates the working tree, appends to
   `.git/logs/HEAD`.

2. **Machine B checks out `feature-branch`.** Same files are written, but with
   different content (`ref: refs/heads/feature-branch` in HEAD, different index
   contents, different working tree files).

3. **Syncthing sees the changes on both sides.** It detects that `.git/HEAD`,
   `.git/index`, `.git/logs/HEAD`, and various working tree files differ. Since
   Syncthing syncs file-by-file (not atomically per directory), it begins
   propagating individual file changes.

4. **Result: corrupted `.git/` state.** The `.git/HEAD` from one machine
   arrives while the `.git/index` from the other is still in transit. The
   repository is now internally inconsistent -- HEAD says one branch, the index
   describes a different tree, and the working tree is a mix of files from both
   branches. Any git command that reads both HEAD and the index will fail or
   produce nonsensical output.

5. **Syncthing conflict files appear.** For files modified on both sides,
   Syncthing creates `.sync-conflict-<date>-<id>` copies. Users have reported
   conflict files for `.git/HEAD`, `.git/index`, `.git/COMMIT_EDITMSG`,
   `.git/logs/HEAD`, and `.git/refs/heads/*`.

### Why this is fundamentally broken

Syncthing's creator Jakob Borg states it plainly:

> "The answer to the topic question 'Can syncthing reliably sync local Git
> repos?' is definitely **no**."

Source: [Can syncthing reliably sync local Git repos?](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404)

The core issue: git's `.git/` directory has internal invariants (HEAD must point
to a valid ref, the index must be consistent with HEAD's tree, reflogs must be
append-only). Syncthing treats each file independently and has no concept of
these cross-file invariants.

---

## 2. The `.git/` directory problem: specific files and failure modes

### File-by-file breakdown

| File | Role | Why syncing breaks it |
|---|---|---|
| `.git/HEAD` | Points to current branch (`ref: refs/heads/main`) or detached commit hash | If synced while another machine has a different branch checked out, HEAD becomes inconsistent with the local index and working tree. Produces `fatal: bad object HEAD`. |
| `.git/index` | Binary staging area; maps file paths to blob SHA-1s with timestamps | The index is tightly coupled to the working tree. Syncing an index from another machine where different files exist causes `git status` to report phantom changes or fail outright. The binary format makes partial sync especially dangerous. |
| `.git/refs/heads/*` | Branch tip pointers (plain text SHA-1 hashes) | If two machines advance different branches, Syncthing creates conflict copies. The Edinburgh Hacklab analysis found these are the *primary* conflict files: `refs/heads/master`, `logs/refs/heads/master`, `logs/HEAD`. |
| `.git/refs/remotes/*` | Remote tracking refs | Same conflict pattern as local refs when `git fetch` runs on different machines at different times. |
| `*.lock` files (`index.lock`, `HEAD.lock`, `refs/heads/*.lock`) | Git's concurrency control; created during write operations, deleted on completion | Syncthing may sync a lock file to another machine, blocking all git operations there with `fatal: Unable to create '.git/index.lock': File exists`. If the originating machine finishes and deletes the lock, Syncthing then deletes it on the remote -- but timing is unpredictable. |
| `.git/objects/` (loose objects) | Content-addressed blobs, trees, commits (`objects/ab/cdef1234...`) | Theoretically safe to sync because SHA-1 naming means identical content = identical filename. However, if Syncthing catches a half-written object (git writes to a temp file then renames), it may propagate a truncated object. This produces `fatal: loose object is corrupt`. |
| `.git/objects/pack/` (packfiles) | Compressed collections of objects (`.pack` + `.idx` pairs) | Packfiles are large binary files. A `git gc` on one machine rewrites the entire pack. If Syncthing syncs the `.pack` but not the matching `.idx` (or vice versa), git cannot read the pack. Partial sync of a multi-MB packfile mid-write causes corruption. |
| `.git/COMMIT_EDITMSG` | Last commit message (used by editors) | Benign conflict, but creates noise. Users report multiple `.sync-conflict` copies. |
| `.git/logs/*` (reflogs) | Append-only history of ref changes | Syncthing may interleave entries from different machines, corrupting the reflog. Not fatal but makes `git reflog` unreliable for recovery. |
| `.git/config` | Repository configuration (remotes, settings) | Generally safe if identical across machines, but per-machine settings (credential helpers, core.autocrlf on mixed OS) will conflict. |

### Documented failure modes

1. **`fatal: bad object HEAD`** -- HEAD points to a commit hash that does not
   exist in the local object store (synced from another machine that has
   different objects).

2. **`fatal: Unable to create '.git/index.lock': File exists`** -- A lock file
   from another machine was synced before the originating machine deleted it.

3. **`fatal: loose object is corrupt`** -- A half-written object file was synced
   mid-write.

4. **Corrupted packfiles** -- Partial sync of `.pack`/`.idx` pairs.
   `git verify-pack` fails. Recovery requires `git repack` or re-clone.

5. **Phantom changes in `git status`** -- Index from machine A + working tree
   from machine B = git reports every file as modified.

6. **Sync-conflict file pollution** -- Opaque `.sync-conflict-*` files
   scattered throughout `.git/`, making manual resolution nearly impossible
   without deep git internals knowledge.

### Sources

- [Resolving sync conflicts in git folder](https://forum.syncthing.net/t/resolving-sync-conflicts-in-git-folder/11969) -- User reports conflict files in `.git/index`, `.git/HEAD`, `.git/logs/HEAD`, `.git/refs/heads/`
- [When Git on Dropbox conflicts](https://edinburghhacklab.com/2012/11/when-git-on-dropbox-conflicts-no-problem/) -- Technical analysis showing conflicts limited to `refs/heads/master`, `logs/HEAD`, `logs/refs/heads/master`
- [Corrupted files after synchronization (issue #9262)](https://github.com/syncthing/syncthing/issues/9262) -- Reports of files filled with zeroes after Syncthing sync
- [Git index.lock file](https://learn.microsoft.com/en-us/azure/devops/repos/git/git-index-lock) -- Microsoft documentation on the lock file mechanism

---

## 3. Community consensus

### Official maintainer statements

**Jakob Borg (calmh)**, Syncthing creator and lead maintainer:

> "The answer to the topic question 'Can syncthing reliably sync local Git
> repos?' is definitely **no**."

Source: [forum.syncthing.net/t/8404](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404)

> "You can, and it'll sync just fine, but you _shouldn't_. A Git
> repository...is made up of a bunch of files that should be internally
> consistent with each other."

Source: [forum.syncthing.net/t/1774](https://forum.syncthing.net/t/is-putting-a-git-workspace-in-a-synced-folder-really-a-good-idea/1774)

> "if you have to ask, the answer is no."

Source: [forum.syncthing.net/t/8404](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404)

On the atomic directory feature request that would have made `.git/` syncing
safer:

> "I'll think about it for a while but my gut reaction is 'ugh no'."

Source: [github.com/syncthing/syncthing/issues/4608](https://github.com/syncthing/syncthing/issues/4608)

**Simon Frei (imsodin)**, Syncthing project member:

> "you should not sync git repos (at least not the .git dir)."

Source: [forum.syncthing.net/t/15489/2](https://forum.syncthing.net/t/gitingore-supported/15489/2)

Closed the atomic directory sync request for git as "out-of-scope for
Syncthing":

Source: [github.com/syncthing/syncthing/issues/7627](https://github.com/syncthing/syncthing/issues/7627)

**Audrius Butkevicius**, Syncthing maintainer:

On ignoring VCS directories by default: "I don't think there will ever be a
feature like that, and you'll always have to exclude them manually."

On atomic directory sync: "So I say no, because this is an absurdly racy can
of worms, which would require pretty much rewriting how syncthing works."

Source: [github.com/syncthing/syncthing/issues/7215](https://github.com/syncthing/syncthing/issues/7215), [github.com/syncthing/syncthing/issues/4608](https://github.com/syncthing/syncthing/issues/4608)

### Experienced community members

**canton7**:

> "They're rare, but they occur when you put a git repository into any sort
> of synchronized folder (Dropbox, etc). Lots of small files changing often
> tend to confuse file synchronization tools a bit, and you end up with
> repository corruption sooner or later."

> "I've had git repositories mess up in a big way when there's just 1 of me
> using Syncthing."

Source: [forum.syncthing.net/t/8404/12](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404/12)

**lfam**:

> "Syncthing doesn't understand anything about how Git wants to use its
> internal metadata, and will naively sync all the various files between
> nodes."

Source: [forum.syncthing.net/t/8404](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404)

### Summary of stance

| Aspect | Position |
|---|---|
| Syncing `.git/` directories | Explicitly warned against by creator and all maintainers |
| Auto-ignoring `.git/` by default | Rejected; users must configure `.stignore` manually |
| Atomic directory sync (which would help) | Rejected as "out of scope" |
| Recommended alternative | Use git's own push/pull mechanisms |

The community position is clear and consistent: **do not sync `.git/`
directories with Syncthing**. This is not a theoretical concern but a
documented source of data loss.

---

## 4. Workarounds people actually use

### 4a. `.stignore` patterns for `.git/` (sync working tree only)

The most common approach: ignore `.git/` and sync only the working tree files.
Each machine maintains its own independent `.git/` directory and uses git
push/pull to a shared remote for version control synchronization.

**Minimal `.stignore`:**

```
.git
```

This pattern matches `.git` directories at any depth in the folder hierarchy.
The `**/.git` form is redundant because Syncthing's pattern matching already
matches `foo` at all directory levels.

**Development-oriented `.stignore` (also ignoring build artifacts):**

```
// Version control
.git

// Build artifacts and dependencies
node_modules
__pycache__
*.pyc
build
dist
target
.tox
.eggs
*.egg-info

// IDE/editor directories
.vscode
.idea
*.swp
*~

// OS files
(?d).DS_Store
(?d)Thumbs.db
```

The `(?d)` prefix allows Syncthing to delete these files if they block
directory removal.

**Partially syncing `.git/`:** One forum user asked about ignoring `.git/` but
still syncing `.git/config`. This is technically possible with negation patterns:

```
.git
!.git/config
```

However, this causes Syncthing to traverse the otherwise-ignored `.git/`
directory (to check for the negated pattern), which partially defeats the
purpose and may cause the filesystem watcher to monitor `.git/` contents.

Sources:
- [Ignoring Files -- Syncthing documentation](https://docs.syncthing.net/users/ignoring.html)
- [How to ignore .git but still sync .git/config](https://forum.syncthing.net/t/how-to-ignore-git-but-still-sync-git-config-for-all-my-projects/17005)
- [Useful .stignore Patterns](https://forum.syncthing.net/t/useful-stignore-patterns/1175)

### 4b. Ignoring the entire repo and using git push/pull instead

Some users exclude entire project directories from Syncthing and rely
exclusively on git remotes. This is the safest approach when the full project
is under version control.

Jakob Borg on syncing repos between devices:

> "git isn't a great example [for file sync] to be honest -- it's
> specifically designed to be used in a distributed manner."

Source: [forum.syncthing.net/t/13886](https://forum.syncthing.net/t/idea-for-handling-git-repos-and-other-similar-directories/13886)

**Approach:** Set up a central git server (GitHub, Gitea, self-hosted bare
repo) and use `git push`/`git pull` on each machine. This preserves full
history, supports branching, and uses git's own merge conflict resolution.

### 4c. Using Syncthing for non-git project files only

A hybrid approach: use git for source code, Syncthing for binary assets
and data files that git handles poorly.

From the forum:

> "Use Syncthing for ALL sync instead of git. Use git for version control,
> which is where it really shines."

Source: [forum.syncthing.net/t/23160](https://forum.syncthing.net/t/mixing-git-and-syncthing/23160)

**Implementation patterns:**

- Git tracks code; Syncthing syncs large binary assets (images, models,
  datasets) that would bloat the git repo.
- `.gitignore` excludes the Syncthing-managed assets directory.
- `.stignore` excludes `.git/` and potentially build artifacts.
- The two tools operate on complementary file sets within the same project
  directory.

Alternatives for the binary side: `git-lfs` or `git-annex` may be preferable
if you want everything under version control. Maintainer Jakob Borg suggested:
"Check if maybe git-lfs or git-annex is a better fit."

### 4d. Other documented approaches

**One-machine-at-a-time discipline:** Some users sync `.git/` but enforce a
strict workflow: only work on one machine at a time, wait for Syncthing to
fully sync before switching machines. This reduces (but does not eliminate)
the risk. A git operation that happens to coincide with Syncthing syncing
incoming changes can still corrupt the repo.

**Send-only/receive-only folder types:** Configure Syncthing so one machine
is "send-only" and the other is "receive-only." This prevents bidirectional
conflicts but means only one machine can originate changes.

**Backup-only (ignoring `.git/` on backup target):** Use Syncthing one-way
to back up repositories to a storage server, accepting that the backup copy
is read-only and may occasionally be inconsistent.

---

## 5. The "different branches" scenario with `.git/` ignored

This is the scenario where `.git/` is in `.stignore` and only the working
tree is synced. Machine A is on `main`, Machine B is on `feature-branch`.

### What Syncthing sees and does

With `.git/` ignored, Syncthing only operates on the working tree files
(source code, configs, assets, etc.). It has no knowledge of branches, commits,
or git state.

### Step-by-step analysis

**Starting state:** Machine A and Machine B both have the same working tree
(e.g., both were on `main` at the same commit).

**Machine A stays on `main`.** Makes some edits to `file1.py`.

**Machine B checks out `feature-branch`.** Git modifies the working tree:
some files are added, some modified, some deleted to match the `feature-branch`
state. This is invisible to Syncthing regarding *why* it happened -- Syncthing
just sees files changing on disk.

**Syncthing reacts:**

1. Files that exist on A but were deleted by B's checkout: Syncthing sees a
   deletion on B and a modification on A. If A's version is newer, A "wins"
   and the file reappears on B. If B's deletion is newer, the file disappears
   on A.

2. Files that were modified on both sides (A's edits + B's branch checkout):
   Syncthing creates `.sync-conflict-*` files for the loser.

3. Files that only changed on one side: synced normally to the other machine.

**End state:** Both machines end up with a hybrid working tree -- a mix of
files from `main` and `feature-branch`, plus `.sync-conflict-*` files. Neither
machine's working tree matches any commit in the repository.

### Impact on git operations

On each machine, `git status` will report:

- **Modified files:** Files that Syncthing overwrote with the other machine's
  version show as "modified" relative to the locally checked-out branch.
- **Untracked files:** Any `.sync-conflict-*` files show up as untracked.
- **Deleted files:** Files that Syncthing deleted (because the other machine's
  branch deleted them) show as deleted.

The local `.git/` directory is unaffected and still correctly tracks its own
branch. But the working tree no longer matches any known state. Running
`git checkout -- .` or `git restore .` will reset the working tree to match
the local branch, but Syncthing will then see those changes and propagate
them back to the other machine, restarting the cycle.

### What about uncommitted changes?

Uncommitted changes are just modified files on disk. Syncthing syncs them
like any other file change. If Machine A has uncommitted edits to `app.py`,
those edits land on Machine B's working tree. On Machine B, `git status` shows
`app.py` as modified (relative to whatever branch B has checked out).

### What about staged files?

Staged files exist in the `.git/index`, which is ignored. The working tree
copy of a staged file is the same as the staged version (unless the user made
further edits after staging). So staged content syncs via the working tree
copy, but the *staging state* does not sync (it lives in the ignored index).

### What about untracked files?

Untracked files (new files not yet `git add`-ed) sync normally via Syncthing.
They appear as untracked on the other machine too. This is actually the
least problematic case.

### Bottom line

Syncing working trees with `.git/` ignored across machines on different
branches is **not viable for normal development**. The working tree becomes a
garbage mix of two branch states. It is only workable if:

- Both machines are always on the same branch, AND
- You only edit on one machine at a time, AND
- You wait for Syncthing to finish syncing before switching machines.

Even then, you lose the ability to use `git stash`, `git checkout`, or any
operation that modifies the working tree without it being propagated to the
other machine.

---

## 6. Alternatives for code synchronization

### 6a. Git itself (push/pull/remotes)

**The recommended approach.** Git was designed for distributed development.

- Set up a remote (GitHub, GitLab, Gitea, bare repo over SSH).
- `git push` from the machine you are working on.
- `git pull` (or `git fetch` + `git merge`) on the machine you switch to.
- Full branch support, merge conflict resolution, history preservation.
- Works offline (commit locally, push when connected).

**Drawback:** Requires explicit push/pull; not automatic. Uncommitted work
does not transfer (must commit or use `git stash` + manual transfer).

### 6b. Git worktrees for multiple branches

`git worktree` creates additional working directories linked to the same
repository. Each worktree can have a different branch checked out
simultaneously.

```
git worktree add ../project-feature feature-branch
git worktree add ../project-hotfix hotfix-branch
```

- All worktrees share the same `.git` repository (object store, refs).
- Commits in any worktree are immediately visible to all others.
- Each branch can only be checked out in one worktree at a time.
- Worktrees are lightweight -- no full clone needed.

**Use case:** When you need to work on multiple branches on the *same*
machine without stashing. Does not solve cross-machine sync, but eliminates
the "different branches" problem locally.

Source: [git-scm.com/docs/git-worktree](https://git-scm.com/docs/git-worktree)

### 6c. VS Code Remote SSH

Opens a remote folder over SSH; the VS Code Server runs on the remote machine.
No file sync needed -- code stays on one machine.

- Full IDE features (IntelliSense, debugging, terminal) on remote code.
- No sync conflicts possible (single source of truth).
- Requires constant network connection.
- Tied to VS Code as the editor.

Source: [code.visualstudio.com/docs/remote/ssh](https://code.visualstudio.com/docs/remote/ssh)

### 6d. rsync / Unison for ad-hoc sync

`rsync` provides one-way or bidirectional file sync with delta transfer.
`unison` provides bidirectional sync with conflict detection.

- More control than Syncthing (explicit invocation, not continuous).
- Can exclude `.git/` with `--exclude` flags.
- No background daemon required.
- Must be invoked manually or via cron/watch scripts.

### 6e. SSH + git stash/patch for uncommitted work

For transferring uncommitted work between machines:

```
# On source machine
git diff > /tmp/work.patch
# Transfer patch file (scp, email, etc.)

# On target machine
git apply /tmp/work.patch
```

Or using `git stash`:

```
# On source machine
git stash create > /tmp/stash-ref.txt
git stash show -p > /tmp/stash.patch

# On target machine
git apply /tmp/stash.patch
```

### 6f. Comparison matrix

| Approach | Automatic? | Supports branches? | Handles uncommitted work? | Offline? | Risk of corruption? |
|---|---|---|---|---|---|
| Syncthing (full repo) | Yes | No (breaks) | Yes (syncs files) | Yes | **High** |
| Syncthing (working tree only) | Yes | No (garbles) | Yes (syncs files) | Yes | Medium (working tree confusion) |
| Git push/pull | No (manual) | Yes | No (must commit) | Partial | None |
| Git worktree | N/A (local) | Yes (per directory) | N/A (local) | N/A | None |
| VS Code Remote SSH | N/A (no sync) | Yes | Yes | No | None |
| rsync/Unison | Semi (scriptable) | With exclusions | Yes | Yes | Low |
| Git patch transfer | No (manual) | Yes | Yes | Yes | None |

---

## Sources index

### Syncthing forum threads

- [Can syncthing reliably sync local Git repos?](https://forum.syncthing.net/t/can-syncthing-reliably-sync-local-git-repos-not-github/8404)
- [Is putting a Git workspace in a synced folder really a good idea?](https://forum.syncthing.net/t/is-putting-a-git-workspace-in-a-synced-folder-really-a-good-idea/1774)
- [Resolving sync conflicts in git folder](https://forum.syncthing.net/t/resolving-sync-conflicts-in-git-folder/11969)
- [Mixing git and syncthing](https://forum.syncthing.net/t/mixing-git-and-syncthing/23160)
- [Thoughts on .git and .thunderbird and ignoring](https://forum.syncthing.net/t/thoughts-on-git-and-thunderbird-and-ignoring/18755)
- [Idea for handling git repos and other similar directories](https://forum.syncthing.net/t/idea-for-handling-git-repos-and-other-similar-directories/13886)
- [Ignore sync'ing a git repo](https://forum.syncthing.net/t/ignore-syncing-a-git-repo/11058)
- [How to ignore .git but still sync .git/config](https://forum.syncthing.net/t/how-to-ignore-git-but-still-sync-git-config-for-all-my-projects/17005)
- [Useful .stignore Patterns](https://forum.syncthing.net/t/useful-stignore-patterns/1175)
- [gitignore supported?](https://forum.syncthing.net/t/gitingore-supported/15489/2)

### Syncthing GitHub issues

- [#7215: Ignore version-controlled directories](https://github.com/syncthing/syncthing/issues/7215)
- [#7627: Sync git folder with consistency constraints](https://github.com/syncthing/syncthing/issues/7627)
- [#4608: Treat directory as single file, updated atomically](https://github.com/syncthing/syncthing/issues/4608)
- [#837: Ignore some files by default?](https://github.com/syncthing/syncthing/issues/837)
- [#9262: Corrupted files after synchronization](https://github.com/syncthing/syncthing/issues/9262)

### Syncthing documentation

- [Ignoring Files](https://docs.syncthing.net/users/ignoring.html)

### Git documentation and references

- [Git Internals - Git References](https://git-scm.com/book/en/v2/Git-Internals-Git-References)
- [git-checkout documentation](https://git-scm.com/docs/git-checkout)
- [git-worktree documentation](https://git-scm.com/docs/git-worktree)
- [Git index.lock file (Microsoft)](https://learn.microsoft.com/en-us/azure/devops/repos/git/git-index-lock)

### Other analysis

- [When Git on Dropbox conflicts (Edinburgh Hacklab)](https://edinburghhacklab.com/2012/11/when-git-on-dropbox-conflicts-no-problem/)
- [Using Syncthing to sync coding projects (Forrest Jacobs)](https://forrestjacobs.com/using-syncthing-to-sync-coding-projects/)
- [Resolve Syncthing conflicts using three-way merge (Rafael Epplee)](https://www.rafa.ee/articles/resolve-syncthing-conflicts-using-three-way-merge/)
- [VS Code Remote SSH documentation](https://code.visualstudio.com/docs/remote/ssh)
