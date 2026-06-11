"""Evidentia's agent tool schemas — the single source of truth for the dataset remap and the
eval tool-use metric.

These mirror the tools bound in ``backend/app/agent/ask.py`` (``_build_tools``): same names,
same argument shapes. Training trajectories for the grounding/abstention/scientific slices are
rewritten to call THESE tools (so the model learns Evidentia's interface), and the eval's
tool-use scorer validates each emitted tool call against these JSON Schemas.

If a tool's signature changes in ask.py, update it here too.
"""

from __future__ import annotations

# OpenAI / Qwen "tools" array format: each entry is {"type": "function", "function": {...}}.
TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_sources",
            "description": (
                "Search the user's uploaded sources (papers and datasets) for passages relevant "
                "to the query. Returns numbered results that should be cited."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_draft",
            "description": (
                "Search the user's current LaTeX draft for passages relevant to the query. "
                "Returns numbered results that should be cited."
            ),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_sources",
            "description": "List all of the user's uploaded sources (filename and type).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the files in the user's current LaTeX draft.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the full content of a file in the user's draft by its path (e.g. 'main.tex').",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_references",
            "description": (
                "Return verified BibTeX entries (and their \\cite keys) for the user's paper "
                "sources, for citing them and building references.bib. Use entries and keys "
                "verbatim — never invent bibliographic details. Datasets are not citable."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Propose creating a new draft file, or overwriting an existing one, with the "
                "given full content. Shown to the user for approval before being applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Propose replacing an exact text snippet in a draft file. old_string must appear "
                "in the file; new_string is the replacement (empty deletes the snippet). Shown to "
                "the user for approval before being applied."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_string": {"type": "string"},
                    "new_string": {"type": "string"},
                },
                "required": ["path", "old_string"],
            },
        },
    },
]

# Convenience lookups.
TOOLS_BY_NAME: dict[str, dict] = {t["function"]["name"]: t["function"] for t in TOOLS}
QA_TOOLS = [t for t in TOOLS if t["function"]["name"] not in {"write_file", "edit_file"}]
AGENTIC_TOOLS = TOOLS


def required_args(tool_name: str) -> list[str]:
    fn = TOOLS_BY_NAME.get(tool_name)
    if fn is None:
        return []
    return list(fn["parameters"].get("required", []))


def allowed_args(tool_name: str) -> set[str]:
    fn = TOOLS_BY_NAME.get(tool_name)
    if fn is None:
        return set()
    return set(fn["parameters"].get("properties", {}).keys())
