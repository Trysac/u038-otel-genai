# Explicit API-only GenAI instrumentation instead of SDK patching

Status: accepted (generated, pending human review)

## Context

Teams instrument LLM calls with ad-hoc span names and attributes, so traces cannot be compared and token usage is not aggregated. Existing auto-instrumentation libraries patch provider SDKs and pull in many dependencies. The OpenTelemetry GenAI conventions (v1.37.0, status Development) are still evolving and prompt content can leak into traces by accident.

## Decision

Provide an explicit context-manager API (GenAITelemetry.llm_span and tool_span) that depends only on opentelemetry-api. Convention names live in one module (attributes.py) citing the version and date. Content capture is opt-in and truncated, errors are recorded once by the library (the tracer is asked not to record them), metric failures are logged and swallowed, and in-memory recorders for tests are bounded.

## Consequences

Callers wrap each call themselves and nothing is patched or auto-detected, which keeps the dependency footprint to one package and makes behaviour predictable. Convention changes only require editing attributes.py and the docs. Users must review what exception messages contain because they are attached to spans.
