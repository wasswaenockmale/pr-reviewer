import json

import httpx

from reviewer.github_client import GitHub
from reviewer.models import PullRequest
from reviewer.render import build_review
from reviewer.session import ReviewSession


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com")


def test_get_pull_paginates_files():
    def handler(req):
        if req.url.path.endswith("/pulls/7"):
            return httpx.Response(200, json={"title": "T", "body": None,
                                             "head": {"sha": "abc"}, "base": {"ref": "main"}})
        page = int(req.url.params["page"])
        n = 100 if page == 1 else 3
        return httpx.Response(200, json=[
            {"filename": f"f{page}_{i}.py", "status": "modified", "additions": 1, "deletions": 0, "patch": "@@"}
            for i in range(n)])

    pr = GitHub("t", client(handler)).get_pull("o", "r", 7)
    assert len(pr.files) == 103 and pr.body == "" and pr.head_sha == "abc"


def test_post_review_payload():
    seen = {}

    def handler(req):
        seen["path"], seen["json"] = req.url.path, json.loads(req.content)
        return httpx.Response(200, json={"id": 1})

    pr = PullRequest("o", "r", 7, "T", "", "abc", "main")
    comment = {"path": "a.py", "line": 3, "side": "RIGHT", "body": "x"}
    GitHub("t", client(handler)).post_review(pr, "summary", [comment])
    assert seen["path"] == "/repos/o/r/pulls/7/reviews"
    assert seen["json"] == {"commit_id": "abc", "body": "summary", "event": "COMMENT", "comments": [comment]}


def test_empty_review_says_so(tmp_path):
    pr = PullRequest("o", "r", 7, "T", "", "abc", "main")
    body, comments = build_review(pr, ReviewSession(tmp_path, []))
    assert "No verified issues" in body and comments == []
