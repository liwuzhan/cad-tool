"""Script executor for build123d scripts"""

import pickle
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..config import Config
from ..constants import RESULT_VARIABLE, ErrorCode
from ..models import ErrorInfo
from .sandbox import timeout, TimeoutError
from .error_handler import format_syntax_error, format_runtime_error, format_timeout_error


class ScriptExecutor:
    """Executes build123d scripts and manages shape state"""

    def __init__(self, project_dir: Path):
        """
        Initialize executor

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self.cad_dir = project_dir / ".cad"
        self.config = Config(project_dir)
        self.config.load()
        self.timeout_seconds = self.config.get("timeout_seconds", 60)
        self._shape_cache_path = self.cad_dir / "runlog" / "current_shape.pkl"

    def execute(self, script_path: Path) -> tuple[Optional["Shape"], Optional[ErrorInfo]]:
        """
        Execute a build123d script

        Convention: Script must assign final result to 'result' variable

        Args:
            script_path: Path to the script file

        Returns:
            Tuple of (shape, error) - one will be None
        """
        try:
            # Read and compile script
            with open(script_path, 'r', encoding='utf-8') as f:
                code_str = f.read()

            try:
                code = compile(code_str, str(script_path), 'exec')
            except SyntaxError as e:
                return None, format_syntax_error(e, script_path)

            # Execute with timeout
            namespace: dict[str, Any] = {}

            try:
                with timeout(self.timeout_seconds):
                    exec(code, namespace)
            except TimeoutError:
                return None, format_timeout_error(script_path, self.timeout_seconds)

            # Check for result variable
            if RESULT_VARIABLE not in namespace:
                return None, ErrorInfo(
                    file=str(script_path),
                    line=0,
                    type="MissingResult",
                    code=ErrorCode.E_RUNTIME,
                    message=f"Script must define '{RESULT_VARIABLE}' variable",
                    hint=f"Add '{RESULT_VARIABLE} = <your_shape>' at the end of the script"
                )

            shape = namespace[RESULT_VARIABLE]

            # Validate that result is a Shape
            if not self._is_valid_shape(shape):
                return None, ErrorInfo(
                    file=str(script_path),
                    line=0,
                    type="InvalidResult",
                    code=ErrorCode.E_RUNTIME,
                    message=f"'{RESULT_VARIABLE}' must be a build123d Shape object",
                    hint="Ensure result is a valid Shape (Box, Cylinder, etc.)"
                )

            # Cache the shape for later use
            self._save_current_shape(shape)

            return shape, None

        except SyntaxError as e:
            return None, format_syntax_error(e, script_path)
        except Exception as e:
            return None, format_runtime_error(e, script_path)

    def load_current_shape(self) -> Optional["Shape"]:
        """
        Load the most recently executed shape

        Returns:
            Shape object or None if not available
        """
        if not self._shape_cache_path.exists():
            return None

        try:
            with open(self._shape_cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            return None

    def _save_current_shape(self, shape: "Shape") -> None:
        """
        Save shape to cache for later use

        Args:
            shape: Shape to save
        """
        self._shape_cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._shape_cache_path, 'wb') as f:
            pickle.dump(shape, f)

    def _is_valid_shape(self, obj: Any) -> bool:
        """
        Check if object is a valid build123d Shape

        Args:
            obj: Object to check

        Returns:
            True if valid Shape
        """
        # Check for common Shape attributes
        return (
            hasattr(obj, 'volume') and
            hasattr(obj, 'area') and
            hasattr(obj, 'bounding_box') and
            hasattr(obj, 'faces') and
            hasattr(obj, 'edges') and
            hasattr(obj, 'vertices')
        )
