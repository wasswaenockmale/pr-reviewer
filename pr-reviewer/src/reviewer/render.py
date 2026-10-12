from __future__ import annotations

from .findings import Finding
from .models import PullRequest
from .sandbox import PytestRun
from .session import ReviewSession

_BADGE = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}


def render_comment(f: Finding, runs: dict[str, PytestRun]) -> str:
    parts = [f"{_BADGE[f.severity]} **{f.severity.upper()}: {f.title}**", "", f.explanation,
             "", "**Evidence**", f"```\n{f.evidence.strip()}\n```"]
    run = runs.get(f.repro_id) if f.repro_id else None
    if run:
        body = ""
        if run.test_code:
            body += f"```python\n{run.test_code.strip()}\n```\n\n"
        body += f"```\n{run.output.strip()}\n```"
        parts += ["", f"✅ Reproduced with a failing pytest run (`{run.id}`).",
                  "<details><summary>Repro test and output</summary>\n", body, "\n</details>"]
    return "\n".join(parts)


def build_review(pr: PullRequest, session: ReviewSession) -> tuple[str, list[dict]]:
    fs = session.findings
    inline = [{"path": f.path, "line": f.line, "side": "RIGHT",
               "body": render_comment(f, session.runs)} for f in fs if f.inline]
    repro = sum(f.reproduced for f in fs)
    lines = ["### 🤖 Automated review",
             f"Reviewed {len(pr.files)} changed file(s): {len(fs)} verified finding(s), "
             f"{repro} reproduced by a failing test."]
    if not fs:
        lines.append("No verified issues found.")
    outside = [f for f in fs if not f.inline]
    if outside:
        lines += ["", "**Findings on code outside this diff**"]
        lines += [f"- `{f.path}:{f.line}` ({f.severity}) {f.title}\n\n  {f.explanation}" for f in outside]
    return "\n".join(lines), inline
