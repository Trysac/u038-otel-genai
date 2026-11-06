# Security notes

## Threat model

`trysac-otel-genai` is a library without network or file I/O. It writes only to the OpenTelemetry tracer and meter objects it is given.

Defended:

- **Prompt and completion content leaking into traces**: content capture is off by default. When off, `record_prompt` and `record_completion` set no attribute and the text is not included in any span.
- **Oversized attribute and content values**: strings in attributes are cut to `max_attribute_chars` (default 256); content strings are cut to `max_content_chars` (default 2000) before JSON encoding; error messages are cut to 200 characters.
- **Unbounded input lists**: `record_prompt` rejects more than 1000 messages; `record_response` rejects more than 64 finish reasons.
- **Invalid input**: wrong types, negative token counts, non-finite temperatures and empty names raise `GenAITelemetryError` before any attribute is set.
- **Telemetry failures breaking the caller**: metric recording errors are caught and logged as a warning without the exception content.
- **Supply chain**: the only runtime dependency is `opentelemetry-api>=1.27,<2`; the SDK is never imported.

Not defended:

- **Exception messages**: `record_exception` stores the exception, including its message, on the span. Messages may contain personal data or secrets; the library does not redact them.
- **Content when capture is enabled**: prompts and completions are recorded as given (truncated only). The library does not detect or mask personal data.
- **Attribute values otherwise**: model names, response IDs, server addresses and tool names are recorded unchanged apart from truncation.
- **Exporter and storage security**: transport, access control and retention of spans are the responsibility of the application's OpenTelemetry setup.
- **Recorder memory**: the in-memory recorders in `otel_genai.testing` are for tests; they are bounded but hold recorded data in process memory.

## Reporting

To report a vulnerability, see [SECURITY.md](../SECURITY.md).
