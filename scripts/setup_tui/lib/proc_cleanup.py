"""Shared helper for terminating tracked subprocess.Popen objects."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger("setup")


def terminate_procs(procs: list[subprocess.Popen], timeout: float = 2.0) -> None:
    """Send SIGTERM to all live procs, wait briefly, then SIGKILL stragglers."""
    alive = [p for p in procs if p.poll() is None]
    if not alive:
        return

    for p in alive:
        try:
            p.terminate()
        except OSError:
            pass

    for p in alive:
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Process %d did not exit after SIGTERM, sending SIGKILL", p.pid)
            try:
                p.kill()
            except OSError:
                pass
