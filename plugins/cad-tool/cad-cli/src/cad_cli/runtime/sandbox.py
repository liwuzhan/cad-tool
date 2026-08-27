"""Cross-platform timeout mechanism

On Unix: uses signal.alarm for reliable async interruption.
On Windows: uses ctypes.PyThreadState_SetAsyncExc to inject an exception
into the main thread from a timer thread — actually interrupts exec().
"""

import sys
import threading
import ctypes
from contextlib import contextmanager
from typing import Generator


class TimeoutError(Exception):
    """Raised when execution times out"""
    pass


def _async_raise(thread_id: int, exc_type: type) -> None:
    """Raise an exception in the target thread via ctypes.

    Args:
        thread_id: Thread identifier to target.
        exc_type: Exception type to raise.

    Raises:
        ValueError: If thread_id is invalid.
        SystemError: If the raise failed unexpectedly.
    """
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(thread_id),
        ctypes.py_object(exc_type),
    )
    if res == 0:
        raise ValueError(f"Invalid thread ID: {thread_id}")
    elif res > 1:
        # Reset it — too many threads matched
        ctypes.pythonapi.PyThreadState_SetAsyncExc(
            ctypes.c_ulong(thread_id), None
        )
        raise SystemError("PyThreadState_SetAsyncExc failed")


@contextmanager
def timeout(seconds: int) -> Generator[None, None, None]:
    """
    Cross-platform timeout context manager that actually interrupts execution.

    On Unix: uses signal.alarm (raises TimeoutError via signal handler).
    On Windows: uses ctypes.PyThreadState_SetAsyncExc to inject TimeoutError
        into the main thread from a timer thread.

    Args:
        seconds: Timeout in seconds

    Raises:
        TimeoutError: If execution exceeds timeout
    """
    if sys.platform == 'win32':
        # Windows: inject exception into main thread via ctypes
        main_thread_id = threading.current_thread().ident

        def _on_timeout():
            _async_raise(main_thread_id, TimeoutError)

        timer = threading.Timer(seconds, _on_timeout)
        timer.daemon = True
        timer.start()

        try:
            yield
        finally:
            timer.cancel()
    else:
        # Unix: use signal.alarm
        import signal

        def _signal_handler(signum, frame):
            raise TimeoutError(
                f"Execution timed out after {seconds} seconds"
            )

        old_handler = signal.signal(signal.SIGALRM, _signal_handler)
        signal.alarm(seconds)

        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
