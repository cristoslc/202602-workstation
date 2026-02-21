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

**Template fixes go upstream.** Any fix to template-level files (anything that runs *before* `first-run.sh` personalizes the repo) must be committed as a separate, pre-personalization commit — not bundled into the personalization commit. Use `git reset --soft` to reorder if needed. This ensures all future users of the template get the fix.

The personalization commit (`Initialize personalized workstation config`) should only contain envsubst token replacements and SOPS-encrypted secrets.

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
