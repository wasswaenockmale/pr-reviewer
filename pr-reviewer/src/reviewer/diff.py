"""Unified-diff helpers. All line numbers are new-file (RIGHT side) numbers."""
from __future__ import annotations

import re
from collections.abc import Iterator

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def iter_patch(patch: str) -> Iterator[tuple[int | None, str, str]]:
    """Yield (new_line_no, kind, text). kind: '@' hunk header, '+', '-', ' '."""
    new: int | None = None
    for raw in patch.splitlines():
        m = _HUNK.match(raw)
        if m:
            new = int(m.group(1))
            yield None, "@", raw
        elif new is None or raw.startswith("\\"):  # before first hunk / "no newline"
            continue
        elif raw.startswith("+"):
            yield new, "+", raw[1:]
            new += 1
        elif raw.startswith("-"):
            yield None, "-", raw[1:]
        else:
            yield new, " ", raw[1:]
            new += 1


def added_lines(patch: str) -> set[int]:
    return {n for n, k, _ in iter_patch(patch) if k == "+" and n is not None}


def commentable_lines(patch: str) -> set[int]:
    """Lines GitHub accepts for inline review comments (added + context)."""
    return {n for n, k, _ in iter_patch(patch) if k in "+ " and n is not None}


def annotate(patch: str) -> str:
    """Prefix each line with its new-file line number so the model cites real lines."""
    out = []
    for n, kind, text in iter_patch(patch):
        out.append(text if kind == "@" else f"{'' if n is None else n:>5} {kind} {text}")
    return "\n".join(out)
