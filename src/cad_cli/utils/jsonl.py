"""JSONL event stream utilities"""

import json
import sys
from datetime import datetime
from typing import Any


def emit_event(event: str, payload: dict[str, Any]) -> None:
    """
    Output a JSONL event to stdout

    Args:
        event: Event name
        payload: Event payload data
    """
    event_data = {
        "event": event,
        "ts": datetime.now().isoformat(),
        "payload": payload
    }
    print(json.dumps(event_data, ensure_ascii=False), flush=True)


def emit_error(error_info: dict[str, Any]) -> None:
    """
    Output an error event to stdout

    Args:
        error_info: Error information dictionary
    """
    emit_event("error", error_info)
