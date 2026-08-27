"""Error handling and formatting"""

import traceback
import sys
from pathlib import Path
from typing import Optional

from ..constants import ErrorCode
from ..models import ErrorInfo


def format_syntax_error(e: SyntaxError, script_path: Path) -> ErrorInfo:
    """
    Format a SyntaxError into ErrorInfo

    Args:
        e: SyntaxError exception
        script_path: Path to the script file

    Returns:
        ErrorInfo object
    """
    return ErrorInfo(
        file=str(script_path),
        line=e.lineno or 0,
        type="SyntaxError",
        code=ErrorCode.E_SYNTAX,
        message=str(e.msg) if e.msg else str(e),
        hint=f"Check syntax near line {e.lineno}" if e.lineno else None
    )


def format_runtime_error(e: Exception, script_path: Path) -> ErrorInfo:
    """
    Format a runtime error into ErrorInfo

    Args:
        e: Exception
        script_path: Path to the script file

    Returns:
        ErrorInfo object
    """
    # Extract line number from traceback
    tb = traceback.extract_tb(e.__traceback__)
    line = 0
    for frame in reversed(tb):
        if frame.filename == str(script_path):
            line = frame.lineno
            break

    return ErrorInfo(
        file=str(script_path),
        line=line,
        type=type(e).__name__,
        code=ErrorCode.E_RUNTIME,
        message=str(e),
        hint=_get_hint_for_error(e)
    )


def format_timeout_error(script_path: Path, timeout_seconds: int) -> ErrorInfo:
    """
    Format a timeout error into ErrorInfo

    Args:
        script_path: Path to the script file
        timeout_seconds: Timeout value

    Returns:
        ErrorInfo object
    """
    return ErrorInfo(
        file=str(script_path),
        line=0,
        type="TimeoutError",
        code=ErrorCode.E_RUNTIME,
        message=f"Script execution timed out after {timeout_seconds} seconds",
        hint="Check for infinite loops or reduce computation complexity"
    )


def _get_hint_for_error(e: Exception) -> Optional[str]:
    """
    Get a helpful hint for common errors

    Args:
        e: Exception

    Returns:
        Hint string or None
    """
    error_type = type(e).__name__
    error_msg = str(e).lower()

    if error_type == "NameError":
        if "result" in error_msg:
            return "Script must define a 'result' variable with the final shape"
        return "Check variable names and imports"

    if error_type == "ImportError" or error_type == "ModuleNotFoundError":
        return "Check that all required modules are installed"

    if error_type == "TypeError":
        return "Check function arguments and types"

    if error_type == "ValueError":
        return "Check input values and constraints"

    return None
