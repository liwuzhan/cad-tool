"""Artifact management for model packages"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from build123d import Shape

from ..constants import ErrorCode
from ..models import ErrorInfo


class ArtifactManager:
    """Manages artifacts within a model package (STEP, thumbnails, metrics, scripts)"""

    STEP_FILENAME = "model.step"
    SCRIPT_FILENAME = "script.py"
    DESIGN_DOC_FILENAME = "design.md"
    METRICS_FILENAME = "metrics.json"
    VALIDATE_FILENAME = "validate.json"

    def __init__(self, package_path: Path):
        """
        Initialize artifact manager

        Args:
            package_path: Path to the .456d package directory
        """
        self.package_path = package_path
        self.artifacts_dir = package_path / "artifacts"

    def get_artifact_dir(self, commit_hash: str) -> Path:
        """
        Get the artifact directory for a specific commit

        Args:
            commit_hash: Commit hash

        Returns:
            Path to the artifact directory
        """
        return self.artifacts_dir / commit_hash

    def ensure_artifact_dir(self, commit_hash: str) -> Path:
        """
        Ensure artifact directory exists

        Args:
            commit_hash: Commit hash

        Returns:
            Path to the artifact directory
        """
        artifact_dir = self.get_artifact_dir(commit_hash)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def save_step(self, shape: "Shape", commit_hash: str) -> Path:
        """
        Save shape as STEP file

        Args:
            shape: build123d Shape object
            commit_hash: Commit hash

        Returns:
            Path to the STEP file
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)
        step_path = artifact_dir / self.STEP_FILENAME

        # Use the Compound-fallback exporter (build123d 0.11 STEP re-export bug)
        from ..utils.geometry import export_step_safe
        export_step_safe(shape, step_path)

        return step_path

    def load_step(self, commit_hash: str) -> Optional["Shape"]:
        """
        Load shape from STEP file

        Args:
            commit_hash: Commit hash

        Returns:
            Shape object or None if not found
        """
        step_path = self.get_artifact_dir(commit_hash) / self.STEP_FILENAME

        if not step_path.exists():
            return None

        try:
            from build123d import import_step
            shape = import_step(str(step_path))
            return shape
        except Exception:
            return None

    def step_exists(self, commit_hash: str) -> bool:
        """
        Check if STEP file exists for commit

        Args:
            commit_hash: Commit hash

        Returns:
            True if STEP exists
        """
        step_path = self.get_artifact_dir(commit_hash) / self.STEP_FILENAME
        return step_path.exists()

    def save_script(self, commit_hash: str, script_path: Path) -> Path:
        """
        Save script snapshot to artifacts

        Args:
            commit_hash: Commit hash
            script_path: Path to the script file to save

        Returns:
            Path to the saved script in artifacts
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)
        script_artifact = artifact_dir / self.SCRIPT_FILENAME

        shutil.copy2(script_path, script_artifact)
        return script_artifact

    def load_script(self, commit_hash: str) -> Optional[str]:
        """
        Load script content from artifacts

        Args:
            commit_hash: Commit hash

        Returns:
            Script content as string, or None if not found
        """
        script_path = self.get_artifact_dir(commit_hash) / self.SCRIPT_FILENAME

        if not script_path.exists():
            return None

        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    def script_exists(self, commit_hash: str) -> bool:
        """
        Check if script exists for commit

        Args:
            commit_hash: Commit hash

        Returns:
            True if script exists
        """
        script_path = self.get_artifact_dir(commit_hash) / self.SCRIPT_FILENAME
        return script_path.exists()

    def save_design_doc(self, commit_hash: str, design_doc_path: Path) -> Path:
        """
        Save design document snapshot to artifacts

        Args:
            commit_hash: Commit hash
            design_doc_path: Path to the design.md file to save

        Returns:
            Path to the saved design doc in artifacts
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)
        design_artifact = artifact_dir / self.DESIGN_DOC_FILENAME

        shutil.copy2(design_doc_path, design_artifact)
        return design_artifact

    def load_design_doc(self, commit_hash: str) -> Optional[str]:
        """
        Load design document content from artifacts

        Args:
            commit_hash: Commit hash

        Returns:
            Design doc content as string, or None if not found
        """
        design_path = self.get_artifact_dir(commit_hash) / self.DESIGN_DOC_FILENAME

        if not design_path.exists():
            return None

        try:
            with open(design_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return None

    def design_doc_exists(self, commit_hash: str) -> bool:
        """
        Check if design document exists for commit

        Args:
            commit_hash: Commit hash

        Returns:
            True if design doc exists
        """
        design_path = self.get_artifact_dir(commit_hash) / self.DESIGN_DOC_FILENAME
        return design_path.exists()

    def save_thumbnail(
        self,
        commit_hash: str,
        view_name: str,
        png_path: Path,
        camera_params: dict[str, Any],
        resolution: tuple[int, int],
    ) -> tuple[Path, Path]:
        """
        Save thumbnail and its metadata

        Args:
            commit_hash: Commit hash
            view_name: View name (e.g., "iso", "top")
            png_path: Source PNG path to copy
            camera_params: Camera parameters dict
            resolution: Image resolution (width, height)

        Returns:
            Tuple of (png_path, json_path) in artifacts
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)

        # Define output paths
        thumb_png = artifact_dir / f"thumb_{view_name}.png"
        thumb_json = artifact_dir / f"thumb_{view_name}.json"

        # Copy PNG to artifacts
        shutil.copy2(png_path, thumb_png)

        # Save metadata
        metadata = {
            "view": view_name,
            "camera": camera_params,
            "resolution": list(resolution),
            "timestamp": datetime.now().isoformat(),
        }

        with open(thumb_json, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        return thumb_png, thumb_json

    def save_metrics(self, commit_hash: str, metrics: dict[str, Any]) -> Path:
        """
        Save geometry metrics

        Args:
            commit_hash: Commit hash
            metrics: Metrics dictionary

        Returns:
            Path to the metrics file
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)
        metrics_path = artifact_dir / self.METRICS_FILENAME

        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2)

        return metrics_path

    def load_metrics(self, commit_hash: str) -> Optional[dict[str, Any]]:
        """
        Load metrics for a commit

        Args:
            commit_hash: Commit hash

        Returns:
            Metrics dictionary or None
        """
        metrics_path = self.get_artifact_dir(commit_hash) / self.METRICS_FILENAME

        if not metrics_path.exists():
            return None

        try:
            with open(metrics_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def save_validation(self, commit_hash: str, validation_result: dict[str, Any]) -> Path:
        """
        Save validation results

        Args:
            commit_hash: Commit hash
            validation_result: Validation result dictionary

        Returns:
            Path to the validation file
        """
        artifact_dir = self.ensure_artifact_dir(commit_hash)
        validate_path = artifact_dir / self.VALIDATE_FILENAME

        with open(validate_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)

        return validate_path

    def list_artifacts(self) -> list[dict[str, Any]]:
        """
        List all artifacts in the package

        Returns:
            List of artifact info dictionaries
        """
        artifacts = []

        if not self.artifacts_dir.exists():
            return artifacts

        for commit_dir in sorted(self.artifacts_dir.iterdir()):
            if not commit_dir.is_dir():
                continue

            commit_hash = commit_dir.name
            artifact_info = {
                "commit": commit_hash,
                "files": [],
                "size_bytes": 0,
            }

            for file_path in commit_dir.iterdir():
                if file_path.is_file():
                    size = file_path.stat().st_size
                    artifact_info["files"].append({
                        "name": file_path.name,
                        "size": size,
                    })
                    artifact_info["size_bytes"] += size

            artifacts.append(artifact_info)

        return artifacts

    def get_total_size(self) -> int:
        """
        Get total size of all artifacts in bytes

        Returns:
            Total size in bytes
        """
        total = 0
        if not self.artifacts_dir.exists():
            return total

        for path in self.artifacts_dir.rglob('*'):
            if path.is_file():
                total += path.stat().st_size

        return total

    def cleanup_by_policy(self, policy: str, keep_commits: Optional[list[str]] = None) -> list[str]:
        """
        Clean up artifacts based on policy

        Args:
            policy: Cleanup policy ('all_commits' | 'latest_per_branch' | 'releases_only')
            keep_commits: List of commit hashes to always keep

        Returns:
            List of deleted commit hashes
        """
        keep_commits = keep_commits or []
        deleted = []

        if not self.artifacts_dir.exists():
            return deleted

        all_commits = [d.name for d in self.artifacts_dir.iterdir() if d.is_dir()]

        if policy == "all_commits":
            # Keep all, only delete if explicitly not in keep_commits
            return deleted

        elif policy == "releases_only":
            # Delete all except explicitly kept
            for commit_hash in all_commits:
                if commit_hash not in keep_commits:
                    self.delete_artifacts(commit_hash)
                    deleted.append(commit_hash)

        elif policy == "latest_per_branch":
            # Delete all except the latest (keep_commits should contain branch heads)
            for commit_hash in all_commits:
                if commit_hash not in keep_commits:
                    self.delete_artifacts(commit_hash)
                    deleted.append(commit_hash)

        return deleted

    def delete_artifacts(self, commit_hash: str) -> bool:
        """
        Delete artifacts for a commit

        Args:
            commit_hash: Commit hash

        Returns:
            True if deleted, False if not found
        """
        artifact_dir = self.get_artifact_dir(commit_hash)

        if not artifact_dir.exists():
            return False

        shutil.rmtree(artifact_dir)
        return True
