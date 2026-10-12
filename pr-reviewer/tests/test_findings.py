from pathlib import Path

from reviewer.findings import Finding, check_finding
from reviewer.sandbox import PytestRun

SRC = "def div(a, b):\n    return a / b\n\n\ndef avg(xs):\n    return sum(xs) / len(xs)\n"


def make(tmp_path: Path, **kw) -> Finding:
    (tmp_path / "m.py").write_text(SRC)
    base = dict(path="m.py", line=6, severity="high", title="t", explanation="e",
                evidence="return sum(xs) / len(xs)")
    return Finding(**{**base, **kw})


def test_valid_finding(tmp_path):
    assert check_finding(tmp_path, make(tmp_path), {}) == []


def test_whitespace_insensitive_quote(tmp_path):
    f = make(tmp_path, evidence="return   sum(xs)  /\n len(xs)")
    assert check_finding(tmp_path, f, {}) == []


def test_hallucinated_quote_rejected(tmp_path):
    f = make(tmp_path, evidence="return statistics.mean(xs)")
    assert any("evidence not found" in p for p in check_finding(tmp_path, f, {}))


def test_quote_far_from_cited_line_rejected(tmp_path):
    (tmp_path / "m.py").write_text("\n" * 20 + SRC)  # quote now at line 26
    f = Finding("m.py", 1, "high", "t", "e", "return sum(xs) / len(xs)")
    assert any("evidence not found" in p for p in check_finding(tmp_path, f, {}))


def test_path_traversal_rejected(tmp_path):
    f = make(tmp_path, path="../etc/passwd")
    assert any("not found" in p for p in check_finding(tmp_path, f, {}))


def test_line_out_of_range(tmp_path):
    assert check_finding(tmp_path, make(tmp_path, line=99), {})


def test_bad_severity(tmp_path):
    assert check_finding(tmp_path, make(tmp_path, severity="meh"), {})


def test_repro_must_be_a_real_failure(tmp_path):
    f = make(tmp_path, repro_id="r1")
    assert check_finding(tmp_path, f, {})  # unknown id
    runs = {"r1": PytestRun("r1", "error", 2, "ImportError")}
    assert any("status=error" in p for p in check_finding(tmp_path, f, runs))
    runs = {"r1": PytestRun("r1", "passed", 0, "")}
    assert check_finding(tmp_path, f, runs)
    runs = {"r1": PytestRun("r1", "failed", 1, "assert")}
    assert check_finding(tmp_path, f, runs) == []
