import os
import shutil
import subprocess
import tempfile

from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger("app.latex")

MAIN_FILE = "main.tex"
# Generous: the first compile in a fresh container downloads the Tectonic
# package bundle on demand; later compiles use the cached bundle and are fast.
COMPILE_TIMEOUT_SECONDS = 120


class CompileError(AppError):
    status_code = 422
    code = "compile_error"


def _tectonic_binary() -> str:
    return shutil.which("tectonic") or "tectonic"


def _materialize(files: list[tuple[str, str]], dest_dir: str) -> None:
    """Write (path, content) pairs into dest_dir, guarding against path escapes."""
    dest_root = os.path.realpath(dest_dir)
    for path, content in files:
        target = os.path.realpath(os.path.join(dest_root, path))
        if target != dest_root and not target.startswith(dest_root + os.sep):
            raise CompileError(f"Invalid file path: {path}")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(content)


def compile_project(files: list[tuple[str, str]]) -> bytes:
    """Compile the project's files with Tectonic and return the PDF bytes.

    Raises CompileError (HTTP 422) with the engine log on any failure.
    """
    if not any(path == MAIN_FILE for path, _ in files):
        raise CompileError(f"No {MAIN_FILE} found at the project root")

    with tempfile.TemporaryDirectory(prefix="latex-") as work_dir:
        _materialize(files, work_dir)
        main_path = os.path.join(work_dir, MAIN_FILE)

        try:
            result = subprocess.run(
                [_tectonic_binary(), main_path, "--outdir", work_dir, "--chatter", "minimal"],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=COMPILE_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            logger.error("tectonic binary not found", exc_info=exc)
            raise CompileError("LaTeX engine is not available") from exc
        except subprocess.TimeoutExpired as exc:
            raise CompileError("Compilation timed out") from exc

        if result.returncode != 0:
            log = (result.stdout + "\n" + result.stderr).strip()
            raise CompileError("LaTeX compilation failed", detail=log)

        pdf_path = os.path.join(work_dir, "main.pdf")
        if not os.path.exists(pdf_path):
            log = (result.stdout + "\n" + result.stderr).strip()
            raise CompileError("Compilation produced no PDF", detail=log)

        with open(pdf_path, "rb") as handle:
            return handle.read()
