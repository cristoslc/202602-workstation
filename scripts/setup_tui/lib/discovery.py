"""Auto-discovery of playbook phases and roles from YAML files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .runner import REPO_ROOT

logger = logging.getLogger("setup")

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredRole:
    """A single role discovered from a playbook phase."""

    name: str
    tags: tuple[str, ...]
    description: str  # auto-generated from sub-tool tags
    has_when: bool = False


@dataclass(frozen=True)
class DiscoveredPhase:
    """A single phase (play) discovered from a playbook file."""

    phase_id: str  # e.g. "system", "dev-tools"
    order: int  # e.g. 0, 1, 2
    display_name: str  # e.g. "System foundation"
    roles: tuple[DiscoveredRole, ...]
    has_pre_tasks: bool = False


@dataclass(frozen=True)
class PlaybookManifest:
    """Complete manifest of all phases for a platform."""

    platform: str
    phases: tuple[DiscoveredPhase, ...]

    def phase_ids(self) -> list[str]:
        """Return phase IDs in order."""
        return [p.phase_id for p in self.phases]

    def phase_by_id(self, phase_id: str) -> DiscoveredPhase | None:
        """Look up a phase by its ID."""
        for p in self.phases:
            if p.phase_id == phase_id:
                return p
        return None

    def roles_for_phases(self, phase_ids: list[str]) -> list[DiscoveredRole]:
        """Return all roles belonging to the given phases, in order."""
        roles: list[DiscoveredRole] = []
        for p in self.phases:
            if p.phase_id in phase_ids:
                roles.extend(p.roles)
        return roles


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_PHASE_NAME_RE = re.compile(r"^Phase\s+\d+:\s*(.+)$")


def _parse_display_name(play_name: str) -> str:
    """Strip 'Phase N: ' prefix, return remainder with original casing."""
    m = _PHASE_NAME_RE.match(play_name)
    if m:
        return m.group(1).strip()
    return play_name


def _parse_phase_id(filename: str) -> str:
    """Extract phase ID from filename like '02-dev-tools.yml' → 'dev-tools'."""
    stem = Path(filename).stem  # '02-dev-tools'
    # Strip leading NN- prefix.
    return re.sub(r"^\d+-", "", stem)


def _parse_order(filename: str) -> int:
    """Extract order number from filename like '02-dev-tools.yml' → 2."""
    m = re.match(r"^(\d+)-", Path(filename).name)
    return int(m.group(1)) if m else 0


def _make_description(tags: list[str], role_name: str, phase_id: str) -> str:
    """Auto-generate a role description from its sub-tool tags.

    Tags minus the role name and phase ID, title-cased.
    E.g. tags=[browsers, firefox, brave, chrome, desktop] → "Firefox, Brave, Chrome"
    """
    excluded = {role_name, phase_id}
    sub_tools = [t for t in tags if t not in excluded]
    if not sub_tools:
        return ""
    return ", ".join(t.replace("-", " ").title() for t in sub_tools)


def _parse_role(role_entry: dict, phase_id: str) -> DiscoveredRole:
    """Parse a single role entry from a play's roles list."""
    name = role_entry.get("role", "")
    tags = role_entry.get("tags", [])
    has_when = "when" in role_entry
    description = _make_description(tags, name, phase_id)
    return DiscoveredRole(
        name=name,
        tags=tuple(tags),
        description=description,
        has_when=has_when,
    )


def _parse_play_file(path: Path) -> DiscoveredPhase | None:
    """Parse a single play YAML file into a DiscoveredPhase."""
    try:
        content = path.read_text()
        docs = yaml.safe_load(content)
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Skipping malformed playbook %s: %s", path.name, exc)
        return None

    if not isinstance(docs, list) or not docs:
        logger.warning("Skipping empty or non-list playbook %s", path.name)
        return None

    play = docs[0]  # first play in the file
    if not isinstance(play, dict):
        logger.warning("Skipping non-dict play in %s", path.name)
        return None

    play_name = play.get("name", path.stem)
    phase_id = _parse_phase_id(path.name)
    order = _parse_order(path.name)
    display_name = _parse_display_name(play_name)
    has_pre_tasks = bool(play.get("pre_tasks"))

    roles_raw = play.get("roles", [])
    roles = tuple(
        _parse_role(r, phase_id) for r in roles_raw if isinstance(r, dict)
    )

    return DiscoveredPhase(
        phase_id=phase_id,
        order=order,
        display_name=display_name,
        roles=roles,
        has_pre_tasks=has_pre_tasks,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def discover_playbook(platform: str) -> PlaybookManifest:
    """Discover all phases and roles from a platform's playbook directory.

    Args:
        platform: "linux" or "macos"

    Returns:
        PlaybookManifest with phases sorted by order.

    Raises:
        FileNotFoundError: if the plays directory doesn't exist.
    """
    platform_dir = "macos" if platform == "macos" else "linux"
    plays_dir = REPO_ROOT / platform_dir / "plays"

    if not plays_dir.is_dir():
        raise FileNotFoundError(f"Plays directory not found: {plays_dir}")

    phases: list[DiscoveredPhase] = []
    for path in sorted(plays_dir.glob("*.yml")):
        phase = _parse_play_file(path)
        if phase is not None:
            phases.append(phase)

    phases.sort(key=lambda p: p.order)

    return PlaybookManifest(platform=platform, phases=tuple(phases))


def validate_config(
    manifest: PlaybookManifest,
    default_phases: dict[str, list[str]],
    phase_deps: dict[str, list[str]],
) -> list[str]:
    """Validate DEFAULT_PHASES and PHASE_DEPS against discovered data.

    Returns a list of warning messages for unknown phase IDs.
    """
    known = set(manifest.phase_ids())
    warnings: list[str] = []

    for mode, phase_ids in default_phases.items():
        for pid in phase_ids:
            if pid not in known:
                warnings.append(
                    f"DEFAULT_PHASES[{mode!r}] references unknown phase {pid!r}"
                )

    for phase, deps in phase_deps.items():
        if phase not in known:
            warnings.append(
                f"PHASE_DEPS key {phase!r} is not a known phase"
            )
        for dep in deps:
            if dep not in known:
                warnings.append(
                    f"PHASE_DEPS[{phase!r}] references unknown dependency {dep!r}"
                )

    return warnings
