# Project record

## Objective

Provide convention-correct OpenTelemetry spans and metrics for LLM calls and tool executions, following the OpenTelemetry GenAI semantic conventions v1.37.0 (status Development), using only `opentelemetry-api`. Content capture is off by default.

## Scope

- In scope: `GenAITelemetry` with `llm_span` and `tool_span`; `LLMSpan` with `record_response`, `record_prompt` and `record_completion`; `GenAITelemetryError` with codes `invalid_usage` and `invalid_operation`; the in-memory recorders in `otel_genai.testing` (`RecordingTracer`, `RecordingSpan`, `RecordingMeter`), which keep at most 10,000 entries.
- Out of scope: SDK auto-instrumentation, exporters, the events API, agent spans, and a decorator. Anything that needs runtime dependencies or I/O requires an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | pending measurement |
| Hours (human) | pending measurement |
| Cost (USD) | pending measurement |
