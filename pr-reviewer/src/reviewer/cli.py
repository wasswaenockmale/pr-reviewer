from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import tempfile
from pathlib import Path

from .agent import run_review
from .github_client import GitHub
from .render import build_review
from .session import ReviewSession


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pr-reviewer", description="AI review of a GitHub pull request")
    ap.add_argument("pr", help="owner/repo#123")
    ap.add_argument("--post", action="store_true", help="post the review (default: print only)")
    ap.add_argument("--python", help="interpreter with the target repo's dependencies installed")
    ap.add_argument("--budget", type=float, default=5.0, help="max USD for the agent run")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    m = re.fullmatch(r"([\w.-]+)/([\w.-]+)#(\d+)", args.pr)
    if not m:
        ap.error("PR must look like owner/repo#123")
    owner, repo, number = m[1], m[2], int(m[3])
    if "GITHUB_TOKEN" not in os.environ:
        ap.error("set GITHUB_TOKEN (and ANTHROPIC_API_KEY)")

    gh = GitHub(os.environ["GITHUB_TOKEN"])
    pr = gh.get_pull(owner, repo, number)
    with tempfile.TemporaryDirectory(prefix="pr-review-") as tmp:
        root = Path(tmp) / "repo"
        gh.checkout(pr, root)
        session = ReviewSession(root, pr.files, python=args.python)
        result = asyncio.run(run_review(pr, session, verbose=args.verbose, max_budget_usd=args.budget))
        body, comments = build_review(pr, session)

    if result:
        print(f"[{result.num_turns} turns, ${result.total_cost_usd or 0:.2f}]", file=sys.stderr)
    if args.post:
        gh.post_review(pr, body, comments)
        print(f"Posted review with {len(comments)} inline comment(s).")
    else:
        print(body)
        for c in comments:
            print(f"\n--- {c['path']}:{c['line']} ---\n{c['body']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
