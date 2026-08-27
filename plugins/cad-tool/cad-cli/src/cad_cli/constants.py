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


# Script execution convention
RESULT_VARIABLE = "result"

# Design document filename
DESIGN_DOC_FILENAME = "design.md"
