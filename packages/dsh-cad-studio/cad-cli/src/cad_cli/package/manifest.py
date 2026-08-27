"""Package manifest management for model packages (.456d)"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class PackageMetadata:
    """Metadata stored in manifest.json"""
    name: str
    kind: str = "part"  # part | assembly
    version: str = "2.0.0"
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    head: Optional[str] = None  # Current commit hash
    branches: dict[str, str] = field(default_factory=lambda: {"main": None})
    current_branch: str = "main"
    artifact_policy: str = "latest_per_branch"  # all_commits | latest_per_branch | releases_only
    unit: str = "mm"
    timeout_seconds: int = 60
    render: dict[str, Any] = field(default_factory=lambda: {
        "default_views": ["top", "front", "right", "iso"],
        "image_format": "png",
        "resolution": [800, 600]
    })

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackageMetadata":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class ManifestManager:
    """Manages manifest.json for model packages"""

    MANIFEST_FILENAME = "manifest.json"

    def __init__(self, package_path: Path):
        """
        Initialize manifest manager

        Args:
            package_path: Path to the .456d package directory
        """
        self.package_path = package_path
        self.manifest_path = package_path / self.MANIFEST_FILENAME
        self._metadata: Optional[PackageMetadata] = None

    def exists(self) -> bool:
        """Check if manifest exists"""
        return self.manifest_path.exists()

    def load(self) -> PackageMetadata:
        """
        Load manifest from file

        Returns:
            PackageMetadata object

        Raises:
            FileNotFoundError: If manifest doesn't exist
            ValueError: If manifest is invalid
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        try:
            with open(self.manifest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._metadata = PackageMetadata.from_dict(data)
            return self._metadata
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid manifest JSON: {e}")

    def save(self, metadata: Optional[PackageMetadata] = None) -> None:
        """
        Save manifest to file

        Args:
            metadata: Metadata to save (uses cached if None)
        """
        if metadata is not None:
            self._metadata = metadata

        if self._metadata is None:
            raise ValueError("No metadata to save")

        self.package_path.mkdir(parents=True, exist_ok=True)

        with open(self.manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self._metadata.to_dict(), f, indent=2, ensure_ascii=False)

    def create(self, name: str, **kwargs) -> PackageMetadata:
        """
        Create a new manifest with default values

        Args:
            name: Package name
            **kwargs: Override default metadata values

        Returns:
            PackageMetadata object
        """
        self._metadata = PackageMetadata(name=name, **kwargs)
        self.save()
        return self._metadata

    def update(self, **updates) -> PackageMetadata:
        """
        Update manifest with new values

        Args:
            **updates: Fields to update

        Returns:
            Updated PackageMetadata
        """
        if self._metadata is None:
            self.load()

        for key, value in updates.items():
            if hasattr(self._metadata, key):
                setattr(self._metadata, key, value)

        self.save()
        return self._metadata

    def update_nested(self, key: str, value: Any) -> PackageMetadata:
        """
        Update a nested manifest value using dot notation

        Args:
            key: Key to update (supports dot notation like "branches.main")
            value: Value to set

        Returns:
            Updated PackageMetadata

        Raises:
            ValueError: If key path is invalid
        """
        if self._metadata is None:
            self.load()

        keys = key.split('.')

        if len(keys) == 1:
            # Top-level attribute
            if hasattr(self._metadata, keys[0]):
                setattr(self._metadata, keys[0], value)
            else:
                raise ValueError(f"Unknown attribute: {keys[0]}")
        else:
            # Nested dict access
            obj = self._metadata
            for k in keys[:-1]:
                if hasattr(obj, k):
                    obj = getattr(obj, k)
                else:
                    raise ValueError(f"Invalid key path: {key}")

            # Set the final value
            if isinstance(obj, dict):
                obj[keys[-1]] = value
            else:
                raise ValueError(f"Cannot set nested value on non-dict: {key}")

        self.save()
        return self._metadata

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a specific manifest value

        Args:
            key: Key to retrieve (supports dot notation)
            default: Default value if not found

        Returns:
            Value or default
        """
        if self._metadata is None:
            self.load()

        keys = key.split('.')
        value = self._metadata.to_dict()

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def metadata(self) -> PackageMetadata:
        """Get cached or load metadata"""
        if self._metadata is None:
            self.load()
        return self._metadata
