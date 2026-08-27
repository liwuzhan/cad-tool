"""Repository for version control"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Dict, Any

if TYPE_CHECKING:
    from build123d import Shape

from ..config import Config
from ..constants import DEFAULT_CONFIG
from ..models import CommitData, GeometryMetrics
from ..utils.geometry import compute_metrics
from .commit import create_commit_hash, dict_to_commit
from .storage import save_json, load_json


class Repository:
    """Git-like repository for CAD projects"""

    def __init__(self, project_dir: Path):
        """
        Initialize repository

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self.cad_dir = project_dir / ".cad"
        self.commits_dir = self.cad_dir / "commits"
        self.runlog_dir = self.cad_dir / "runlog"
        self.thumbs_dir = self.cad_dir / "thumbs"
        self.config = Config(project_dir)

    def init(self) -> None:
        """Initialize a new repository"""
        # Create directory structure
        self.commits_dir.mkdir(parents=True, exist_ok=True)
        self.runlog_dir.mkdir(parents=True, exist_ok=True)
        self.thumbs_dir.mkdir(parents=True, exist_ok=True)

        # Create default configuration
        self.config.save(DEFAULT_CONFIG.copy())

    def commit(self, message: str, shape: "Shape", script_path: str = "main.py") -> CommitData:
        """
        Create a new commit

        Args:
            message: Commit message
            shape: Shape to commit
            script_path: Path to the script (default: main.py)

        Returns:
            CommitData object
        """
        timestamp = datetime.now()

        # Compute geometry metrics
        metrics = compute_metrics(shape)

        # Generate thumbnail (iso view)
        thumbnail_path = None
        try:
            from ..feedback.renderer import OffscreenRenderer
            from ..feedback.camera import STANDARD_VIEWS

            renderer = OffscreenRenderer(self.project_dir)
            thumbnail_filename = f"commit_{timestamp.strftime('%Y%m%d_%H%M%S')}.png"
            thumbnail_path_obj = self.thumbs_dir / thumbnail_filename
            renderer.render(shape, STANDARD_VIEWS["iso"], thumbnail_path_obj)
            thumbnail_path = str(thumbnail_path_obj.relative_to(self.project_dir))
        except Exception:
            # Rendering failed, continue without thumbnail
            pass

        # Create commit hash
        commit_hash = create_commit_hash(message, timestamp)

        # Create commit data
        commit_data = CommitData(
            hash=commit_hash,
            message=message,
            timestamp=timestamp.isoformat(),
            script_path=script_path,
            metrics=metrics.to_dict(),
            thumbnail_path=thumbnail_path
        )

        # Save commit
        commit_file = self.commits_dir / f"{commit_hash}.json"
        save_json(commit_data.to_dict(), commit_file)

        return commit_data

    def log(self) -> List[CommitData]:
        """
        Get commit history

        Returns:
            List of CommitData objects, sorted by timestamp (newest first)
        """
        if not self.commits_dir.exists():
            return []

        commits = []
        for commit_file in self.commits_dir.glob("*.json"):
            try:
                data = load_json(commit_file)
                commits.append(dict_to_commit(data))
            except Exception:
                # Skip invalid commit files
                continue

        # Sort by timestamp (newest first)
        commits.sort(key=lambda c: c.timestamp, reverse=True)

        return commits

    def status(self) -> Dict[str, Any]:
        """
        Get current repository status

        Returns:
            Status dictionary with current commit and change information
        """
        commits = self.log()
        current_commit = commits[0] if commits else None

        # Check if main.py has been modified
        has_changes = False
        main_script = self.project_dir / "main.py"

        if current_commit and main_script.exists():
            try:
                # Compare modification time
                script_mtime = main_script.stat().st_mtime
                commit_time = datetime.fromisoformat(current_commit.timestamp).timestamp()
                has_changes = script_mtime > commit_time
            except Exception:
                pass

        return {
            "current_commit": current_commit.hash if current_commit else None,
            "has_changes": has_changes,
            "total_commits": len(commits)
        }

    def get_commit(self, commit_hash: str) -> Optional[CommitData]:
        """
        Get a specific commit by hash

        Args:
            commit_hash: Commit hash

        Returns:
            CommitData object or None if not found
        """
        commit_file = self.commits_dir / f"{commit_hash}.json"
        if not commit_file.exists():
            return None

        try:
            data = load_json(commit_file)
            return dict_to_commit(data)
        except Exception:
            return None
