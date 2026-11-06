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
| Tokens (input / output) | 448685 / 79170 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.7416 |

## Factory run u038 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 3238 | 63215 | 0 | 4246 | 0.3197 |
| fix-1 | claude-sonnet-5-5 | no | 6 | 2069 | 11642 | 46354 | 0.0544 |
| fix-2 | claude-sonnet-5-5 | no | 6 | 550 | 8444 | 43624 | 0.0310 |
| fix-3 | claude-sonnet-5-5 | no | 10 | 2133 | 19284 | 94991 | 0.0791 |
| audit | claude-sonnet-5-5 | no | 10 | 3407 | 38075 | 96997 | 0.1390 |
| fix-4 | claude-sonnet-5-5 | no | 6 | 1786 | 9137 | 42452 | 0.0450 |
| docs | claude-haiku-5-5 | no | 116745 | 6010 | 0 | 0 | 0.0734 |

Total: $0.7416. Prices: Anthropic list prices.
