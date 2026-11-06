# otel-genai

[![PyPI version](https://img.shields.io/pypi/v/trysac-otel-genai)](https://pypi.org/project/trysac-otel-genai/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-otel-genai)](LICENSE)
[![CI](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml)

OpenTelemetry spans and metrics following the GenAI semantic conventions for LLM calls and tool executions, depending only on opentelemetry-api

## Problem

Teams instrument LLM calls with ad-hoc span names and attributes, so traces from different services
cannot be compared and token usage is not aggregated. Prompt content also leaks into traces by
accident. This library wraps LLM and tool calls in convention-correct spans and metrics, with content
capture off by default.

Conventions: OpenTelemetry semantic conventions for GenAI v1.37.0 (status Development).

## Install

```sh
pip install trysac-otel-genai
# or
uv add trysac-otel-genai
```

Requires Python 3.10 or newer. The only runtime dependency is `opentelemetry-api>=1.27,<2`; the SDK is never imported.

## Usage

```python
from otel_genai import GenAITelemetry

t = GenAITelemetry(provider_name="openai")
with t.llm_span("chat", "gpt-x", max_tokens=100) as llm:
    with t.tool_span("search", call_id="c1"):
        pass
    llm.record_response(input_tokens=10, output_tokens=5, finish_reasons=["stop"])
```

Testing with the in-memory recorders:

```python
from otel_genai import GenAITelemetry
from otel_genai.testing import RecordingMeter, RecordingTracer

tracer, meter = RecordingTracer(), RecordingMeter()
t = GenAITelemetry(provider_name="openai", tracer=tracer, meter=meter)
with t.llm_span("chat", "gpt-x") as llm:
    llm.record_response(input_tokens=10, output_tokens=5)
```

## API

- `GenAITelemetry(*, provider_name, tracer=None, meter=None, capture_content=False,
  max_content_chars=2000, max_attribute_chars=256, clock=time.monotonic)` with `llm_span(operation,
  model, *, max_tokens, temperature, server_address)` and `tool_span(tool_name, call_id=None)`.
- `LLMSpan`: `record_response(...)`, `record_prompt(messages)`, `record_completion(text, finish_reason)`.
- `GenAITelemetryError` (a `ValueError`) with `code` of `invalid_usage` or `invalid_operation`.

## Security

Content capture is opt-in (`capture_content=False` by default) because prompts carry personal data;
when enabled, each content string is cut to `max_content_chars`. Exceptions are recorded on spans
via `record_exception`, and exception messages may contain data, so review them before exporting.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
