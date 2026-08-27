"""Constants and error codes for CAD CLI"""

from enum import Enum


class ErrorCode(str, Enum):
    """Error codes for different failure types"""
    E_SYNTAX = "E-SYNTAX"
    E_RUNTIME = "E-RUNTIME"
    E_CONSTRAINT = "E-CONSTRAINT"
    E_BREP = "E-BREP"
    E_RENDER = "E-RENDER"
    E_IO = "E-IO"


# Default configuration values
DEFAULT_CONFIG = {
    "unit": "mm",
    "timeout_seconds": 60,
    "render": {
        "default_views": ["top", "front", "right", "iso"],
        "image_format": "png",
        "resolution": [800, 600]
    }
}

# Script execution convention
RESULT_VARIABLE = "result"
