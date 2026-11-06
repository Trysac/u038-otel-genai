# Architecture

## Purpose

`trysac-otel-genai` (import name `otel_genai`) is a small Python library that produces OpenTelemetry spans and metrics following the GenAI semantic conventions v1.37.0 for LLM calls and tool executions. It depends only on `opentelemetry-api`.

## Shape

```text
caller code --> otel_genai (public API in __init__.py)
                    |
                    +-- core.py: GenAITelemetry, LLMSpan (spans and metrics)
                    +-- attributes.py: convention names and constants
                    +-- errors.py: GenAITelemetryError
                    +-- testing.py: in-memory recorders (not exported from __init__)
```

- **Public API**: `GenAITelemetry`, `LLMSpan`, `GenAITelemetryError` and `__version__`, as listed in `__all__` of `src/otel_genai/__init__.py`. `otel_genai.testing` is a separate public module.
- **Spans**: started with `start_as_current_span`, with `record_exception=False` and `set_status_on_exception=False`; the library records the exception once and sets the status itself.
- **Metrics**: two histograms are created when `GenAITelemetry` is constructed. Metric recording failures are logged and do not propagate.
- **Errors**: invalid input raises `GenAITelemetryError`, a `ValueError` subclass with a stable `code`.
- **Side effects**: logging through `getLogger(__name__)` with a NullHandler. No other I/O.

## Decisions

Architecture decisions are meant to be recorded as numbered ADRs; no ADR files were part of the source snapshot used for this document.
