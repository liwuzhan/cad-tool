"""Main CLI entry point - v2.0

This module provides backwards compatibility by re-exporting from cli_v2.
The v2 CLI uses Model Packages (.456d) instead of .cad directories.
"""

# Re-export v2 CLI
from .cli_v2 import cli, main

__all__ = ["cli", "main"]
