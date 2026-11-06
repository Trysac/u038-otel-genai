"""GenAI semantic-convention spans and metrics for LLM calls and tool executions."""

from __future__ import annotations

import json
import logging
import math
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from itertools import islice
from typing import Any, Protocol

from opentelemetry import metrics, trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue

from otel_genai import attributes as attrs
from otel_genai.errors import GenAITelemetryError

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

MAX_MESSAGES = 1000
MAX_FINISH_REASONS = 64


class HistogramLike(Protocol):
    """The part of an OpenTelemetry histogram used by this library."""

    def record(self, amount: float, attributes: Mapping[str, str] | None = None) -> None:
        """Record one measurement."""


class MeterLike(Protocol):
    """The part of an OpenTelemetry meter used by this library."""

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> HistogramLike:
        """Create a histogram instrument."""


def _usage_error(message: str) -> GenAITelemetryError:
    return GenAITelemetryError("invalid_usage", message)


def _cut(value: str, limit: int) -> str:
    return value[:limit]


def _require_str(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise _usage_error(f"{name} must be a string")
    return value


def _optional_str(name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_str(name, value)


def _require_count(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise _usage_error(f"{name} must be a non-negative integer")
    return value


def _optional_count(name: str, value: object) -> int | None:
    if value is None:
        return None
    return _require_count(name, value)


def _message_pair(item: object) -> tuple[str, str]:
    if not isinstance(item, tuple | list) or len(item) != 2:
        raise _usage_error("each message must be a (role, content) pair")
    return _require_str("role", item[0]), _require_str("content", item[1])


def _dump(payload: object) -> str:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _error_type(exc: BaseException) -> str:
    """Return ``error.type``: the bare qualname for builtins, else ``module.qualname``."""
    cls = type(exc)
    if cls.__module__ == "builtins":
        return cls.__qualname__
    return f"{cls.__module__}.{cls.__qualname__}"


class LLMSpan:
    """Handle yielded by :meth:`GenAITelemetry.llm_span` to record response data."""

    def __init__(
        self,
        span: Span,
        *,
        capture_content: bool,
        max_content_chars: int,
        max_attribute_chars: int,
    ) -> None:
        self._span = span
        self._capture = capture_content
        self._max_content_chars = max_content_chars
        self._max_attribute_chars = max_attribute_chars
        self._response_model: str | None = None
        self._input_tokens: int | None = None
        self._output_tokens: int | None = None

    @property
    def span(self) -> Span:
        """The underlying OpenTelemetry span."""
        return self._span

    @property
    def response_model(self) -> str | None:
        """Response model recorded so far, if any."""
        return self._response_model

    @property
    def input_tokens(self) -> int | None:
        """Input token count recorded so far, if any."""
        return self._input_tokens

    @property
    def output_tokens(self) -> int | None:
        """Output token count recorded so far, if any."""
        return self._output_tokens

    def _cut_attr(self, value: str) -> str:
        return _cut(value, self._max_attribute_chars)

    def _text_part(self, content: str) -> dict[str, str]:
        return {"type": "text", "content": _cut(content, self._max_content_chars)}

    def record_response(
        self,
        *,
        response_model: str | None = None,
        response_id: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        finish_reasons: Sequence[str] = (),
    ) -> None:
        """Record response attributes and token usage.

        Everything is validated before anything is set.

        Raises:
            GenAITelemetryError: code ``invalid_usage`` for bad types, negative token
                counts or more than 64 finish reasons.
        """
        model = _optional_str("response_model", response_model)
        rid = _optional_str("response_id", response_id)
        n_in = _optional_count("input_tokens", input_tokens)
        n_out = _optional_count("output_tokens", output_tokens)
        if isinstance(finish_reasons, str | bytes):
            raise _usage_error("finish_reasons must be a sequence of strings")
        items = tuple(islice(finish_reasons, MAX_FINISH_REASONS + 1))
        if len(items) > MAX_FINISH_REASONS:
            raise _usage_error("too many finish_reasons")
        checked = tuple(self._cut_attr(_require_str("finish_reason", i)) for i in items)
        if model is not None:
            self._response_model = self._cut_attr(model)
            self._span.set_attribute(attrs.GEN_AI_RESPONSE_MODEL, self._response_model)
        if rid is not None:
            self._span.set_attribute(attrs.GEN_AI_RESPONSE_ID, self._cut_attr(rid))
        if n_in is not None:
            self._input_tokens = n_in
            self._span.set_attribute(attrs.GEN_AI_USAGE_INPUT_TOKENS, n_in)
        if n_out is not None:
            self._output_tokens = n_out
            self._span.set_attribute(attrs.GEN_AI_USAGE_OUTPUT_TOKENS, n_out)
        if checked:
            self._span.set_attribute(attrs.GEN_AI_RESPONSE_FINISH_REASONS, checked)

    def record_prompt(self, messages: Sequence[tuple[str, str]]) -> None:
        """Record the prompt as ``gen_ai.input.messages`` (only with content capture).

        Raises:
            GenAITelemetryError: code ``invalid_usage`` for malformed or too many messages.
        """
        if not self._capture:
            return
        items = tuple(islice(messages, MAX_MESSAGES + 1))
        if len(items) > MAX_MESSAGES:
            raise _usage_error("too many messages")
        payload: list[dict[str, Any]] = []
        for item in items:
            role, content = _message_pair(item)
            message = {"role": self._cut_attr(role), "parts": [self._text_part(content)]}
            payload.append(message)
        self._span.set_attribute(attrs.GEN_AI_INPUT_MESSAGES, _dump(payload))

    def record_completion(self, text: str, finish_reason: str | None = None) -> None:
        """Record the completion as ``gen_ai.output.messages`` (only with content capture).

        Raises:
            GenAITelemetryError: code ``invalid_usage`` for non-string arguments.
        """
        if not self._capture:
            return
        content = _require_str("text", text)
        reason = _optional_str("finish_reason", finish_reason)
        message: dict[str, Any] = {"role": "assistant", "parts": [self._text_part(content)]}
        if reason is not None:
            message["finish_reason"] = self._cut_attr(reason)
        self._span.set_attribute(attrs.GEN_AI_OUTPUT_MESSAGES, _dump([message]))


class GenAITelemetry:
    """Creates convention-correct spans and metrics for LLM calls and tool executions.

    Content capture is opt-in because prompts and completions may carry personal data.
    Exception messages are attached to spans through ``record_exception`` and may also
    contain data.
    """

    def __init__(
        self,
        *,
        provider_name: str,
        tracer: Tracer | None = None,
        meter: MeterLike | None = None,
        capture_content: bool = False,
        max_content_chars: int = 2000,
        max_attribute_chars: int = 256,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_content_chars = _require_count("max_content_chars", max_content_chars)
        self._max_attribute_chars = _require_count("max_attribute_chars", max_attribute_chars)
        if self._max_attribute_chars < 1:
            raise _usage_error("max_attribute_chars must be at least 1")
        provider = _require_str("provider_name", provider_name)
        if not provider.strip():
            raise _usage_error("provider_name must not be empty")
        self._provider = self._cut_attr(provider)
        self._capture = bool(capture_content)
        self._clock = clock
        self._tracer = tracer if tracer is not None else trace.get_tracer("otel_genai")
        chosen: MeterLike = meter if meter is not None else metrics.get_meter("otel_genai")
        self._token_usage = chosen.create_histogram(
            attrs.METRIC_TOKEN_USAGE,
            unit=attrs.UNIT_TOKEN,
            description="Number of input and output tokens used.",
        )
        self._duration = chosen.create_histogram(
            attrs.METRIC_OPERATION_DURATION,
            unit=attrs.UNIT_SECONDS,
            description="Duration of the GenAI client operation.",
        )

    def _cut_attr(self, value: str) -> str:
        return _cut(value, self._max_attribute_chars)

    def llm_span(
        self,
        operation: str,
        model: str,
        *,
        max_tokens: int | None = None,
        temperature: float | None = None,
        server_address: str | None = None,
    ) -> AbstractContextManager[LLMSpan]:
        """Open a CLIENT span named ``"{operation} {model}"`` for one LLM call.

        Validation happens when this method is called. Exceptions escaping the block are
        recorded once, set the status to ERROR and ``error.type``, and are re-raised.

        Raises:
            GenAITelemetryError: code ``invalid_operation`` for an unknown operation,
                ``invalid_usage`` for bad argument types.
        """
        if not isinstance(operation, str) or operation not in attrs.LLM_OPERATIONS:
            allowed = ", ".join(sorted(attrs.LLM_OPERATIONS))
            raise GenAITelemetryError("invalid_operation", f"operation must be one of: {allowed}")
        cut_model = self._cut_attr(_require_str("model", model))
        span_attrs: dict[str, AttributeValue] = {
            attrs.GEN_AI_OPERATION_NAME: operation,
            attrs.GEN_AI_PROVIDER_NAME: self._provider,
        }
        if cut_model:
            span_attrs[attrs.GEN_AI_REQUEST_MODEL] = cut_model
        if max_tokens is not None:
            span_attrs[attrs.GEN_AI_REQUEST_MAX_TOKENS] = _require_count("max_tokens", max_tokens)
        if temperature is not None:
            is_number = isinstance(temperature, int | float) and not isinstance(temperature, bool)
            if not is_number or not math.isfinite(temperature):
                raise _usage_error("temperature must be a finite number")
            span_attrs[attrs.GEN_AI_REQUEST_TEMPERATURE] = float(temperature)
        if server_address is not None:
            address = _require_str("server_address", server_address)
            span_attrs[attrs.SERVER_ADDRESS] = self._cut_attr(address)
        name = f"{operation} {cut_model}" if cut_model else operation
        return self._llm_context(operation, cut_model, name, span_attrs)

    def tool_span(
        self,
        tool_name: str,
        call_id: str | None = None,
    ) -> AbstractContextManager[Span]:
        """Open an INTERNAL span named ``"execute_tool {tool_name}"`` for a tool execution.

        Raises:
            GenAITelemetryError: code ``invalid_usage`` for an empty or non-string name or
                a non-string ``call_id``.
        """
        name = self._cut_attr(_require_str("tool_name", tool_name))
        if not name.strip():
            raise _usage_error("tool_name must not be empty")
        span_attrs: dict[str, AttributeValue] = {
            attrs.GEN_AI_OPERATION_NAME: attrs.OPERATION_EXECUTE_TOOL,
            attrs.GEN_AI_TOOL_NAME: name,
        }
        cid = _optional_str("call_id", call_id)
        if cid is not None:
            span_attrs[attrs.GEN_AI_TOOL_CALL_ID] = self._cut_attr(cid)
        return self._tool_context(f"{attrs.OPERATION_EXECUTE_TOOL} {name}", span_attrs)

    def _mark_error(self, span: Span, exc: BaseException) -> str:
        error_type = self._cut_attr(_error_type(exc))
        span.set_attribute(attrs.ERROR_TYPE, error_type)
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, error_type))
        return error_type

    @contextmanager
    def _tool_context(
        self,
        name: str,
        span_attrs: Mapping[str, AttributeValue],
    ) -> Iterator[Span]:
        cm = self._tracer.start_as_current_span(
            name,
            kind=SpanKind.INTERNAL,
            attributes=span_attrs,
            record_exception=False,
            set_status_on_exception=False,
        )
        with cm as span:
            try:
                yield span
            except Exception as exc:
                self._mark_error(span, exc)
                raise

    @contextmanager
    def _llm_context(
        self,
        operation: str,
        model: str,
        name: str,
        span_attrs: Mapping[str, AttributeValue],
    ) -> Iterator[LLMSpan]:
        start = self._clock()
        error_type: str | None = None
        cm = self._tracer.start_as_current_span(
            name,
            kind=SpanKind.CLIENT,
            attributes=span_attrs,
            record_exception=False,
            set_status_on_exception=False,
        )
        with cm as span:
            llm = LLMSpan(
                span,
                capture_content=self._capture,
                max_content_chars=self._max_content_chars,
                max_attribute_chars=self._max_attribute_chars,
            )
            try:
                yield llm
            except Exception as exc:
                error_type = self._mark_error(span, exc)
                raise
            finally:
                self._emit_metrics(operation, model, llm, start, error_type)

    def _emit_metrics(
        self,
        operation: str,
        model: str,
        llm: LLMSpan,
        start: float,
        error_type: str | None,
    ) -> None:
        try:
            duration = max(0.0, self._clock() - start)
            common: dict[str, str] = {
                attrs.GEN_AI_OPERATION_NAME: operation,
                attrs.GEN_AI_PROVIDER_NAME: self._provider,
            }
            if model:
                common[attrs.GEN_AI_REQUEST_MODEL] = model
            if llm.response_model is not None:
                common[attrs.GEN_AI_RESPONSE_MODEL] = llm.response_model
            usage = (
                (attrs.TOKEN_TYPE_INPUT, llm.input_tokens),
                (attrs.TOKEN_TYPE_OUTPUT, llm.output_tokens),
            )
            for token_type, count in usage:
                if count is not None:
                    labels = {**common, attrs.GEN_AI_TOKEN_TYPE: token_type}
                    self._token_usage.record(count, labels)
            if error_type is not None:
                common[attrs.ERROR_TYPE] = error_type
            self._duration.record(duration, common)
        except Exception:
            logger.warning("failed to record GenAI metrics")
