"""JSONL event stream utilities"""

import json
import sys
from datetime import datetime
from typing import Any


def json_safe(value: Any) -> Any:
    """Return a copy of ``value`` that survives a strict JSON round trip.

    The event stream is consumed by JavaScript, where ``JSON.parse("-0.0")``
    yields ``-0`` and ``JSON.stringify(-0)`` yields ``"0"``: a negative zero
    therefore comes back as a different value and lossless-round-trip validators
    reject the whole message.  ``NaN``/``Infinity`` are not legal JSON at all,
    so they are reported as ``null`` instead of corrupting the stream.
    """
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value + 0.0
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


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
        "payload": json_safe(payload)
    }
    print(json.dumps(event_data, ensure_ascii=False), flush=True)


def emit_error(error_info: dict[str, Any]) -> None:
    """
    Output an error event to stdout

    Args:
        error_info: Error information dictionary
    """
    emit_event("error", error_info)
