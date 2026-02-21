# CLAUDE.md

## Project overview

Cross-platform (macOS + Linux) workstation provisioning using Ansible, GNU Stow, and SOPS/age for secrets management. This is a **template repo** — users fork it, run `first-run.sh` to personalize, then `bootstrap.sh` to provision.

## Repo structure

- `shared/` — cross-platform roles, dotfiles, tasks, and library scripts
- `linux/`, `macos/` — platform-specific plays, roles, dotfiles, and secrets
- `scripts/` — lint, decrypt, diff, and collision-check utilities
- `tests/bats/` — shell unit tests (bats-core)
- `first-run.sh` — one-time template personalization wizard
- `bootstrap.sh` → `{linux,macos}/bootstrap.sh` — full provisioning entry point

## Commit discipline

**The personalization commit is always the final commit on the branch.** Every commit before it is clean, reusable template code. This is the upstream — anyone can fork the repo and every commit up to (but not including) personalization works out of the box.

### What is personalization?

These files — and ONLY these files — contain personalized content:

| File | Personalized content |
|------|---------------------|
| `.sops.yaml` | Real age public key (replaces `${AGE_PUBLIC_KEY}`) |
| `bootstrap.sh` | Real GitHub repo URL (replaces `${GITHUB_REPO_URL}`) |
| `README.md` | Real repo URL, username, repo name |
| `*/secrets/*.sops.*` | Encrypted with real age key |

Everything else is template code.

### Commit procedure (MUST follow for every commit)

1. **Classify your change.** If it touches ANY file not in the table above, it is a template change.
2. **Commit the template change.** Write the commit as normal.
3. **Reorder before pushing.** After every template commit, reorder so personalization is last:
   ```
   git reset --hard <hash-of-your-new-template-commit>
   git cherry-pick <personalization-commit-hash>
   git push --force-with-lease
   ```
   To find the personalization commit: `git log --oneline --all | grep "Initialize personalized"`
4. **Never push with personalization buried in the middle of the history.** If you realize template commits are stacked after personalization, stop and reorder before pushing.

### Why this matters

The commit history before personalization IS the template. If personalized content (age keys, repo URLs, encrypted secrets) appears in a template-position commit, it leaks into upstream and every future fork inherits someone else's config.

## Key conventions

- **SOPS bypass for lint/CI**: Set `ANSIBLE_VARS_ENABLED=host_group_vars` to disable the `community.sops.sops` vars plugin when running ansible-lint, ansible-playbook --check, or CI. Both `ansible.cfg` files enable it, but it requires an age key that won't exist in CI.
- **Shell scripts are testable**: Scripts use `BASH_SOURCE` source guards and env var overrides (`REPO_DIR`, `SHARED_DIR`) so bats-core can source them without executing main logic.
- **Pre-commit hooks**: SOPS encryption check, gitleaks, yamllint, shellcheck. The SOPS hook excludes `.sops.yaml` (the config file, not a secret).
- **Ansible module preference**: Use `ansible.builtin.unarchive` + `ansible.builtin.file: absent` instead of `shell: tar ... && rm`. Use `ansible.builtin.copy`/`apt_repository` instead of raw `.deb` downloads where apt repos are available.
- **Secrets hygiene**: `no_log: true` on any task that handles tokens/keys. Log rotation in `01-security.yml` pre_tasks. `HIST_IGNORE_SPACE` in `.zshrc`.

## Running checks

```
make check       # fast: shellcheck, yamllint, stow collisions, bats tests
make lint        # full: above + ansible-lint (needs ansible-core installed)
make test        # lint + bats
make test-bats   # just bats tests
```

## Common gotchas

- `.sops.yaml` is a SOPS *config* file, not an encrypted secret. Don't let hooks or patterns treat it as one.
- `bash -c 'script' arg0 arg1` — `arg0` becomes `$0`, not part of `$@`. Always use `_` as a dummy `$0` placeholder.
- `first-run.sh` must be idempotent. Guard against: existing age key, already-encrypted secrets, existing GitHub repo, SSH vs HTTPS origin URLs, empty git commits.
- `gh repo create --remote origin` sets SSH URLs. `GITHUB_REPO_URL` is HTTPS. Never compare these as strings — match on `owner/repo` instead.
