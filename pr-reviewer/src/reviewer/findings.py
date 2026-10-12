"""A finding is only accepted if its evidence checks out against the real checkout."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .sandbox import PytestRun

SEVERITIES = ("critical", "high", "medium", "low")
WINDOW = 5  # quote must appear within +/- this many lines of the cited line


@dataclass
class Finding:
    path: str
    line: int
    severity: str
    title: str
    explanation: str
    evidence: str  # verbatim code from the file
    repro_id: str | None = None
    reproduced: bool = False
    inline: bool = False  # cited line is part of the diff -> can be an inline comment


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def check_finding(root: Path, f: Finding, runs: dict[str, PytestRun]) -> list[str]:
    """Return a list of problems; empty means the finding is acceptable."""
    problems: list[str] = []
    if f.severity not in SEVERITIES:
        problems.append(f"severity must be one of {SEVERITIES}")
    if not f.title.strip() or not f.explanation.strip():
        problems.append("title and explanation are required")

    root = root.resolve()
    target = (root / f.path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return problems + [f"File not found in the PR checkout: {f.path}"]

    lines = target.read_text(errors="replace").splitlines()
    if not 1 <= f.line <= len(lines):
        problems.append(f"line {f.line} is out of range (file has {len(lines)} lines)")
    elif not f.evidence.strip():
        problems.append("evidence is required: quote the offending code verbatim")
    else:
        window = "\n".join(lines[max(0, f.line - 1 - WINDOW): f.line + WINDOW])
        if _squash(f.evidence) not in _squash(window):
            problems.append(
                f"evidence not found within {WINDOW} lines of {f.path}:{f.line}. "
                "Copy the code verbatim from the file (no diff markers or line numbers)."
            )

    if f.repro_id:
        run = runs.get(f.repro_id)
        if run is None:
            problems.append(f"unknown repro_id {f.repro_id!r}")
        elif not run.failed:
            problems.append(
                f"run {f.repro_id} has status={run.status}; only a genuinely failing "
                "test counts as a reproduction. Fix the test or drop repro_id."
            )
    return problems
