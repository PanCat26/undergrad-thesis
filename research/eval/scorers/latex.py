"""Deterministic LaTeX scoring — uses the backend's real Tectonic compile, no judge.

For a LaTeX-edit task: apply the model's proposed edits onto the task's draft files, then
  - compiled:        does the project compile (Tectonic exit 0)?  None if Tectonic isn't installed.
  - edit_applied:    did the model actually propose any edit?
  - cite_consistent: every \\cite{key} has a matching @type{key, ...} in a .bib file.
"""

from __future__ import annotations

import re

from app.services.latex import CompileError, compile_project

_CITE = re.compile(r"\\cite[tp]?\*?\{([^}]*)\}")
_BIB_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)", re.IGNORECASE)


def _final_files(task: dict, result) -> list[tuple[str, str]]:
    files = {f["path"]: f["content"] for f in task.get("draft_files", [])}
    files.update(result.proposed_edits)  # model's edits win
    return list(files.items())


def _cite_consistent(files: list[tuple[str, str]]) -> bool:
    cited: set[str] = set()
    defined: set[str] = set()
    for path, content in files:
        if path.endswith(".bib"):
            defined.update(m.group(1) for m in _BIB_ENTRY.finditer(content))
        else:
            for m in _CITE.finditer(content):
                cited.update(k.strip() for k in m.group(1).split(",") if k.strip())
    return cited.issubset(defined)  # no \cite without a matching entry


def score_latex(task: dict, result) -> dict:
    files = _final_files(task, result)
    edit_applied = bool(result.proposed_edits)
    out = {"edit_applied": edit_applied, "cite_consistent": _cite_consistent(files), "log": ""}

    if not any(p == "main.tex" for p, _ in files):
        out["compiled"] = False
        out["log"] = "no main.tex"
        return out
    try:
        compile_project(files)
        out["compiled"] = True
    except CompileError as exc:
        if "not available" in str(exc) or "not be found" in str(exc).lower():
            out["compiled"] = None  # Tectonic not installed on this box — column will show n/a
            out["log"] = "tectonic unavailable"
        else:
            out["compiled"] = False
            out["log"] = (getattr(exc, "detail", "") or str(exc))[:500]
    return out
