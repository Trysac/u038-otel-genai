# otel-genai

[![PyPI version](https://img.shields.io/pypi/v/trysac-otel-genai)](https://pypi.org/project/trysac-otel-genai/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-otel-genai)](LICENSE)
[![CI](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml)

OpenTelemetry spans and metrics following the GenAI semantic conventions (v1.37.0) for LLM calls and tool executions. The only runtime dependency is `opentelemetry-api`.

## Problem

Teams instrument LLM calls with ad-hoc span names and attributes, so traces from different services cannot be compared and token usage is not aggregated. Applying the GenAI conventions by hand is verbose, and prompt content leaks into traces by accident. `otel_genai` wraps LLM and tool calls in convention-correct spans and metrics, with content capture off by default.

## Install

```sh
pip install trysac-otel-genai
# or
uv add trysac-otel-genai
```

Requires Python 3.10 or newer. The import name is `otel_genai`. The SDK (`opentelemetry-sdk`) is never imported; without an SDK the default no-op tracer and meter are used.

## Usage

```python
from otel_genai import GenAITelemetry

telemetry = GenAITelemetry(provider_name="openai")
with telemetry.llm_span("chat", "gpt-x", max_tokens=100) as llm:
    llm.record_response(input_tokens=10, output_tokens=5, finish_reasons=["stop"])
    with telemetry.tool_span("search", call_id="c1"):
        pass
```

Testing with the in-memory recorders from `otel_genai.testing`:

```python
from otel_genai import GenAITelemetry
from otel_genai.testing import RecordingMeter, RecordingTracer

tracer, meter = RecordingTracer(), RecordingMeter()
telemetry = GenAITelemetry(provider_name="openai", tracer=tracer, meter=meter)
with telemetry.llm_span("chat", "gpt-x") as llm:
    llm.record_response(input_tokens=10, output_tokens=5)
```

## API

- `GenAITelemetry(*, provider_name: str, tracer=None, meter=None, capture_content=False, max_content_chars=2000, max_attribute_chars=256, clock=time.monotonic)`
  - `llm_span(operation, model, *, max_tokens=None, temperature=None, server_address=None)` returns a context manager yielding `LLMSpan`. Span name is `"{operation} {model}"` (the operation alone when model is empty), kind CLIENT. `operation` must be one of `chat`, `text_completion`, `embeddings`, `generate_content`.
  - `tool_span(tool_name, call_id=None)` returns a context manager yielding the OpenTelemetry span. Span name is `"execute_tool {tool_name}"`, kind INTERNAL.
- `LLMSpan`
  - `record_response(*, response_model=None, response_id=None, input_tokens=None, output_tokens=None, finish_reasons=())` sets the response and usage attributes. Everything is validated before anything is set.
  - `record_prompt(messages)` takes a sequence of `(role, content)` tuples and records `gen_ai.input.messages` only when `capture_content=True`.
  - `record_completion(text, finish_reason=None)` records `gen_ai.output.messages` only when `capture_content=True`.
- Metrics: histogram `gen_ai.client.token.usage` (unit `{token}`, attribute `gen_ai.token.type` with values `input` and `output`) and histogram `gen_ai.client.operation.duration` (unit `s`).
- `GenAITelemetryError(ValueError)` with attribute `code`: `invalid_usage` for bad argument types, negative token counts, empty names or too many messages or finish reasons; `invalid_operation` for an unknown operation.
- `otel_genai.testing`: `RecordingTracer`, `RecordingSpan`, `RecordingMeter`.

Limits: strings in attributes are cut to `max_attribute_chars`; content strings are cut to `max_content_chars`; `record_prompt` accepts at most 1000 messages; `record_response` accepts at most 64 finish reasons; error messages are cut to 200 characters; recorders keep at most 10,000 entries and drop the oldest.

## Why not OpenLLMetry

OpenLLMetry patches LLM SDKs and brings many dependencies. `otel_genai` is explicit, requires only `opentelemetry-api`, and does not patch anything: the caller opens each span and records each value.

## Security

Content capture is opt-in (`capture_content=False` by default) because prompts and completions may carry personal data. Exception messages are attached to spans through `record_exception` and may contain data. See [docs/SECURITY.md](docs/SECURITY.md) for the threat model and limits.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
