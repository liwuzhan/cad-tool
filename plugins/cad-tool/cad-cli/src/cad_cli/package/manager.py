"""Model Package manager - Core class for managing .456d packages"""

from pathlib import Path
from typing import Optional

from .manifest import ManifestManager, PackageMetadata
from .artifact import ArtifactManager
from ..constants import DESIGN_DOC_FILENAME

DESIGN_DOC_TEMPLATE = """\
# {name} - 设计文档

## 零件描述
<!-- 功能用途、使用场景 -->


## 关键尺寸

| 参数 | 值 | 来源/备注 |
|------|------|-----------|
| 总长 (X) | mm | |
| 总宽 (Y) | mm | |
| 总高 (Z) | mm | |

## 建模策略
1.
2.
3.

## 约束校验
- [ ] 基体：expect_solids(1), expect_bbox_size(X, Y, Z)
"""


class ModelPackage:
    """
    Manages a .456d model package

    A model package is a self-contained directory with:
    - manifest.json: Package metadata and configuration
    - src/: Source scripts
    - vcs/: Version control data (commits.jsonl)
    - artifacts/: Build artifacts (STEP files, thumbnails, metrics)
    - runlog/: Execution logs
    """

    PACKAGE_EXTENSION = ".456d"
    SRC_DIR = "src"
    VCS_DIR = "vcs"
    ARTIFACTS_DIR = "artifacts"
    RUNLOG_DIR = "runlog"
    DEFAULT_SCRIPT = "main.py"

    def __init__(self, package_path: Path):
        """
        Initialize model package

        Args:
            package_path: Path to the .456d directory
        """
        self.package_path = package_path.resolve()
        self.manifest_manager = ManifestManager(package_path)
        self.artifact_manager = ArtifactManager(package_path)

        # Directory paths
        self.src_dir = package_path / self.SRC_DIR
        self.vcs_dir = package_path / self.VCS_DIR
        self.artifacts_dir = package_path / self.ARTIFACTS_DIR
        self.runlog_dir = package_path / self.RUNLOG_DIR

    @classmethod
    def create(
        cls,
        path: Path,
        name: str,
        create_default_script: bool = True,
    ) -> "ModelPackage":
        """
        Create a new model package

        Args:
            path: Path for the package (will add .456d if not present)
            name: Package name
            create_default_script: Whether to create a default main.py script

        Returns:
            ModelPackage instance

        Raises:
            FileExistsError: If package already exists
        """
        # Ensure .456d extension
        if not str(path).endswith(cls.PACKAGE_EXTENSION):
            path = Path(str(path) + cls.PACKAGE_EXTENSION)

        if path.exists():
            raise FileExistsError(f"Package already exists: {path}")

        # Create package directory
        path.mkdir(parents=True, exist_ok=False)

        # Create subdirectories
        (path / cls.SRC_DIR).mkdir()
        (path / cls.VCS_DIR).mkdir()
        (path / cls.ARTIFACTS_DIR).mkdir()
        (path / cls.RUNLOG_DIR).mkdir()

        # Initialize manifest
        package = cls(path)
        package.manifest_manager.create(name=name)

        # Create default script if requested
        if create_default_script:
            default_script = path / cls.SRC_DIR / cls.DEFAULT_SCRIPT
            default_script.write_text(
                "# CAD model script\n"
                "# 1. 先完成 design.md\n"
                "# 2. 参数定义在顶部\n"
                "# 3. 每个特征后添加 Checkpoint\n\n"
                "from build123d import *\n"
                "from cad_cli.feedback import Checkpoint\n\n"
                "Checkpoint.reset()\n\n"
                "# === 参数（从 design.md 尺寸表） ===\n"
                "length = 100\n"
                "width = 50\n"
                "height = 20\n\n"
                "# === 建模 ===\n"
                "with BuildPart() as part:\n"
                "    Box(length, width, height)\n"
                "    Checkpoint(part, 'base') \\\n"
                "        .expect_solids(1) \\\n"
                "        .expect_bbox_size(length, width, height, tolerance=0.1) \\\n"
                "        .verify()\n\n"
                "result = part.part\n",
                encoding='utf-8'
            )

        # Create design document
        design_doc = path / DESIGN_DOC_FILENAME
        design_doc.write_text(
            DESIGN_DOC_TEMPLATE.format(name=name),
            encoding='utf-8'
        )

        return package

    @classmethod
    def open(cls, path: Path) -> "ModelPackage":
        """
        Open an existing model package

        Args:
            path: Path to the .456d directory

        Returns:
            ModelPackage instance

        Raises:
            FileNotFoundError: If package doesn't exist
            ValueError: If path is not a valid package
        """
        if not path.exists():
            raise FileNotFoundError(f"Package not found: {path}")

        if not path.is_dir():
            raise ValueError(f"Not a directory: {path}")

        package = cls(path)

        # Verify it's a valid package
        if not package.manifest_manager.exists():
            raise ValueError(f"Invalid package (no manifest): {path}")

        return package

    @classmethod
    def find_package(cls, start_path: Optional[Path] = None) -> Optional["ModelPackage"]:
        """
        Find the nearest .456d package by walking up the directory tree

        Args:
            start_path: Starting path (defaults to current directory)

        Returns:
            ModelPackage instance or None if not found
        """
        if start_path is None:
            start_path = Path.cwd()

        current = start_path.resolve()

        # Check if we're inside a .456d directory
        while current != current.parent:
            if str(current).endswith(cls.PACKAGE_EXTENSION):
                manifest_path = current / ManifestManager.MANIFEST_FILENAME
                if manifest_path.exists():
                    return cls(current)

            # Check if current directory contains a .456d subdirectory
            for child in current.iterdir():
                if child.is_dir() and str(child).endswith(cls.PACKAGE_EXTENSION):
                    manifest_path = child / ManifestManager.MANIFEST_FILENAME
                    if manifest_path.exists():
                        return cls(child)

            current = current.parent

        return None

    def get_manifest(self) -> PackageMetadata:
        """
        Get package manifest

        Returns:
            PackageMetadata object
        """
        return self.manifest_manager.metadata

    def update_manifest(self, **updates) -> PackageMetadata:
        """
        Update package manifest

        Args:
            **updates: Fields to update

        Returns:
            Updated PackageMetadata
        """
        return self.manifest_manager.update(**updates)

    def get_default_script(self) -> Path:
        """
        Get path to the default script (src/main.py)

        Returns:
            Path to main.py
        """
        return self.src_dir / self.DEFAULT_SCRIPT

    def get_design_doc(self) -> Path:
        """
        Get path to the design document (design.md)

        Returns:
            Path to design.md
        """
        return self.package_path / DESIGN_DOC_FILENAME

    def get_artifact_dir(self, commit_hash: str) -> Path:
        """
        Get artifact directory for a commit

        Args:
            commit_hash: Commit hash

        Returns:
            Path to artifact directory
        """
        return self.artifact_manager.get_artifact_dir(commit_hash)

    def exists(self) -> bool:
        """
        Check if package exists and is valid

        Returns:
            True if package is valid
        """
        return (
            self.package_path.exists() and
            self.package_path.is_dir() and
            self.manifest_manager.exists()
        )

    def __repr__(self) -> str:
        """String representation"""
        return f"ModelPackage({self.package_path})"

    def __str__(self) -> str:
        """Human-readable string"""
        try:
            metadata = self.get_manifest()
            return f"ModelPackage: {metadata.name} at {self.package_path}"
        except Exception:
            return f"ModelPackage at {self.package_path}"
