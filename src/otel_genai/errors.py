"""Typed errors raised by otel_genai."""

from __future__ import annotations

from typing import Literal

ErrorCode = Literal["invalid_usage", "invalid_operation"]

_MAX_MESSAGE_CHARS = 200


class GenAITelemetryError(ValueError):
    """Base error of the library.

    Attributes:
        code: Stable machine-readable error code.
    """

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message[:_MAX_MESSAGE_CHARS])
        self.code: ErrorCode = code
