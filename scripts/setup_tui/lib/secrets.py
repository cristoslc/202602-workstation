"""Secret field definitions and collection logic.

Ansible vars are auto-discovered by scanning role ``defaults/main.yml``
files for ``# @tui`` annotations.  See :mod:`var_scanner` for the
annotation format.

Shell secrets (exports sourced by .zshrc) remain a static list because
they don't correspond to Ansible role defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .encryption import write_and_encrypt
from .runner import REPO_ROOT, ToolRunner
from .var_scanner import ScannedVar, scan_role_defaults, scanned_to_ansible_vars

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


def discover_ansible_vars(repo_root: Path | None = None) -> list[SecretField]:
    """Scan role defaults for @tui annotations and return SecretFields.

    This replaces the former static ``SHARED_ANSIBLE_VARS`` list.
    """
    root = repo_root or REPO_ROOT
    scanned = scan_role_defaults(root)
    ansible_vars = scanned_to_ansible_vars(scanned)
    return [_scanned_to_field(v) for v in ansible_vars]


# Cached result — populated on first access via get_shared_ansible_vars().
_ansible_vars_cache: list[SecretField] | None = None


def get_shared_ansible_vars(repo_root: Path | None = None) -> list[SecretField]:
    """Return the discovered Ansible vars, scanning once and caching."""
    global _ansible_vars_cache
    if _ansible_vars_cache is None:
        _ansible_vars_cache = discover_ansible_vars(repo_root)
    return _ansible_vars_cache


# Backward-compatible alias — existing code importing SHARED_ANSIBLE_VARS
# will get the dynamically-discovered list.  Eager evaluation at import
# time is fine because the annotation scanner is fast (pure file reads).
SHARED_ANSIBLE_VARS: list[SecretField] = discover_ansible_vars()


# Shell secrets -- written to secrets.zsh.sops as export statements.
# These remain static because they are shell exports, not Ansible role vars.
SHELL_SECRETS: list[SecretField] = [
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
