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

**Template changes go upstream — personalization stays last.** The personalization commit (`Initialize personalized workstation config`) must ALWAYS be the final commit on the branch. All template-level commits — whether fixes or new features — must be ordered before it in the git history. This keeps the upstream template clean: anyone can fork the repo, and every commit up to (but not including) personalization is reusable.

Personalization-only files: `.sops.yaml` (with real age public key baked in), `bootstrap.sh` (with real repo URL), `README.md` (with real repo URL), and `*/secrets/*.sops.*` (encrypted with real key). The personalization commit should only touch these.

**When committing template changes to an already-personalized repo:**
1. Commit the template change normally (it lands after personalization)
2. Reorder: `git reset --hard <last-template-commit>`, cherry-pick template commits, then cherry-pick personalization last
3. `git push --force-with-lease` (safe when no other machines consume the repo yet)

Never bundle template code and personalization content in the same commit.

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
