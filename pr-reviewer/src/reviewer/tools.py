"""Thin SDK wrapper: each tool just delegates to ReviewSession."""
from __future__ import annotations

from claude_agent_sdk import create_sdk_mcp_server, tool

from .session import ReviewSession, Result

SERVER_NAME = "review"
TOOL_NAMES = ["get_pr_overview", "get_diff", "run_pytest", "report_finding"]
ALLOWED = [f"mcp__{SERVER_NAME}__{n}" for n in TOOL_NAMES]


def _out(res: Result) -> dict:
    ok, text = res
    return {"content": [{"type": "text", "text": text}], **({} if ok else {"is_error": True})}


def build_server(s: ReviewSession):
    @tool("get_pr_overview", "List files changed in the PR with status and line counts.", {})
    async def get_pr_overview(args):
        return _out(s.overview())

    @tool("get_diff",
          "Diff of one changed file. Each line is prefixed with its new-file line number; "
          "use those numbers when reporting findings.", {"path": str})
    async def get_diff(args):
        return _out(s.diff(args["path"]))

    @tool("run_pytest",
          "Run pytest in the PR checkout. Pass test_code to write and run a throwaway repro test, "
          "and/or node_ids to run existing tests. Returns a run_id usable as repro_id.",
          {"type": "object", "properties": {
              "test_code": {"type": "string", "description": "Complete pytest module source"},
              "node_ids": {"type": "array", "items": {"type": "string"}}}})
    async def run_pytest_tool(args):
        return _out(s.pytest(args.get("test_code"), args.get("node_ids")))

    @tool("report_finding",
          "Report one bug. Validated against the real files: 'evidence' must be code copied verbatim "
          "from within 5 lines of 'line'. If you reproduced it, pass the failing run's id as repro_id. "
          "Rejected findings return the reason; fix or drop them.",
          {"type": "object", "required": ["path", "line", "severity", "title", "explanation", "evidence"],
           "properties": {
               "path": {"type": "string"}, "line": {"type": "integer"},
               "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
               "title": {"type": "string"}, "explanation": {"type": "string"},
               "evidence": {"type": "string"}, "repro_id": {"type": "string"}}})
    async def report_finding(args):
        return _out(s.report(**args))

    return create_sdk_mcp_server(
        SERVER_NAME, "1.0.0", [get_pr_overview, get_diff, run_pytest_tool, report_finding])
