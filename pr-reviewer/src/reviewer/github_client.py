from __future__ import annotations

import base64
import subprocess
from pathlib import Path

import httpx

from .models import ChangedFile, PullRequest


class GitHub:
    def __init__(self, token: str, client: httpx.Client | None = None):
        self.token = token
        self.http = client or httpx.Client(
            base_url="https://api.github.com",
            timeout=30,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def _paginate(self, url: str):
        page = 1
        while True:
            r = self.http.get(url, params={"per_page": 100, "page": page})
            r.raise_for_status()
            data = r.json()
            yield from data
            if len(data) < 100:
                return
            page += 1

    def get_pull(self, owner: str, repo: str, number: int) -> PullRequest:
        r = self.http.get(f"/repos/{owner}/{repo}/pulls/{number}")
        r.raise_for_status()
        d = r.json()
        files = [
            ChangedFile(f["filename"], f["status"], f["additions"], f["deletions"], f.get("patch"))
            for f in self._paginate(f"/repos/{owner}/{repo}/pulls/{number}/files")
        ]
        return PullRequest(owner, repo, number, d["title"], d.get("body") or "",
                           d["head"]["sha"], d["base"]["ref"], files)

    def checkout(self, pr: PullRequest, dest: Path) -> None:
        """Fetch the PR head into dest. The token is passed per-command, never stored in .git/config."""
        auth = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
        url = f"https://github.com/{pr.owner}/{pr.repo}.git"
        dest.mkdir(parents=True, exist_ok=True)
        run = lambda *a: subprocess.run(a, cwd=dest, check=True, capture_output=True, text=True)
        run("git", "init", "-q")
        run("git", "-c", f"http.extraheader=Authorization: Basic {auth}",
            "fetch", "-q", "--depth=50", url, f"pull/{pr.number}/head")
        run("git", "checkout", "-q", "--detach", "FETCH_HEAD")
        head = run("git", "rev-parse", "HEAD").stdout.strip()
        if head != pr.head_sha:
            raise RuntimeError(f"PR was updated during checkout ({head[:7]} != {pr.head_sha[:7]}); re-run.")

    def post_review(self, pr: PullRequest, body: str, comments: list[dict]) -> dict:
        r = self.http.post(
            f"/repos/{pr.owner}/{pr.repo}/pulls/{pr.number}/reviews",
            json={"commit_id": pr.head_sha, "body": body, "event": "COMMENT", "comments": comments},
        )
        r.raise_for_status()
        return r.json()
