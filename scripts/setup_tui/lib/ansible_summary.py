"""Line-by-line parser for Ansible YAML callback output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class FailedTask:
    """A single failed Ansible task with context."""

    play: str  # e.g. "Phase 2: Development tools"
    role: str  # e.g. "git"
    task: str  # e.g. "Install git"
    message: str  # extracted error message


@dataclass
class AnsibleSummary:
    """Structured summary of an Ansible run."""

    ok: int = 0
    changed: int = 0
    failed: int = 0
    skipped: int = 0
    unreachable: int = 0
    rescued: int = 0
    ignored: int = 0
    failures: list[FailedTask] = field(default_factory=list)


# Regex patterns for Ansible YAML callback output.
_PLAY_RE = re.compile(r"^PLAY \[(.+?)\] \*+")
_TASK_RE = re.compile(r"^TASK \[(?:(.+?) : )?(.+?)\] \*+")
_FATAL_RE = re.compile(r"^fatal: \[.+?\]: (?:FAILED|UNREACHABLE)! =>")
_MSG_RE = re.compile(r'^(\s+)msg: (.+)$')
_MSG_BLOCK_RE = re.compile(r'^(\s+)msg: \|[->]?$')
_RECAP_RE = re.compile(r"^PLAY RECAP \*+")
_RECAP_LINE_RE = re.compile(
    r"^(\S+)\s+:"
    r"\s+ok=(\d+)"
    r"\s+changed=(\d+)"
    r"\s+unreachable=(\d+)"
    r"\s+failed=(\d+)"
    r"(?:\s+skipped=(\d+))?"
    r"(?:\s+rescued=(\d+))?"
    r"(?:\s+ignored=(\d+))?"
)


class AnsibleOutputParser:
    """Stateful parser fed one line at a time during Ansible streaming.

    After the run completes, call ``summary()`` to get structured results.
    """

    def __init__(self) -> None:
        self._current_play: str = ""
        self._current_role: str = ""
        self._current_task: str = ""

        self._in_fatal: bool = False
        self._fatal_msg_lines: list[str] = []
        self._fatal_msg_indent: int = 0
        self._in_msg_block: bool = False

        self._failures: list[FailedTask] = []
        self._in_recap: bool = False
        self._summary: AnsibleSummary | None = None

    def feed_line(self, line: str) -> None:
        """Feed a single line of Ansible output to the parser."""
        # PLAY RECAP parsing (final counts).
        if self._in_recap:
            self._parse_recap_line(line)
            return

        if _RECAP_RE.match(line):
            self._flush_fatal()
            self._in_recap = True
            return

        # PLAY header.
        m = _PLAY_RE.match(line)
        if m:
            self._flush_fatal()
            self._current_play = m.group(1)
            return

        # TASK header.
        m = _TASK_RE.match(line)
        if m:
            self._flush_fatal()
            self._current_role = m.group(1) or ""
            self._current_task = m.group(2)
            return

        # Fatal line — start capturing.
        if _FATAL_RE.match(line):
            self._flush_fatal()
            self._in_fatal = True
            self._fatal_msg_lines = []
            self._in_msg_block = False
            return

        # Inside a fatal block — look for the msg field.
        if self._in_fatal:
            self._capture_fatal_line(line)

    def _capture_fatal_line(self, line: str) -> None:
        """Capture error message lines after a fatal marker."""
        # Check for msg: on a single line (inline value).
        m = _MSG_RE.match(line)
        if m and not self._in_msg_block:
            indent = len(m.group(1))
            msg_value = m.group(2).strip()
            if msg_value and msg_value not in ('|-', '|', '>-', '>'):
                # Single-line msg.
                self._fatal_msg_lines = [msg_value]
                self._fatal_msg_indent = indent
                return
            # msg: |- or msg: | — start block capture.
            self._in_msg_block = True
            self._fatal_msg_indent = indent
            return

        # Check for msg block start: "  msg: |-" etc.
        m = _MSG_BLOCK_RE.match(line)
        if m and not self._in_msg_block:
            self._in_msg_block = True
            self._fatal_msg_indent = len(m.group(1))
            return

        # Capturing block-scalar continuation lines.
        if self._in_msg_block:
            stripped = line.rstrip()
            if stripped == '' or (len(stripped) - len(stripped.lstrip()) > self._fatal_msg_indent):
                self._fatal_msg_lines.append(stripped.strip())
            else:
                # Dedented line ends the block.
                self._in_msg_block = False

    def _flush_fatal(self) -> None:
        """Finalize any in-progress fatal capture into a FailedTask."""
        if not self._in_fatal:
            return

        msg = "\n".join(self._fatal_msg_lines).strip()
        if not msg:
            msg = "(no error message captured)"

        self._failures.append(FailedTask(
            play=self._current_play,
            role=self._current_role,
            task=self._current_task,
            message=msg,
        ))
        self._in_fatal = False
        self._fatal_msg_lines = []
        self._in_msg_block = False

    def _parse_recap_line(self, line: str) -> None:
        """Parse a PLAY RECAP stats line."""
        m = _RECAP_LINE_RE.match(line.strip())
        if not m:
            return

        # Accumulate across hosts (usually just localhost).
        if self._summary is None:
            self._summary = AnsibleSummary(failures=self._failures)

        self._summary.ok += int(m.group(2))
        self._summary.changed += int(m.group(3))
        self._summary.unreachable += int(m.group(4))
        self._summary.failed += int(m.group(5))
        self._summary.skipped += int(m.group(6) or 0)
        self._summary.rescued += int(m.group(7) or 0)
        self._summary.ignored += int(m.group(8) or 0)

    def summary(self) -> AnsibleSummary | None:
        """Return the parsed summary, or None if no recap was seen."""
        self._flush_fatal()
        if self._summary is not None:
            self._summary.failures = self._failures
        return self._summary
