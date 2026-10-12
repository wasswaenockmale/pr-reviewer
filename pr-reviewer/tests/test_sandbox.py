from reviewer.sandbox import run_pytest


def run(tmp_path, code):
    (tmp_path / "test_x.py").write_text(code)
    return run_pytest(tmp_path, ["test_x.py"], "r1")


def test_failing_test_is_failed(tmp_path):
    r = run(tmp_path, "def test_a():\n    assert 1 == 2\n")
    assert r.status == "failed" and r.failed


def test_passing_test(tmp_path):
    assert run(tmp_path, "def test_a():\n    assert True\n").status == "passed"


def test_broken_test_is_error_not_failure(tmp_path):
    r = run(tmp_path, "import does_not_exist\n\ndef test_a(): pass\n")
    assert r.status == "error" and not r.failed


def test_secrets_not_inherited(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    r = run(tmp_path, "import os\n\ndef test_a():\n    assert 'GITHUB_TOKEN' not in os.environ\n")
    assert r.status == "passed"


def test_classify_does_not_trust_exit_code_1_alone():
    from reviewer.sandbox import classify
    assert classify(1, "1 failed in 0.02s") == "failed"
    assert classify(1, "1 failed, 4 passed in 0.5s") == "failed"
    # an interpreter crash (e.g. Windows without SYSTEMROOT) also exits 1
    assert classify(1, "Fatal Python error: failed to get random numbers") == "error"
    assert classify(1, "") == "error"
    assert classify(0, "3 passed") == "passed"
    assert classify(2, "1 failed") == "error"
    assert classify(5, "no tests ran") == "no_tests"