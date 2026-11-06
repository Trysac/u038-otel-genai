# otel-genai

[![PyPI version](https://img.shields.io/pypi/v/trysac-otel-genai)](https://pypi.org/project/trysac-otel-genai/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-otel-genai)](LICENSE)
[![CI](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u038-otel-genai/actions/workflows/ci.yml)

OpenTelemetry spans and metrics following the GenAI semantic conventions for LLM calls and tool executions, depending only on opentelemetry-api

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-otel-genai
# or
uv add trysac-otel-genai
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import otel_genai

# normalize() trims surrounding whitespace and lower-cases the text.
print(otel_genai.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    otel_genai.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
