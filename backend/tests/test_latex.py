import shutil
from pathlib import Path

import pytest

from app.services.files import DEFAULT_MAIN_TEX
from app.services.latex import CompileError, _materialize, compile_project


def test_materialize_writes_files_with_subdirs(tmp_path: Path) -> None:
    _materialize([("main.tex", "hello"), ("chapters/intro.tex", "intro")], str(tmp_path))
    assert (tmp_path / "main.tex").read_text() == "hello"
    assert (tmp_path / "chapters" / "intro.tex").read_text() == "intro"


def test_materialize_rejects_path_escape(tmp_path: Path) -> None:
    with pytest.raises(CompileError):
        _materialize([("../evil.tex", "x")], str(tmp_path))


def test_compile_without_main_raises() -> None:
    with pytest.raises(CompileError):
        compile_project([("intro.tex", "x")])


@pytest.mark.skipif(shutil.which("tectonic") is None, reason="tectonic not installed")
def test_compile_produces_pdf() -> None:
    pdf = compile_project([("main.tex", DEFAULT_MAIN_TEX)])
    assert pdf[:4] == b"%PDF"
