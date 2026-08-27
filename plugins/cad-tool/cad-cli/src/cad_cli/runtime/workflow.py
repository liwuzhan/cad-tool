"""Build workflow orchestrator for v2"""

from datetime import datetime
import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..models import ErrorInfo
from ..package import ModelPackage
from ..runtime.executor_v2 import ScriptExecutorV2
from ..runtime.validator import GeometryValidator
from ..feedback.renderer_v2 import OffscreenRendererV2
from ..feedback.camera import STANDARD_VIEWS
from ..utils.geometry import compute_metrics
from ..vcs.commits import CommitRecord, generate_commit_hash


class BuildWorkflow:
    """
    Orchestrates the complete build workflow:
    1. Execute script
    2. Validate geometry
    3. Save STEP artifact
    4. Render thumbnails
    5. Save metrics
    6. Create commit record
    """

    def __init__(self, package: ModelPackage):
        """
        Initialize build workflow

        Args:
            package: ModelPackage instance
        """
        self.package = package
        self.executor = ScriptExecutorV2(package)
        self.validator = GeometryValidator()
        self.renderer = OffscreenRendererV2(package)

    def build(
        self,
        script_path: Optional[Path] = None,
        commit_message: Optional[str] = None,
        render_views: Optional[list[str]] = None,
    ) -> tuple[Optional[CommitRecord], Optional[ErrorInfo]]:
        """
        Execute full build workflow

        Args:
            script_path: Path to script (defaults to src/main.py)
            commit_message: Commit message (if None, no commit is created)
            render_views: Views to render (defaults to manifest.render.default_views)

        Returns:
            Tuple of (CommitRecord, ErrorInfo) - one will be None
        """
        # Default to main script
        if script_path is None:
            script_path = self.package.get_default_script()

        if not script_path.exists():
            return None, ErrorInfo(
                file=str(script_path),
                line=0,
                type="FileNotFound",
                code="E-IO",
                message=f"Script not found: {script_path}",
                hint="Create a script at src/main.py or specify a different path"
            )

        # Step 1: Execute script
        shape, error = self.executor.execute(script_path)
        if error:
            return None, error

        # Step 2: Validate geometry
        validation_errors = self.validator.validate(shape)
        if validation_errors:
            # Emit validation warnings (non-fatal)
            from ..utils.jsonl import emit_event
            emit_event("validation_warning", {
                "warning_count": len(validation_errors),
                "warnings": [e.to_dict() for e in validation_errors]
            })

        # Step 3: Compute metrics
        metrics = compute_metrics(shape)

        # If no commit message, return here (just a build, not a commit)
        if commit_message is None:
            return None, None

        # Generate commit
        timestamp = datetime.now()
        parent_commit = self.package.manifest_manager.metadata.head
        commit_hash = generate_commit_hash(commit_message, timestamp, parent_commit)

        # Step 4: Save STEP artifact
        try:
            self.package.artifact_manager.save_step(shape, commit_hash)
        except Exception as e:
            return None, ErrorInfo(
                file=str(script_path),
                line=0,
                type="ArtifactError",
                code="E-IO",
                message=f"Failed to save STEP artifact: {e}",
                hint=None
            )

        # Step 4.5: Save script snapshot
        try:
            self.package.artifact_manager.save_script(commit_hash, script_path)
        except Exception as e:
            # Script save failure is not fatal, but log it
            pass

        # Step 4.6: Save design doc snapshot
        try:
            design_doc_path = self.package.get_design_doc()
            if design_doc_path.exists():
                self.package.artifact_manager.save_design_doc(commit_hash, design_doc_path)
        except Exception:
            pass

        # Step 5: Render thumbnails
        manifest = self.package.get_manifest()
        render_disabled = os.environ.get("CAD_SKIP_RENDER", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if render_disabled:
            render_views = []
        elif render_views is None:
            render_views = manifest.render.get("default_views", ["iso"])

        thumbnails_created = []
        for view_name in render_views:
            if view_name not in STANDARD_VIEWS:
                continue

            try:
                # Create temp PNG first
                temp_png = self.package.runlog_dir / f"temp_{view_name}.png"
                temp_json = self.package.runlog_dir / f"temp_{view_name}.json"

                metadata = self.renderer.render(
                    shape,
                    STANDARD_VIEWS[view_name],
                    temp_png,
                    temp_json
                )

                # Move to artifacts with metadata
                camera_params = metadata["camera"]
                resolution = tuple(metadata["resolution"])

                self.package.artifact_manager.save_thumbnail(
                    commit_hash,
                    view_name,
                    temp_png,
                    camera_params,
                    resolution
                )

                # Clean up temp files
                temp_png.unlink(missing_ok=True)
                temp_json.unlink(missing_ok=True)

                thumbnails_created.append(view_name)

            except Exception as e:
                # Thumbnail rendering failure is not fatal
                pass

        # Step 6: Save metrics
        self.package.artifact_manager.save_metrics(commit_hash, metrics.to_dict())

        # Step 7: Save validation results
        validation_result = {
            "valid": len(validation_errors) == 0,
            "errors": [e.to_dict() for e in validation_errors],
            "timestamp": timestamp.isoformat()
        }
        self.package.artifact_manager.save_validation(commit_hash, validation_result)

        # Step 8: Create commit record
        commit_record = CommitRecord(
            hash=commit_hash,
            message=commit_message,
            timestamp=timestamp.isoformat(),
            script_path=str(script_path.resolve().relative_to(self.package.package_path.resolve())),
            parent_hash=parent_commit,
            branch=manifest.current_branch,
            metrics_hash=None,  # Could add SHA256 of metrics in the future
            has_step=True,
            has_thumbnails=len(thumbnails_created) > 0
        )

        # Step 9: Update manifest HEAD and branch head pointer
        self.package.update_manifest(head=commit_hash)
        self.package.manifest_manager.update_nested(
            f"branches.{manifest.current_branch}",
            commit_hash
        )

        return commit_record, None
