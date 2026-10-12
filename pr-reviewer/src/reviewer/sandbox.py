"""Run pytest against the PR checkout. See README: this is NOT a security boundary."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# Non-secret variables the interpreter needs. Windows Python fails at startup without SYSTEMROOT.
_WINDOWS = {"SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP"}
_KEEP_ENV = {"PATH", "LANG", "LC_ALL", "VIRTUAL_ENV"} | _WINDOWS
_FAILED_SUMMARY = re.compile(r"\b\d+ failed\b")


@dataclass
class PytestRun:
    id: str
    status: str  # passed | failed | no_tests | error | timeout
    exit_code: int | None
    output: str
    test_code: str | None = None

    @property
    def failed(self) -> bool:
        """True only for genuine test failures, not collection/usage errors or crashes."""
        return self.status == "failed"


def classify(exit_code: int, output: str) -> str:
    """Exit code 1 alone is ambiguous: a crashed interpreter also exits 1.
    Only call it a test failure if pytest's own summary says tests failed."""
    if exit_code == 0:
        return "passed"
    if exit_code == 5:
        return "no_tests"
    if exit_code == 1 and _FAILED_SUMMARY.search(output):
        return "failed"
    return "error"


def run_pytest(
    root: Path,
    args: list[str],
    run_id: str,
    python: str | None = None,
    timeout: int = 120,
    max_output: int = 6000,
) -> PytestRun:
    with tempfile.TemporaryDirectory() as home:
        env = {k: v for k, v in os.environ.items() if k.upper() in _KEEP_ENV}  # no tokens/API keys
        env.update(HOME=home, USERPROFILE=home, PYTHONDONTWRITEBYTECODE="1")
        cmd = [python or sys.executable, "-m", "pytest", "-q", "--no-header",
               "-p", "no:cacheprovider", "-x", *args]
        try:
            p = subprocess.run(cmd, cwd=root, env=env, capture_output=True,
                               text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return PytestRun(run_id, "timeout", None, f"Timed out after {timeout}s")
    out = (p.stdout + p.stderr)[-max_output:]
    return PytestRun(run_id, classify(p.returncode, out), p.returncode, out)