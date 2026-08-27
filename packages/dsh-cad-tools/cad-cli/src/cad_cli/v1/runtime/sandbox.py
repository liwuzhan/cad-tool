"""Cross-platform timeout mechanism"""

import sys
import threading
from contextlib import contextmanager
from typing import Generator


class TimeoutError(Exception):
    """Raised when execution times out"""
    pass


@contextmanager
def timeout(seconds: int) -> Generator[None, None, None]:
    """
    Cross-platform timeout context manager

    Args:
        seconds: Timeout in seconds

    Raises:
        TimeoutError: If execution exceeds timeout
    """
    if sys.platform == 'win32':
        # Windows: use threading.Timer
        timer = None
        timed_out = threading.Event()

        def timeout_handler():
            timed_out.set()

        timer = threading.Timer(seconds, timeout_handler)
        timer.start()

        try:
            yield
            if timed_out.is_set():
                raise TimeoutError(f"Execution timed out after {seconds} seconds")
        finally:
            if timer:
                timer.cancel()
    else:
        # Unix: use signal.alarm
        import signal

        def timeout_handler(signum, frame):
            raise TimeoutError(f"Execution timed out after {seconds} seconds")

        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
