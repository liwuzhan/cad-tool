"""Storage utilities for VCS"""

import json
from pathlib import Path
from typing import Any, Dict


def save_json(data: Dict[str, Any], file_path: Path) -> None:
    """
    Save data to JSON file

    Args:
        data: Data to save
        file_path: Output file path
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_json(file_path: Path) -> Dict[str, Any]:
    """
    Load data from JSON file

    Args:
        file_path: Input file path

    Returns:
        Loaded data dictionary
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
