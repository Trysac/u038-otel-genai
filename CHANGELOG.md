# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add `otel_genai` with `GenAITelemetry.llm_span`/`tool_span` producing OpenTelemetry GenAI semantic-convention (v1.37.0) spans and metrics on top of `opentelemetry-api`, opt-in content capture, typed `GenAITelemetryError`, and bounded `otel_genai.testing` recorders.
- Initial project structure from the factory utility template.
