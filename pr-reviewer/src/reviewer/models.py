from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ChangedFile:
    path: str
    status: str  # added | modified | removed | renamed
    additions: int
    deletions: int
    patch: str | None  # GitHub omits this for binary / very large diffs


@dataclass
class PullRequest:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    head_sha: str
    base_ref: str
    files: list[ChangedFile] = field(default_factory=list)
