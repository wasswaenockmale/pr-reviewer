import pytest

from reviewer.models import ChangedFile
from reviewer.session import ReviewSession

SRC = "def avg(xs):\n    return sum(xs) / len(xs)\n"
PATCH = "@@ -0,0 +1,2 @@\n+def avg(xs):\n+    return sum(xs) / len(xs)\n"
REPRO = "import sys\nsys.path.insert(0, '.')\nfrom m import avg\n\n\ndef test_empty():\n    assert avg([]) == 0\n"


@pytest.fixture
def s(tmp_path):
    (tmp_path / "m.py").write_text(SRC)
    return ReviewSession(tmp_path, [ChangedFile("m.py", "added", 2, 0, PATCH)])


def report(s, **kw):
    base = dict(path="m.py", line=2, severity="high", title="Division by zero",
                explanation="avg([]) raises ZeroDivisionError", evidence="return sum(xs) / len(xs)")
    return s.report(**{**base, **kw})


def test_diff_tool_returns_annotated_patch(s):
    ok, text = s.diff("m.py")
    assert ok and "    2 +     return" in text
    assert not s.diff("other.py")[0]


def test_hallucinated_evidence_is_rejected_and_not_stored(s):
    ok, msg = report(s, evidence="return statistics.mean(xs)")
    assert not ok and "Rejected" in msg and s.findings == []


def test_reproduced_finding_end_to_end(s):
    ok, out = s.pytest(test_code=REPRO)
    assert ok and "status=failed" in out
    ok, msg = report(s, repro_id="r1")
    assert ok and "inline" in msg
    assert s.findings[0].reproduced and s.findings[0].inline


def test_option_injection_blocked(s):
    assert not s.pytest(node_ids=["-p", "evil"])[0]


def test_finding_outside_diff_is_summary_only(s):
    (s.root / "m.py").write_text(SRC + "\n" * 3 + "x = 1\n")
    s.files["m.py"].patch = "@@ -1,1 +1,1 @@\n def avg(xs):\n"
    ok, msg = report(s)
    assert ok and "summary only" in msg and not s.findings[0].inline


def test_duplicate_and_cap(s):
    assert report(s)[0]
    assert not report(s)[0]
    s.MAX_FINDINGS = 1
    assert not report(s, line=1, evidence="def avg(xs):")[0]
