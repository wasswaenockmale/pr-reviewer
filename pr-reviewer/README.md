# pr-reviewer

An AI code-review agent for GitHub pull requests. Built on the Claude Agent SDK, the GitHub REST API, and pytest.

The core idea: **the model proposes, the harness verifies.** A finding is only posted if its evidence checks out against the real checkout.

## How it works

```
CLI ──► GitHub API: PR metadata + per-file patches
    ──► git: fetch pull/N/head into a temp dir (token never written to .git/config)
    ──► Claude Agent SDK agent (cwd = checkout)
          built-in, read-only : Read, Grep, Glob   (jailed to the checkout by a PreToolUse hook)
          custom MCP tools    : get_pr_overview, get_diff (line-numbered), run_pytest, report_finding
    ──► report_finding validates every finding, then
    ──► GitHub API: one review with inline comments (or print with no --post)
```

What "evidence" means here (`findings.py`):

| Check | Why |
|---|---|
| File exists inside the checkout | no path traversal / invented files |
| Quoted code appears verbatim within ±5 lines of the cited line | catches hallucinated or misnumbered citations |
| If `repro_id` given, that pytest run must have **failed** (exit 1) | an erroring or passing test is not proof; broken repros are rejected |
| Line is part of the diff? | yes → inline comment; no → listed in the review summary (GitHub rejects off-diff inline comments) |

Rejected findings return the reason to the agent so it can fix or drop them.

## Run

```bash
pip install -e '.[dev]'
export ANTHROPIC_API_KEY=...  GITHUB_TOKEN=...   # token: pull_requests:write, contents:read

pr-reviewer owner/repo#123 --python /path/to/target-venv/bin/python        # dry run
pr-reviewer owner/repo#123 --python /path/to/target-venv/bin/python --post # post review
pytest                                                                      # tests for this project
```

`--python` should be an interpreter that already has the target repo's dependencies installed (the reviewer does not install them). Model defaults to `claude-sonnet-5-5`; override with `REVIEW_MODEL`.

## Security: read this before pointing it at untrusted PRs

`run_pytest` **executes code from the PR** (and code the model wrote). The env is scrubbed (no tokens or API keys) and the agent has no shell, but that is not a sandbox. For anything beyond your own repos, run the whole tool in a disposable container with no network access to internal services and no mounted secrets (e.g. Docker with `--network` restricted, read-only root, non-root user).

Other hardening already in place: `setting_sources=[]` (a malicious PR can't inject `.claude/` settings or CLAUDE.md), `permission_mode="dontAsk"` with an explicit tool allowlist, PR text wrapped as untrusted, a USD budget cap, and a 15-finding cap.

## Layout

```
src/reviewer/
  session.py        agent-facing logic (SDK-free, unit-tested)
  findings.py       evidence verification
  sandbox.py        pytest runner
  diff.py           patch parsing, line numbering
  github_client.py  GitHub REST + checkout
  tools.py          SDK MCP wrappers
  agent.py          prompt, options, hook, agent loop
  render.py         comment / summary formatting
  cli.py
tests/              27 tests; none need network or API keys
```

## Not yet done (suggested next steps)

1. **Evals.** Build a set of PRs with seeded bugs plus clean PRs; track recall, false-positive rate, and cost per review. This is what tells you whether prompt/model changes help.
2. **Regression proof:** run each repro against the PR base too; a test that passes on base and fails on head proves the PR introduced the bug.
3. **Idempotency:** skip if this head SHA was already reviewed; dedupe against existing bot comments on re-pushes.
4. **Webhook / GitHub Action trigger** instead of the CLI.
5. Large-PR strategy (sub-agents per file group via `AgentDefinition`) and dependency install per repo.
