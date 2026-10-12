"""All agent-facing logic lives here, free of SDK imports so it is unit-testable."""
from __future__ import annotations

from pathlib import Path

from .diff import annotate, commentable_lines
from .findings import Finding, check_finding
from .models import ChangedFile
from .sandbox import PytestRun, run_pytest

Result = tuple[bool, str]  # (ok, text for the model)


class ReviewSession:
    MAX_FINDINGS = 15

    def __init__(self, root: Path, files: list[ChangedFile], python: str | None = None):
        self.root = Path(root).resolve()
        self.files = {f.path: f for f in files}
        self.python = python
        self.runs: dict[str, PytestRun] = {}
        self.findings: list[Finding] = []

    def overview(self) -> Result:
        rows = [f"{f.status:<9} +{f.additions}/-{f.deletions}  {f.path}"
                for f in self.files.values()]
        return True, "Changed files:\n" + "\n".join(rows)

    def diff(self, path: str) -> Result:
        f = self.files.get(path)
        if f is None:
            return False, f"{path!r} is not a changed file. Use get_pr_overview for the list."
        if not f.patch:
            return False, "No patch available (binary, deleted, or too large). Use Read."
        return True, annotate(f.patch)

    def pytest(self, test_code: str | None = None, node_ids: list[str] | None = None) -> Result:
        run_id = f"r{len(self.runs) + 1}"
        args = list(node_ids or [])
        if any(a.startswith("-") for a in args):
            return False, "node_ids must be test paths/ids, not pytest options."
        if test_code:
            d = self.root / "_review_repro"
            d.mkdir(exist_ok=True)
            p = d / f"test_{run_id}.py"
            p.write_text(test_code)
            args.append(str(p.relative_to(self.root)))
        if not args:
            return False, "Provide test_code and/or node_ids."
        run = run_pytest(self.root, args, run_id, python=self.python)
        run.test_code = test_code
        self.runs[run_id] = run
        hint = {"error": "The run errored (import/collection/usage). The test itself is probably broken; fix it.",
                "no_tests": "No tests were collected.",
                "timeout": "Timed out."}.get(run.status, "")
        return True, f"run_id={run_id} status={run.status} exit={run.exit_code}\n{hint}\n{run.output}".strip()

    def report(self, path: str, line: int, severity: str, title: str, explanation: str,
               evidence: str, repro_id: str | None = None) -> Result:
        if len(self.findings) >= self.MAX_FINDINGS:
            return False, "Finding limit reached. Stop reporting and write your summary."
        f = Finding(path, int(line), severity, title, explanation, evidence, repro_id)
        problems = check_finding(self.root, f, self.runs)
        if problems:
            return False, "Rejected:\n- " + "\n- ".join(problems) + "\nFix and resubmit, or drop it."
        if any(x.path == f.path and x.line == f.line for x in self.findings):
            return False, f"A finding already exists at {path}:{line}."
        f.reproduced = bool(repro_id)
        cf = self.files.get(path)
        f.inline = bool(cf and cf.patch and f.line in commentable_lines(cf.patch))
        self.findings.append(f)
        where = "inline comment" if f.inline else "summary only (line is outside the diff)"
        return True, f"Accepted as {where}."
