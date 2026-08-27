"""Configuration management"""

import json
from pathlib import Path
from typing import Any, Optional

from .constants import DEFAULT_CONFIG


class Config:
    """Configuration manager for CAD CLI"""

    def __init__(self, project_dir: Path):
        """
        Initialize configuration

        Args:
            project_dir: Project root directory
        """
        self.project_dir = project_dir
        self.cad_dir = project_dir / ".cad"
        self.config_file = self.cad_dir / "config.json"
        self._config: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """
        Load configuration from file or use defaults

        Returns:
            Configuration dictionary
        """
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self._config = json.load(f)
        else:
            self._config = DEFAULT_CONFIG.copy()

        return self._config

    def save(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        Save configuration to file

        Args:
            config: Configuration dictionary (uses current if None)
        """
        if config is not None:
            self._config = config

        self.cad_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value

        Args:
            key: Configuration key (supports dot notation, e.g., "render.resolution")
            default: Default value if key not found

        Returns:
            Configuration value
        """
        if not self._config:
            self.load()

        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        if not self._config:
            self.load()

        keys = key.split('.')
        config = self._config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value
