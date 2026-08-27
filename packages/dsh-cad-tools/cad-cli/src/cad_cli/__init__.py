"""CAD CLI v2.0 - AI-Native CAD with Model Packages

Key v2.0 features:
- Model packages (.456d) instead of .cad directories
- STEP artifacts instead of pickle caching
- Render outputs with JSON metadata
- JSONL commit history
"""

__version__ = "2.0.0"

from .package import ModelPackage, PackageMetadata, ArtifactManager
from .vcs import CommitHistory, CommitRecord, Repository
from .runtime import ScriptExecutorV2, GeometryValidator, BuildWorkflow

__all__ = [
    "ModelPackage",
    "PackageMetadata",
    "ArtifactManager",
    "CommitHistory",
    "CommitRecord",
    "Repository",
    "ScriptExecutorV2",
    "GeometryValidator",
    "BuildWorkflow",
]
