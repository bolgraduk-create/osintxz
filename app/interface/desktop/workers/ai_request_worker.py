"""
AI request worker.

Executes one AI operation outside the Qt interface thread.

Responsible for:

- running a supplied AI callable
- returning the result through Qt signals
- converting execution failures into error signals
- supporting cooperative cancellation of result delivery

Does NOT:

- access widgets
- create or manage QThread instances
- access repositories directly
- commit or roll back database transactions
- build investigation context
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import (
    QObject,
    Signal,
    Slot,
)


class AIRequestWorker(
    QObject,
):
    """
    Executes one callable representing an AI request.

    The worker must be moved to a QThread before run() is called.
    """

    succeeded = Signal(
        object
    )

    failed = Signal(
        str
    )

    finished = Signal()

    def __init__(
        self,
        operation: Callable[..., Any],
        *,
        operation_kwargs: dict[str, Any] | None = None,
    ) -> None:

        super().__init__()

        if not callable(
            operation
        ):

            raise TypeError(
                "operation must be callable."
            )

        if (
            operation_kwargs is not None
            and not isinstance(
                operation_kwargs,
                dict,
            )
        ):

            raise TypeError(
                "operation_kwargs must be a dictionary or None."
            )

        self.operation = operation

        self.operation_kwargs = dict(
            operation_kwargs
            or {}
        )

        self._cancel_requested = False

        self._running = False

    # ==========================================================
    # Execution
    # ==========================================================

    @Slot()
    def run(
        self,
    ) -> None:
        """
        Execute the configured AI operation.

        This method is intended to run inside a QThread.
        """

        if self._running:

            return

        self._running = True

        try:

            if self._cancel_requested:

                return

            result = self.operation(
                **self.operation_kwargs
            )

            if self._cancel_requested:

                return

            self.succeeded.emit(
                result
            )

        except Exception as exc:

            if not self._cancel_requested:

                self.failed.emit(
                    self._format_error(
                        exc
                    )
                )

        finally:

            self._running = False

            self.finished.emit()

    # ==========================================================
    # Cancellation
    # ==========================================================

    @Slot()
    def request_cancel(
        self,
    ) -> None:
        """
        Request cooperative cancellation.

        A blocking provider request cannot be forcibly interrupted
        here. Cancellation prevents its eventual result or error from
        being delivered to the interface.
        """

        self._cancel_requested = True

    # ==========================================================
    # State
    # ==========================================================

    @property
    def is_running(
        self,
    ) -> bool:
        """
        Return whether the operation is currently executing.
        """

        return self._running

    @property
    def cancel_requested(
        self,
    ) -> bool:
        """
        Return whether cancellation has been requested.
        """

        return self._cancel_requested

    # ==========================================================
    # Error formatting
    # ==========================================================

    @staticmethod
    def _format_error(
        error: Exception,
    ) -> str:
        """
        Convert an exception into a readable UI error.

        The traceback is retained only when the exception text is
        empty, so ordinary provider errors remain concise.
        """

        error_text = str(
            error
        ).strip()

        if error_text:

            return error_text

        traceback_text = traceback.format_exc().strip()

        if traceback_text:

            return traceback_text

        return error.__class__.__name__