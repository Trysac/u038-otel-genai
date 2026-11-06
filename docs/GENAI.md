# GenAI telemetry

`otel_genai` wraps LLM calls and tool executions in spans and metrics that follow the
OpenTelemetry semantic conventions for GenAI v1.37.0 (status Development; checked 2026-11-05).
It depends only on `opentelemetry-api`; without an SDK installed every call is a no-op.

## Usage

```python
from otel_genai import GenAITelemetry

telemetry = GenAITelemetry(provider_name="openai")
with telemetry.llm_span("chat", "gpt-x", max_tokens=100) as llm:
    llm.record_response(input_tokens=10, output_tokens=5, finish_reasons=["stop"])
    with telemetry.tool_span("search", call_id="c1"):
        pass
```

Operations accepted by `llm_span`: `chat`, `text_completion`, `embeddings`, `generate_content`.
Anything else raises `GenAITelemetryError` with code `invalid_operation`. Invalid arguments raise
the same error with code `invalid_usage`.

## Privacy

- Prompt and completion capture is **off by default** because they usually carry personal data.
  Enable it with `capture_content=True`; each content string is cut to `max_content_chars`.
- Exceptions raised inside a span are recorded with `record_exception`. Exception messages may
  contain data, so review what your code puts in them.
- Strings used as attributes are cut to `max_attribute_chars`.

## Metrics

`gen_ai.client.token.usage` (unit `{token}`) receives the input and output token counts when known.
`gen_ai.client.operation.duration` (unit `s`) receives the duration measured with the injected
clock. Metric attributes are the operation, provider, request model and, when known, response
model; the duration metric adds `error.type` on failure and the token metric adds
`gen_ai.token.type`.

## Testing

`otel_genai.testing` provides `RecordingTracer`, `RecordingSpan` and `RecordingMeter`, which keep at
most 10_000 spans or measurements and drop the oldest.

Out of scope: SDK auto-instrumentation, exporters, the events API, agent spans and decorators.
