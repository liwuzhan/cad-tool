"""Script executor v2 - Subprocess-isolated execution with reliable timeout

Runs user scripts in a subprocess so that:
- Timeout works reliably on ALL platforms (Windows included)
- A hung script is forcefully killed without corrupting the parent process
- Checkpoint JSONL events are forwarded from subprocess stdout
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..constants import RESULT_VARIABLE, ErrorCode
from ..models import ErrorInfo
from ..package import ModelPackage
from .error_handler import format_timeout_error


# ---------------------------------------------------------------------------
# Runner script template (executed inside the subprocess)
# Uses %s-style formatting so we don't clash with Python dict literals.
# ---------------------------------------------------------------------------
_RUNNER_TEMPLATE = """\
import sys, json, traceback
from pathlib import Path

_SCRIPT = %(script)r
_RESULT = %(result)r
_ERROR  = %(error)r

try:
    _code_str = Path(_SCRIPT).read_text(encoding="utf-8")
    try:
        _code = compile(_code_str, _SCRIPT, "exec")
    except SyntaxError as _e:
        Path(_ERROR).write_text(json.dumps({"type": "syntax", "line": _e.lineno or 0, "message": str(_e.msg or _e)}))
        sys.exit(1)

    _ns = {}
    exec(_code, _ns)

    if "result" not in _ns:
        Path(_ERROR).write_text(json.dumps({"type": "missing_result", "message": "Script must define 'result' variable"}))
        sys.exit(1)

    _shape = _ns["result"]
    if not (hasattr(_shape, "volume") and hasattr(_shape, "area")
            and hasattr(_shape, "bounding_box") and hasattr(_shape, "faces")
            and hasattr(_shape, "edges") and hasattr(_shape, "vertices")):
        Path(_ERROR).write_text(json.dumps({"type": "invalid_result", "message": "'result' must be a build123d Shape object"}))
        sys.exit(1)

    from build123d import export_step, Compound
    try:
        export_step(_shape, _RESULT)
    except Exception:
        # build123d 0.11 regression (#1356): shapes read back from STEP
        # cannot be re-exported directly; wrap in a Compound as fallback.
        export_step(Compound(children=[_shape]), _RESULT)

except SystemExit:
    raise
except Exception as _e:
    _tb = traceback.extract_tb(_e.__traceback__)
    _line = 0
    for _frame in reversed(_tb):
        if _frame.filename == _SCRIPT:
            _line = _frame.lineno
            break
    Path(_ERROR).write_text(json.dumps({"type": "runtime", "line": _line, "error_type": type(_e).__name__, "message": str(_e)}))
    sys.exit(1)
"""


def _error_from_json(data: dict, script_path: Path) -> ErrorInfo:
    """Convert error JSON written by the runner subprocess into ErrorInfo."""
    t = data.get("type", "unknown")

    if t == "syntax":
        return ErrorInfo(
            file=str(script_path),
            line=data.get("line", 0),
            type="SyntaxError",
            code=ErrorCode.E_SYNTAX,
            message=data.get("message", "Syntax error"),
            hint=f"Check syntax near line {data.get('line', 0)}",
        )
    if t == "missing_result":
        return ErrorInfo(
            file=str(script_path),
            line=0,
            type="MissingResult",
            code=ErrorCode.E_RUNTIME,
            message=data.get("message", ""),
            hint=f"Add '{RESULT_VARIABLE} = <your_shape>' at the end of the script",
        )
    if t == "invalid_result":
        return ErrorInfo(
            file=str(script_path),
            line=0,
            type="InvalidResult",
            code=ErrorCode.E_RUNTIME,
            message=data.get("message", ""),
            hint="Ensure result is a valid Shape (Box, Cylinder, etc.)",
        )
    # runtime
    return ErrorInfo(
        file=str(script_path),
        line=data.get("line", 0),
        type=data.get("error_type", "RuntimeError"),
        code=ErrorCode.E_RUNTIME,
        message=data.get("message", "Unknown error"),
        hint=None,
    )


class ScriptExecutorV2:
    """Executes build123d scripts in a subprocess for reliable timeout.

    The user script runs inside a child Python process.  Results are
    communicated back via a temporary STEP file; errors via a JSON file.
    JSONL events (checkpoints, etc.) emitted to the child's stdout are
    forwarded to the parent's stdout.
    """

    def __init__(self, package: ModelPackage):
        self.package = package
        self.timeout_seconds = package.get_manifest().timeout_seconds
        self._checkpoint_names: list[str] = []
        self._checkpoint_results: list[dict] = []  # full payloads from checkpoints

    def execute(self, script_path: Path) -> tuple[Optional["Shape"], Optional[ErrorInfo]]:
        """Execute a build123d script in an isolated subprocess.

        Returns (shape, error) — exactly one will be None.
        """
        self._checkpoint_names = []
        self._checkpoint_results = []

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            result_step = tmp / "_result.step"
            error_json = tmp / "_error.json"

            runner_code = _RUNNER_TEMPLATE % {
                "script": str(script_path),
                "result": str(result_step),
                "error": str(error_json),
            }

            try:
                proc = subprocess.run(
                    [sys.executable, "-c", runner_code],
                    timeout=self.timeout_seconds,
                    capture_output=True,
                    text=True,
                    cwd=str(script_path.parent),
                )
            except subprocess.TimeoutExpired:
                return None, format_timeout_error(script_path, self.timeout_seconds)

            # Forward JSONL events from subprocess stdout (checkpoints, etc.)
            if proc.stdout:
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # Forward to our stdout
                    print(line, flush=True)
                    # Extract checkpoint data for review command
                    try:
                        evt = json.loads(line)
                        if evt.get("event") in ("checkpoint_passed", "checkpoint_failed"):
                            payload = evt.get("payload", {})
                            name = payload.get("name")
                            if name:
                                self._checkpoint_names.append(name)
                                self._checkpoint_results.append({
                                    "name": name,
                                    "event": evt["event"],
                                    "passed": payload.get("passed", 0),
                                    "total": payload.get("total", 0),
                                    "state": payload.get("state", {}),
                                    "checks": payload.get("checks", []),
                                })
                    except (json.JSONDecodeError, KeyError):
                        pass

            # --- Handle error ---
            if proc.returncode != 0:
                if error_json.exists():
                    data = json.loads(error_json.read_text(encoding="utf-8"))
                    return None, _error_from_json(data, script_path)
                return None, ErrorInfo(
                    file=str(script_path),
                    line=0,
                    type="SubprocessError",
                    code=ErrorCode.E_RUNTIME,
                    message=f"Script exited with code {proc.returncode}",
                    hint=None,
                )

            # --- Handle success ---
            if not result_step.exists():
                return None, ErrorInfo(
                    file=str(script_path),
                    line=0,
                    type="MissingResult",
                    code=ErrorCode.E_RUNTIME,
                    message="Script completed but produced no result",
                    hint=f"Add '{RESULT_VARIABLE} = <your_shape>' at the end of the script",
                )

            try:
                from build123d import import_step
                shape = import_step(str(result_step))
                return shape, None
            except Exception as e:
                return None, ErrorInfo(
                    file=str(script_path),
                    line=0,
                    type="StepImportError",
                    code=ErrorCode.E_RUNTIME,
                    message=f"Failed to import result STEP: {e}",
                    hint=None,
                )

    @property
    def checkpoint_names(self) -> list[str]:
        """Checkpoint names collected from the last execution's stdout."""
        return list(self._checkpoint_names)

    @property
    def checkpoint_results(self) -> list[dict]:
        """Full checkpoint payloads (state + checks) from the last execution."""
        return list(self._checkpoint_results)
