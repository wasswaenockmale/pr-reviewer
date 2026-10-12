"""Run pytest against the PR checkout. See README: this is NOT a security boundary."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

_STATUS = {0: "passed", 1: "failed", 5: "no_tests"}  # anything else -> "error"
_KEEP_ENV = {"PATH", "LANG", "LC_ALL", "VIRTUAL_ENV"}


@dataclass
class PytestRun:
    id: str
    status: str  # passed | failed | no_tests | error | timeout
    exit_code: int | None
    output: str
    test_code: str | None = None

    @property
    def failed(self) -> bool:
        """True only for genuine test failures (exit 1), not collection/usage errors."""
        return self.status == "failed"


def run_pytest(
    root: Path,
    args: list[str],
    run_id: str,
    python: str | None = None,
    timeout: int = 120,
    max_output: int = 6000,
) -> PytestRun:
    with tempfile.TemporaryDirectory() as home:
        env = {k: v for k, v in os.environ.items() if k in _KEEP_ENV}  # no tokens/API keys
        env.update(HOME=home, PYTHONDONTWRITEBYTECODE="1")
        cmd = [python or sys.executable, "-m", "pytest", "-q", "--no-header",
               "-p", "no:cacheprovider", "-x", *args]
        try:
            p = subprocess.run(cmd, cwd=root, env=env, capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return PytestRun(run_id, "timeout", None, f"Timed out after {timeout}s")
    out = (p.stdout + p.stderr)[-max_output:]
    return PytestRun(run_id, _STATUS.get(p.returncode, "error"), p.returncode, out)
