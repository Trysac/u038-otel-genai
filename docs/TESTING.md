# Testing

## Running

```sh
uv run pytest --cov=otel_genai   # tests with coverage report
uv run python scripts/check.py      # every gate, as the factory runs it
```

## Policy

- Branch coverage of `src/otel_genai` must stay at or above 80 %; the gate fails below it.
- Tests exercise the public API (`import otel_genai`) and assert observable effects: return values, raised exceptions and their messages, span names, kinds, attributes, status and recorded metrics.
- Each bug fix starts with a failing test that reproduces it.
- Tests are deterministic: no network, no wall clock (the `clock` parameter is injected), no dependence on test order.

## Coverage of the specification

The behaviours that the tests must check are the acceptance criteria of the specification:

- span name, kind and request attributes for `llm_span`, and the TypeError for a missing `provider_name`;
- response attributes and the `invalid_usage` error for negative token counts;
- ERROR status, single exception recording, `error.type` (builtin and module-qualified) and re-raise;
- `tool_span` as an INTERNAL child of the LLM span;
- content capture off and on, including truncation to `max_content_chars`;
- token usage and duration measurements with a fixed clock;
- `RecordingSpan` and `RecordingTracer` as subclasses of the OpenTelemetry base classes, the no-op default behaviour, and the `invalid_operation` error.

## Layout

The convention is `tests/test_<module>.py` for each public module, with shared fixtures in `tests/conftest.py`. The test files were not part of the source snapshot used to write this document, so their exact names are not listed here.
