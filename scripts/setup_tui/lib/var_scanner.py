"""Scan role defaults for @tui annotations and build SecretField lists.

Annotation format (placed on the line immediately before a variable):

    # @tui <directive> [flags...] [key="value"...]
    some_variable: ""

Directives:
    secret      Ansible var stored in vars.sops.yml, prompted in TUI.
    shell-secret  Shell export stored in secrets.zsh.sops.
    skip        Excluded from TUI (auto-provisioned, intentional empty, etc.).

Flags (for secret / shell-secret):
    password    Mask input in TUI.
    optional    Not required — allowed to stay empty.

Key-value overrides:
    label="..."        Human-readable label (default: auto from key name).
    placeholder="..."  Example value shown in empty field.
    description="..."  What the var is for (default: inline comment).
    doc_url="..."      URL to docs on how to obtain the value.

Variables with empty-string defaults ("") that have NO annotation are ignored
by the scanner — the @tui marker is an opt-in signal.

A separate **heuristic lint** (``find_unannotated_candidates``) scans for
empty-string vars whose names look like secrets but lack any ``@tui``
annotation, as a safety-net to catch omissions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("setup")

# ---------------------------------------------------------------------------
# Public dataclass — mirrors SecretField but adds role provenance
# ---------------------------------------------------------------------------


@dataclass
class ScannedVar:
    """A user-input variable discovered from role defaults."""

    key: str
    role: str  # role directory name (e.g., "backups", "git")
    directive: str  # "secret", "shell-secret", or "skip"
    label: str = ""
    placeholder: str = ""
    description: str = ""
    doc_url: str = ""
    password: bool = False
    optional: bool = False

    @property
    def is_secret(self) -> bool:
        return self.directive in ("secret", "shell-secret")


# ---------------------------------------------------------------------------
# Annotation parser
# ---------------------------------------------------------------------------

_ANNOTATION_RE = re.compile(r"^#\s*@tui\s+(.+)$")
_KV_RE = re.compile(r'(\w+)="([^"]*)"')
_YAML_VAR_RE = re.compile(r'^(\w+):\s*""\s*(?:#\s*(.*))?$')
_FLAGS = frozenset({"password", "optional"})
_DIRECTIVES = frozenset({"secret", "shell-secret", "skip"})


def _humanize_key(key: str) -> str:
    """Turn a variable name into a human-readable label.

    ``restic_b2_bucket`` → ``Restic B2 bucket``
    ``git_user_email`` → ``Git user email``
    """
    return key.replace("_", " ").capitalize()


def _parse_annotation(text: str) -> dict | None:
    """Parse the body of a ``# @tui ...`` comment.

    Returns a dict with keys: directive, password, optional, label,
    placeholder, description, doc_url.  Returns None on parse failure.
    """
    tokens = text.strip().split()
    if not tokens:
        return None

    directive = tokens[0]
    if directive not in _DIRECTIVES:
        logger.warning("Unknown @tui directive %r (expected one of %s)", directive, _DIRECTIVES)
        return None

    result: dict = {
        "directive": directive,
        "password": False,
        "optional": False,
        "label": "",
        "placeholder": "",
        "description": "",
        "doc_url": "",
    }

    # Extract key="value" pairs first (they may contain spaces inside quotes).
    full_text = text.strip()
    for key, value in _KV_RE.findall(full_text):
        if key in result:
            result[key] = value

    # Remaining bare words after the directive are flags.
    # Strip the directive and any kv pairs to find bare flags.
    remainder = _KV_RE.sub("", full_text)
    bare_words = remainder.split()[1:]  # skip directive
    for word in bare_words:
        if word in _FLAGS:
            result[word] = True

    return result


def _parse_defaults_file(path: Path, role_name: str) -> list[ScannedVar]:
    """Parse one defaults/main.yml and return ScannedVar entries."""
    try:
        lines = path.read_text().splitlines()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return []

    results: list[ScannedVar] = []
    pending_annotation: dict | None = None

    for line in lines:
        # Check for annotation comment.
        m = _ANNOTATION_RE.match(line.strip())
        if m:
            parsed = _parse_annotation(m.group(1))
            if parsed and parsed["directive"] != "skip":
                pending_annotation = parsed
            else:
                # skip directive or parse failure — consume and discard
                pending_annotation = None
            continue

        # Check for a YAML variable with empty-string default.
        if pending_annotation is not None:
            vm = _YAML_VAR_RE.match(line)
            if vm:
                var_key = vm.group(1)
                inline_comment = (vm.group(2) or "").strip()

                ann = pending_annotation
                label = ann["label"] or _humanize_key(var_key)
                description = ann["description"] or inline_comment
                placeholder = ann["placeholder"]

                # Try to extract placeholder from inline comment: ``e.g. "value"``
                if not placeholder and inline_comment:
                    eg_match = re.search(r'e\.g\.\s*"([^"]+)"', inline_comment)
                    if eg_match:
                        placeholder = eg_match.group(1)

                results.append(
                    ScannedVar(
                        key=var_key,
                        role=role_name,
                        directive=ann["directive"],
                        label=label,
                        placeholder=placeholder,
                        description=description,
                        doc_url=ann["doc_url"],
                        password=ann["password"],
                        optional=ann["optional"],
                    )
                )
            # Whether matched or not, consume the pending annotation.
            pending_annotation = None

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_role_defaults(repo_root: Path) -> list[ScannedVar]:
    """Scan all role defaults/main.yml under repo_root for @tui annotations.

    Searches ``shared/roles/*/defaults/main.yml``,
    ``linux/roles/*/defaults/main.yml``, and
    ``macos/roles/*/defaults/main.yml``.

    Returns a flat list of ScannedVar entries sorted by
    (directive, role, key).
    """
    results: list[ScannedVar] = []

    for pattern in [
        "shared/roles/*/defaults/main.yml",
        "linux/roles/*/defaults/main.yml",
        "macos/roles/*/defaults/main.yml",
    ]:
        for path in sorted(repo_root.glob(pattern)):
            role_name = path.parent.parent.name
            results.extend(_parse_defaults_file(path, role_name))

    results.sort(key=lambda v: (v.directive, v.role, v.key))
    return results


def scanned_to_ansible_vars(scanned: list[ScannedVar]) -> list[ScannedVar]:
    """Filter to only ``secret`` directive vars (Ansible vars for SOPS)."""
    return [v for v in scanned if v.directive == "secret"]


def scanned_to_shell_secrets(scanned: list[ScannedVar]) -> list[ScannedVar]:
    """Filter to only ``shell-secret`` directive vars."""
    return [v for v in scanned if v.directive == "shell-secret"]


# ---------------------------------------------------------------------------
# Heuristic lint — catch unannotated secrets
# ---------------------------------------------------------------------------

# Suffixes that strongly suggest a variable is a secret.
_SECRET_SUFFIXES = (
    "_api_key", "_apikey", "_token", "_password", "_passwd",
    "_secret", "_credential", "_cred", "_auth",
)

# Suffixes that look secret-ish but are typically non-sensitive.
_FALSE_POSITIVE_SUFFIXES = ("_key_id", "_public_key", "signing_key")

# Whole-name patterns for ALL_CAPS env-var style secrets.
_ALLCAPS_SECRET_RE = re.compile(
    r"^[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|AUTH_KEY|CREDENTIAL)$"
)

# Regex for shell-export lines:  ``export FOO="bar"``  or  ``export FOO=bar``
# Allows optional leading whitespace (heredocs in templatize.sh are indented).
_SHELL_EXPORT_RE = re.compile(
    r'^\s*export\s+([A-Z][A-Z0-9_]+)=["\']?(.+?)["\']?\s*$',
    re.MULTILINE,
)


class UnannotatedCandidate(NamedTuple):
    """A variable that looks like a secret but has no @tui annotation."""

    key: str
    source: str  # "role:<name>/defaults" or "shell-export:<file>"
    reason: str  # human-readable explanation of why it was flagged


def _looks_like_secret(key: str) -> str | None:
    """Return a reason string if *key* looks like a secret, else None."""
    lower = key.lower()

    # Check false-positive exclusions first.
    if any(lower.endswith(fp) for fp in _FALSE_POSITIVE_SUFFIXES):
        return None

    for suffix in _SECRET_SUFFIXES:
        if lower.endswith(suffix):
            return f"name ends with {suffix!r}"

    # Bare ``_key`` suffix (but not ``_key_id`` etc. filtered above).
    if lower.endswith("_key") and not lower.endswith("_public_key"):
        return "name ends with '_key'"

    # ALL_CAPS env-var style.
    if _ALLCAPS_SECRET_RE.match(key):
        return "ALL_CAPS name matches secret pattern"

    return None


def find_unannotated_candidates(
    repo_root: Path,
    known_keys: set[str] | None = None,
) -> list[UnannotatedCandidate]:
    """Find empty-string vars and shell exports that look like secrets but
    lack ``@tui`` annotations.

    *known_keys* is the set of keys already handled (annotated vars +
    static SHELL_SECRETS).  If ``None``, it is built from
    ``scan_role_defaults``.

    This is a **lint**, not a hard gate — results should be surfaced as
    warnings to prompt the developer to annotate (or ``@tui skip``).
    """
    if known_keys is None:
        scanned = scan_role_defaults(repo_root)
        known_keys = {v.key for v in scanned}

    candidates: list[UnannotatedCandidate] = []

    # --- Pass 1: unannotated empty-string vars in role defaults ---
    for pattern in [
        "shared/roles/*/defaults/main.yml",
        "linux/roles/*/defaults/main.yml",
        "macos/roles/*/defaults/main.yml",
    ]:
        for path in sorted(repo_root.glob(pattern)):
            role_name = path.parent.parent.name
            try:
                lines = path.read_text().splitlines()
            except OSError:
                continue

            prev_is_annotation = False
            for line in lines:
                stripped = line.strip()
                if _ANNOTATION_RE.match(stripped):
                    prev_is_annotation = True
                    continue

                vm = _YAML_VAR_RE.match(line)
                if vm and not prev_is_annotation:
                    var_key = vm.group(1)
                    if var_key not in known_keys:
                        reason = _looks_like_secret(var_key)
                        if reason:
                            candidates.append(
                                UnannotatedCandidate(
                                    key=var_key,
                                    source=f"role:{role_name}/defaults",
                                    reason=reason,
                                )
                            )
                prev_is_annotation = False

    # --- Pass 2: shell-export placeholders in templatize.sh / SOPS templates ---
    for shell_pattern in [
        "scripts/templatize.sh",
        "shared/secrets/dotfiles/**/*.sops",
    ]:
        for path in sorted(repo_root.glob(shell_pattern)):
            try:
                content = path.read_text()
            except OSError:
                continue

            for m in _SHELL_EXPORT_RE.finditer(content):
                env_key = m.group(1)
                env_val = m.group(2)
                if env_key in known_keys:
                    continue
                # Only flag if the value is a placeholder or empty.
                if env_val in ("PLACEHOLDER", "", '""', "''"):
                    reason = _looks_like_secret(env_key)
                    if reason:
                        candidates.append(
                            UnannotatedCandidate(
                                key=env_key,
                                source=f"shell-export:{path.relative_to(repo_root)}",
                                reason=reason,
                            )
                        )

    return sorted(candidates, key=lambda c: (c.source, c.key))


def _guess_password(key: str) -> bool:
    """Guess whether a variable should be masked in the TUI."""
    lower = key.lower()
    # Non-sensitive even if they end in _key
    if any(lower.endswith(fp) for fp in _FALSE_POSITIVE_SUFFIXES):
        return False
    sensitive = ("_password", "_passwd", "_secret", "_key", "_api_key",
                 "_apikey", "_token", "_credential", "_cred", "_auth")
    return any(lower.endswith(s) for s in sensitive)


def candidates_to_scanned_vars(
    candidates: list[UnannotatedCandidate],
) -> list[ScannedVar]:
    """Convert heuristic candidates into ScannedVar entries with best-guess
    metadata, suitable for merging into the TUI collection flow.

    Role-defaults candidates become ``directive="secret"``; shell-export
    candidates become ``directive="shell-secret"``.
    """
    results: list[ScannedVar] = []
    for c in candidates:
        if c.source.startswith("role:"):
            # "role:backups/defaults" → role="backups"
            role = c.source.split(":")[1].split("/")[0]
            directive = "secret"
        else:
            role = "shell"
            directive = "shell-secret"

        results.append(
            ScannedVar(
                key=c.key,
                role=role,
                directive=directive,
                label=_humanize_key(c.key),
                placeholder="",
                description=f"(auto-detected: {c.reason})",
                doc_url="",
                password=_guess_password(c.key),
                optional=True,  # best-guess entries are always optional
            )
        )
    return results
