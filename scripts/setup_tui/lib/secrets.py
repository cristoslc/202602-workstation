"""Secret field definitions and collection logic.

Ansible vars are auto-discovered by scanning role ``defaults/main.yml``
files for ``# @tui`` annotations.  See :mod:`var_scanner` for the
annotation format.

Shell secrets (exports sourced by .zshrc) start from a static base list
and are augmented by heuristic detection of unannotated shell-export
placeholders (e.g. ``OPENAI_API_KEY`` in ``templatize.sh``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .encryption import write_and_encrypt
from .runner import REPO_ROOT, ToolRunner
from .var_scanner import (
    ScannedVar,
    candidates_to_scanned_vars,
    find_unannotated_candidates,
    scan_role_defaults,
    scanned_to_ansible_vars,
    scanned_to_shell_secrets,
)

logger = logging.getLogger("setup")


@dataclass
class SecretField:
    """One secret the system consumes."""

    key: str              # Variable name (git_user_email, ANTHROPIC_API_KEY, ...)
    label: str            # Human-readable label for the prompt
    placeholder: str      # Example value shown in empty field
    description: str      # What this secret is used for
    used_by: str          # Which roles/tools consume this secret
    doc_url: str = ""     # URL to docs on how to obtain this secret
    password: bool = False  # Mask input


def _scanned_to_field(v: ScannedVar) -> SecretField:
    """Convert a ScannedVar from the role scanner into a SecretField."""
    return SecretField(
        key=v.key,
        label=v.label,
        placeholder=v.placeholder,
        description=v.description,
        used_by=f"{v.role} role",
        doc_url=v.doc_url,
        password=v.password,
    )


# ---------------------------------------------------------------------------
# Static shell-secret base list — entries with hand-tuned metadata that
# the heuristic scanner can't infer from file structure alone.
# ---------------------------------------------------------------------------

_STATIC_SHELL_SECRETS: list[SecretField] = [
    SecretField(
        key="ANTHROPIC_API_KEY",
        label="Anthropic API key",
        placeholder="sk-ant-...",
        description="API access for Claude CLI and SDK",
        used_by="claude-code role, Claude CLI",
        doc_url="https://console.anthropic.com/settings/keys",
        password=True,
    ),
    SecretField(
        key="HOMEBREW_GITHUB_API_TOKEN",
        label="GitHub token for Homebrew",
        placeholder="ghp_...",
        description="Avoids GitHub API rate limits during brew install",
        used_by="homebrew role (macOS)",
        doc_url="https://github.com/settings/tokens",
        password=True,
    ),
]


def _discover_all(
    repo_root: Path | None = None,
) -> tuple[list[SecretField], list[SecretField]]:
    """Discover all ansible vars and shell secrets.

    1. Scan role defaults for ``@tui`` annotations (authoritative).
    2. Run heuristic detection for unannotated vars that look like secrets.
    3. Merge heuristic hits into the appropriate list (ansible or shell).
    4. Prepend the static shell-secrets base list (hand-tuned metadata).

    Returns ``(ansible_vars, shell_secrets)``.
    """
    root = repo_root or REPO_ROOT
    scanned = scan_role_defaults(root)

    # --- Annotated entries (authoritative) ---
    ansible_vars = [_scanned_to_field(v) for v in scanned_to_ansible_vars(scanned)]
    shell_secrets = [_scanned_to_field(v) for v in scanned_to_shell_secrets(scanned)]

    # Start shell secrets from static base list.
    known_shell_keys = {f.key for f in shell_secrets}
    for sf in _STATIC_SHELL_SECRETS:
        if sf.key not in known_shell_keys:
            shell_secrets.append(sf)
            known_shell_keys.add(sf.key)

    # --- Heuristic: best-guess unannotated vars ---
    known_keys = {f.key for f in ansible_vars} | known_shell_keys
    candidates = find_unannotated_candidates(root, known_keys=known_keys)
    if candidates:
        guessed = candidates_to_scanned_vars(candidates)
        for v in guessed:
            sf = _scanned_to_field(v)
            if v.directive == "shell-secret":
                if sf.key not in known_shell_keys:
                    shell_secrets.append(sf)
                    known_shell_keys.add(sf.key)
            else:
                ansible_vars.append(sf)

    return ansible_vars, shell_secrets


def discover_ansible_vars(repo_root: Path | None = None) -> list[SecretField]:
    """Scan role defaults for @tui annotations + heuristic candidates."""
    ansible_vars, _ = _discover_all(repo_root)
    return ansible_vars


def discover_shell_secrets(repo_root: Path | None = None) -> list[SecretField]:
    """Static shell secrets + heuristic shell-export candidates."""
    _, shell_secrets = _discover_all(repo_root)
    return shell_secrets


# Eager evaluation at import time — the scanner is fast (pure file reads).
SHARED_ANSIBLE_VARS, SHELL_SECRETS = _discover_all()


def mask_value(value: str) -> str:
    """Show first 4 and last 4 chars of a secret for confirmation."""
    if len(value) <= 10:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def load_existing_ansible_vars(runner: ToolRunner) -> dict[str, str]:
    """Load current values from vars.sops.yml for pre-filling prompts."""
    shared_vars = REPO_ROOT / "shared" / "secrets" / "vars.sops.yml"
    current: dict[str, str] = {}
    if shared_vars.exists():
        decrypted = runner.sops_decrypt(shared_vars)
        for line in decrypted.splitlines():
            if ":" in line and not line.startswith("#") and not line.startswith("---"):
                key, _, val = line.partition(":")
                val = val.strip().strip("'\"")
                if val and val != "PLACEHOLDER":
                    current[key.strip()] = val
    return current


def load_existing_shell_exports(runner: ToolRunner) -> dict[str, str]:
    """Load current export values from secrets.zsh.sops."""
    shell_file = (
        REPO_ROOT / "shared" / "secrets" / "dotfiles" / "zsh"
        / ".config" / "zsh" / "secrets.zsh.sops"
    )
    existing: dict[str, str] = {}
    if shell_file.exists():
        content = runner.sops_decrypt(shell_file)
        if content:
            for line in content.splitlines():
                if line.startswith("export "):
                    eq_pos = line.find("=")
                    if eq_pos > 0:
                        ekey = line[len("export "):eq_pos]
                        eval_ = line[eq_pos + 1:].strip().strip('"')
                        existing[ekey] = eval_
    return existing


def save_ansible_vars(
    runner: ToolRunner, collected: dict[str, str]
) -> None:
    """Write vars.sops.yml with collected values."""
    shared_vars = REPO_ROOT / "shared" / "secrets" / "vars.sops.yml"
    yaml_lines = ["---"]
    for key, value in collected.items():
        yaml_lines.append(f'{key}: "{value}"')
    write_and_encrypt(runner, shared_vars, "\n".join(yaml_lines))


def save_shell_exports(
    runner: ToolRunner, collected: dict[str, str]
) -> None:
    """Write secrets.zsh.sops with collected export values."""
    shell_file = (
        REPO_ROOT / "shared" / "secrets" / "dotfiles" / "zsh"
        / ".config" / "zsh" / "secrets.zsh.sops"
    )
    if collected:
        lines = ["# Shell secrets -- sourced by .zshrc"]
        for ekey, eval_ in collected.items():
            lines.append(f'export {ekey}="{eval_}"')
        write_and_encrypt(runner, shell_file, "\n".join(lines))
