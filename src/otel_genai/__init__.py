"""OpenTelemetry spans and metrics following the GenAI semantic conventions."""

from __future__ import annotations

from otel_genai.core import GenAITelemetry, LLMSpan
from otel_genai.errors import GenAITelemetryError

__all__ = ["GenAITelemetry", "GenAITelemetryError", "LLMSpan", "__version__"]

__version__ = "0.1.0"
