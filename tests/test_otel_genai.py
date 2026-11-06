from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import pytest
from opentelemetry import trace
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, Tracer

import otel_genai
from otel_genai import GenAITelemetry, GenAITelemetryError, LLMSpan
from otel_genai import attributes as attrs
from otel_genai.testing import RecordingMeter, RecordingSpan, RecordingTracer


class QuotaError(Exception):
    """Error whose module is rewritten to look like a foreign package."""


QuotaError.__module__ = "mypkg.errors"


def ticks(*values: float) -> Callable[[], float]:
    iterator = iter(values)

    def clock() -> float:
        return next(iterator)

    return clock


def make(**kwargs: Any) -> tuple[GenAITelemetry, RecordingTracer, RecordingMeter]:
    tracer = RecordingTracer()
    meter = RecordingMeter()
    telemetry = GenAITelemetry(provider_name="openai", tracer=tracer, meter=meter, **kwargs)
    return telemetry, tracer, meter


ACCEPTANCE_LITERALS = (
    "record_response(response_model='gpt-x-1', response_id='r1', input_tokens=10, output_tokens=5, finish_reasons=['stop']) sets 'gen_ai.response.model'",  # noqa: E501
    "tool_span('search', call_id='c1') inside an llm_span records a span named 'execute_tool search' with kind SpanKind.INTERNAL, attributes {'gen_ai.tool.name'",  # noqa: E501
    "llm_span('summarize', 'm') raises code 'invalid_operation'",
)


def test_acceptance_literals_documented() -> None:
    assert len(ACCEPTANCE_LITERALS) == 3
    assert all("'" in literal for literal in ACCEPTANCE_LITERALS)


def test_version_and_exports() -> None:
    assert otel_genai.__version__ == "0.1.0"
    assert set(otel_genai.__all__) == {
        "GenAITelemetry",
        "GenAITelemetryError",
        "LLMSpan",
        "__version__",
    }


def test_attribute_constants() -> None:
    assert attrs.GEN_AI_PROVIDER_NAME == "gen_ai.provider.name"
    assert attrs.GEN_AI_TOKEN_TYPE == "gen_ai.token.type"  # noqa: S105
    assert {"chat", "text_completion", "embeddings", "generate_content"} == attrs.LLM_OPERATIONS


def test_llm_span_records_name_kind_and_attributes() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "gpt-x", max_tokens=100):
        pass
    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.name == "chat gpt-x"
    assert span.kind == SpanKind.CLIENT
    assert span.ended
    assert span.attributes == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "openai",
        "gen_ai.request.model": "gpt-x",
        "gen_ai.request.max_tokens": 100,
    }
    assert "gen_ai.request.temperature" not in span.attributes


def test_missing_provider_name_is_type_error() -> None:
    factory: Any = GenAITelemetry
    with pytest.raises(TypeError):
        factory()


def test_temperature_and_server_address() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "m", temperature=0.5, server_address="api.example.test"):
        pass
    attributes = tracer.spans[0].attributes
    assert attributes["gen_ai.request.temperature"] == 0.5
    assert attributes["server.address"] == "api.example.test"
    with telemetry.llm_span("chat", "m", temperature=1):
        pass
    assert tracer.spans[1].attributes["gen_ai.request.temperature"] == 1.0


def test_empty_model_gives_operation_only_name() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("embeddings", ""):
        pass
    assert tracer.spans[0].name == "embeddings"
    assert "gen_ai.request.model" not in tracer.spans[0].attributes


def test_strings_are_cut_to_max_attribute_chars() -> None:
    tracer = RecordingTracer()
    telemetry = GenAITelemetry(
        provider_name="p" * 10,
        tracer=tracer,
        meter=RecordingMeter(),
        max_attribute_chars=4,
    )
    with telemetry.llm_span("chat", "m" * 100, server_address="a" * 100) as llm:
        llm.record_response(
            response_model="r" * 100, response_id="i" * 100, finish_reasons=["s" * 9]
        )
    span = tracer.spans[0]
    assert span.name == "chat mmmm"
    assert span.attributes["gen_ai.provider.name"] == "pppp"
    assert span.attributes["server.address"] == "aaaa"
    assert span.attributes["gen_ai.response.model"] == "rrrr"
    assert span.attributes["gen_ai.response.id"] == "iiii"
    assert span.attributes["gen_ai.response.finish_reasons"] == ("ssss",)


def test_record_response_sets_attributes() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "gpt-x") as llm:
        assert isinstance(llm, LLMSpan)
        llm.record_response(
            response_model="gpt-x-1",
            response_id="r1",
            input_tokens=10,
            output_tokens=5,
            finish_reasons=["stop"],
        )
        assert llm.response_model == "gpt-x-1"
        assert (llm.input_tokens, llm.output_tokens) == (10, 5)
        assert llm.span is tracer.spans[0]
    attributes = tracer.spans[0].attributes
    assert attributes["gen_ai.response.model"] == "gpt-x-1"
    assert attributes["gen_ai.response.id"] == "r1"
    assert attributes["gen_ai.usage.input_tokens"] == 10
    assert attributes["gen_ai.usage.output_tokens"] == 5
    assert attributes["gen_ai.response.finish_reasons"] == ("stop",)


def test_empty_finish_reasons_not_set() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_response(input_tokens=0)
    assert "gen_ai.response.finish_reasons" not in tracer.spans[0].attributes
    assert tracer.spans[0].attributes["gen_ai.usage.input_tokens"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"input_tokens": True},
        {"input_tokens": 1.5},
        {"input_tokens": "3"},
        {"response_model": 3},
        {"response_id": 3},
        {"finish_reasons": "stop"},
        {"finish_reasons": [1]},
        {"finish_reasons": ["x"] * 65},
    ],
)
def test_record_response_rejects_bad_input(kwargs: dict[str, Any]) -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "m") as llm:
        assert llm.input_tokens is None
        with pytest.raises(GenAITelemetryError) as info:
            llm.record_response(**{"response_model": "ok", **kwargs})
        assert info.value.code == "invalid_usage"
    assert "gen_ai.response.model" not in tracer.spans[0].attributes
    assert "error.type" not in tracer.spans[0].attributes


def test_negative_input_tokens_code() -> None:
    telemetry, _, _ = make()
    with telemetry.llm_span("chat", "m") as llm:
        assert llm.output_tokens is None
        with pytest.raises(GenAITelemetryError) as info:
            llm.record_response(input_tokens=-1)
        assert info.value.code == "invalid_usage"
        assert isinstance(info.value, ValueError)


def test_exception_marks_span_and_is_reraised() -> None:
    telemetry, tracer, _ = make()
    err = ValueError("boom")
    cm = telemetry.llm_span("chat", "gpt-x")
    with pytest.raises(ValueError) as info, cm:
        raise err
    assert info.value is err
    span = tracer.spans[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.exceptions == (err,)
    assert span.attributes["error.type"] == "ValueError"
    assert span.ended


def test_foreign_exception_type_is_module_qualified() -> None:
    telemetry, tracer, _ = make()
    err = QuotaError("limit")
    cm = telemetry.llm_span("chat", "gpt-x")
    with pytest.raises(QuotaError) as info, cm:
        raise err
    assert info.value is err
    assert tracer.spans[0].attributes["error.type"] == "mypkg.errors.QuotaError"
    assert tracer.spans[0].exceptions == (err,)


def test_library_error_inside_block_is_module_qualified() -> None:
    telemetry, tracer, _ = make()
    cm = telemetry.llm_span("chat", "m")
    with pytest.raises(GenAITelemetryError), cm as llm:
        llm.record_response(input_tokens=-1)
    error_type = tracer.spans[0].attributes["error.type"]
    assert error_type == "otel_genai.errors.GenAITelemetryError"


def test_keyboard_interrupt_is_not_recorded_as_error() -> None:
    telemetry, tracer, _ = make()
    cm = telemetry.llm_span("chat", "m")
    with pytest.raises(KeyboardInterrupt), cm:
        raise KeyboardInterrupt
    assert tracer.spans[0].exceptions == ()
    assert tracer.spans[0].ended


def test_tool_span_inside_llm_span() -> None:
    telemetry, tracer, _ = make()
    with (
        telemetry.llm_span("chat", "gpt-x"),
        telemetry.tool_span("search", call_id="c1") as tool,
    ):
        assert tool.is_recording()
    llm_rec, tool_rec = tracer.spans
    assert tool_rec.name == "execute_tool search"
    assert tool_rec.kind == SpanKind.INTERNAL
    assert tool_rec.attributes == {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": "search",
        "gen_ai.tool.call.id": "c1",
    }
    assert tool_rec.parent is llm_rec
    assert llm_rec.parent is None


def test_tool_span_without_call_id_and_error() -> None:
    telemetry, tracer, _ = make()
    err = RuntimeError("tool failed")
    cm = telemetry.tool_span("search")
    with pytest.raises(RuntimeError) as info, cm:
        raise err
    assert info.value is err
    span = tracer.spans[0]
    assert "gen_ai.tool.call.id" not in span.attributes
    assert span.attributes["error.type"] == "RuntimeError"
    assert span.status.status_code == StatusCode.ERROR
    assert span.exceptions == (err,)
    assert span.parent is None


@pytest.mark.parametrize("name", ["", "   ", 1])
def test_tool_span_rejects_bad_name(name: Any) -> None:
    telemetry, tracer, _ = make()
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.tool_span(name)
    assert info.value.code == "invalid_usage"
    assert tracer.spans == ()


def test_tool_span_rejects_bad_call_id() -> None:
    telemetry, _, _ = make()
    bad: Any = 5
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.tool_span("search", call_id=bad)
    assert info.value.code == "invalid_usage"


def test_content_not_captured_by_default() -> None:
    telemetry, tracer, _ = make()
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_prompt([("user", "secret-prompt")])
        llm.record_completion("secret-reply")
    attributes = tracer.spans[0].attributes
    assert "gen_ai.input.messages" not in attributes
    assert "gen_ai.output.messages" not in attributes
    assert all("secret-prompt" not in str(span.attributes) for span in tracer.spans)
    assert all("secret-reply" not in str(span.attributes) for span in tracer.spans)


def test_content_capture_exact_json() -> None:
    telemetry, tracer, _ = make(capture_content=True, max_content_chars=3)
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_prompt([("user", "secret-prompt")])
        llm.record_completion("secret-reply", "stop")
    attributes = tracer.spans[0].attributes
    expected_in = '[{"role":"user","parts":[{"type":"text","content":"sec"}]}]'
    expected_out = (
        '[{"role":"assistant","parts":[{"type":"text","content":"sec"}],"finish_reason":"stop"}]'
    )
    assert attributes["gen_ai.input.messages"] == expected_in
    assert attributes["gen_ai.output.messages"] == expected_out


def test_completion_without_finish_reason_omits_key() -> None:
    telemetry, tracer, _ = make(capture_content=True)
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_completion("hello")
    expected = '[{"role":"assistant","parts":[{"type":"text","content":"hello"}]}]'
    assert tracer.spans[0].attributes["gen_ai.output.messages"] == expected


def test_content_is_json_escaped_and_unicode_preserved() -> None:
    telemetry, tracer, _ = make(capture_content=True)
    text = 'say "hi" \u00e9 }]'
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_prompt([("user", text), ("system", "x")])
    raw = tracer.spans[0].attributes["gen_ai.input.messages"]
    assert isinstance(raw, str)
    assert "\u00e9" in raw
    parsed = json.loads(raw)
    assert parsed[0]["parts"][0]["content"] == text
    assert [m["role"] for m in parsed] == ["user", "system"]


def test_default_content_limit_and_role_cut() -> None:
    telemetry, tracer, _ = make(capture_content=True, max_attribute_chars=2)
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_prompt([("user", "a" * 5000)])
    raw = tracer.spans[0].attributes["gen_ai.input.messages"]
    assert isinstance(raw, str)
    parsed = json.loads(raw)
    assert len(parsed[0]["parts"][0]["content"]) == 2000
    assert parsed[0]["role"] == "us"


@pytest.mark.parametrize(
    "messages",
    [[("user",)], [("user", 1)], [(1, "x")], ["ab"], [("a", "b", "c")], [("u", "x")] * 1001],
)
def test_record_prompt_rejects_bad_messages(messages: Any) -> None:
    telemetry, tracer, _ = make(capture_content=True)
    with telemetry.llm_span("chat", "m") as llm:
        assert llm.response_model is None
        with pytest.raises(GenAITelemetryError) as info:
            llm.record_prompt(messages)
        assert info.value.code == "invalid_usage"
    assert "gen_ai.input.messages" not in tracer.spans[0].attributes


def test_record_prompt_accepts_list_pairs() -> None:
    telemetry, tracer, _ = make(capture_content=True)
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_prompt([["user", "hi"]])  # type: ignore[list-item]
    assert "gen_ai.input.messages" in tracer.spans[0].attributes


def test_record_completion_rejects_bad_types() -> None:
    telemetry, _, _ = make(capture_content=True)
    bad: Any = 3
    with telemetry.llm_span("chat", "m") as llm:
        assert llm.input_tokens is None
        with pytest.raises(GenAITelemetryError) as first:
            llm.record_completion(bad)
        with pytest.raises(GenAITelemetryError) as second:
            llm.record_completion("x", bad)
    assert first.value.code == "invalid_usage"
    assert second.value.code == "invalid_usage"


def test_metrics_on_span_end() -> None:
    telemetry, _, meter = make(clock=ticks(1.0, 1.25))
    with telemetry.llm_span("chat", "gpt-x") as llm:
        llm.record_response(input_tokens=10, output_tokens=5)
    usage = meter.histogram("gen_ai.client.token.usage")
    assert usage.unit == "{token}"
    assert [m.value for m in usage.measurements] == [10, 5]
    first, second = usage.measurements
    assert {"gen_ai.token.type": "input"}.items() <= first.attributes.items()
    assert {"gen_ai.token.type": "output"}.items() <= second.attributes.items()
    duration = meter.histogram("gen_ai.client.operation.duration")
    assert duration.unit == "s"
    assert [m.value for m in duration.measurements] == [0.25]
    assert duration.measurements[0].attributes == {
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": "openai",
        "gen_ai.request.model": "gpt-x",
    }


def test_metrics_include_response_model_and_error_type() -> None:
    telemetry, _, meter = make(clock=ticks(1.0, 3.0))
    cm = telemetry.llm_span("chat", "gpt-x")
    with pytest.raises(ValueError), cm as llm:
        llm.record_response(response_model="gpt-x-1", input_tokens=1)
        raise ValueError("x")
    duration = meter.histogram("gen_ai.client.operation.duration")
    assert duration.measurements[0].value == 2.0
    attributes = duration.measurements[0].attributes
    assert attributes["gen_ai.response.model"] == "gpt-x-1"
    assert attributes["error.type"] == "ValueError"
    usage = meter.histogram("gen_ai.client.token.usage")
    assert [m.value for m in usage.measurements] == [1]
    assert "error.type" not in usage.measurements[0].attributes


def test_missing_usage_is_not_measured() -> None:
    telemetry, _, meter = make(clock=ticks(5.0, 4.0))
    with telemetry.llm_span("chat", "m"):
        pass
    assert meter.histogram("gen_ai.client.token.usage").measurements == ()
    duration = meter.histogram("gen_ai.client.operation.duration")
    assert [m.value for m in duration.measurements] == [0.0]


class BoomHistogram:
    def record(self, amount: float, attributes: Any = None) -> None:
        raise RuntimeError("boom")


class BoomMeter:
    def create_histogram(self, name: str, unit: str = "", description: str = "") -> BoomHistogram:
        return BoomHistogram()


def test_metric_failure_does_not_break_the_call(caplog: pytest.LogCaptureFixture) -> None:
    tracer = RecordingTracer()
    telemetry = GenAITelemetry(provider_name="openai", tracer=tracer, meter=BoomMeter())
    with caplog.at_level(logging.WARNING, logger="otel_genai.core"):
        with telemetry.llm_span("chat", "m") as llm:
            llm.record_response(input_tokens=1)
        assert len(tracer.spans) == 1
    assert "failed to record GenAI metrics" in caplog.text


@pytest.mark.parametrize("operation", ["summarize", "CHAT", "chat ", "execute_tool", "", 3])
def test_invalid_operation(operation: Any) -> None:
    telemetry, tracer, _ = make()
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.llm_span(operation, "m")
    assert info.value.code == "invalid_operation"
    assert tracer.spans == ()


def test_invalid_operation_literal() -> None:
    telemetry, _, _ = make()
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.llm_span("summarize", "m")
    assert info.value.code == "invalid_operation"


def test_error_messages_are_bounded() -> None:
    telemetry, _, _ = make()
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.llm_span("x" * 1000, "m")
    assert len(str(info.value)) <= 200
    assert len(str(GenAITelemetryError("invalid_usage", "y" * 500))) == 200


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": 1},
        {"model": "m", "max_tokens": -1},
        {"model": "m", "max_tokens": True},
        {"model": "m", "temperature": "hot"},
        {"model": "m", "temperature": True},
        {"model": "m", "temperature": float("nan")},
        {"model": "m", "temperature": float("inf")},
        {"model": "m", "server_address": 5},
    ],
)
def test_llm_span_rejects_bad_arguments(kwargs: dict[str, Any]) -> None:
    telemetry, tracer, _ = make()
    with pytest.raises(GenAITelemetryError) as info:
        telemetry.llm_span("chat", **kwargs)
    assert info.value.code == "invalid_usage"
    assert tracer.spans == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"provider_name": ""},
        {"provider_name": "  "},
        {"provider_name": 1},
        {"provider_name": "p", "max_content_chars": -1},
        {"provider_name": "p", "max_attribute_chars": 0},
        {"provider_name": "p", "max_attribute_chars": True},
    ],
)
def test_constructor_validation(kwargs: dict[str, Any]) -> None:
    with pytest.raises(GenAITelemetryError) as info:
        GenAITelemetry(**kwargs)
    assert info.value.code == "invalid_usage"


def test_default_tracer_and_meter_without_sdk() -> None:
    telemetry = GenAITelemetry(provider_name="openai", capture_content=True)
    with telemetry.llm_span("chat", "m") as llm:
        llm.record_response(input_tokens=1, output_tokens=2, finish_reasons=["stop"])
        llm.record_prompt([("user", "hi")])
        llm.record_completion("yo", "stop")
    with telemetry.tool_span("search"):
        pass
    cm = telemetry.llm_span("chat", "m")
    with pytest.raises(ValueError), cm:
        raise ValueError("x")


def test_recording_classes_are_otel_subclasses() -> None:
    tracer = RecordingTracer()
    span = RecordingSpan("s")
    assert isinstance(tracer, Tracer)
    assert isinstance(span, Span)


def test_recording_span_api() -> None:
    span = RecordingSpan("s", attributes={"a": 1})
    assert span.is_recording()
    span.set_attributes({"b": "x", "c": ["p", "q"]})
    assert span.attributes == {"a": 1, "b": "x", "c": ("p", "q")}
    span.add_event("e")
    span.update_name("t")
    assert span.name == "t"
    assert span.kind == SpanKind.INTERNAL
    span.set_status(StatusCode.ERROR, "bad")
    assert span.status.status_code == StatusCode.ERROR
    assert span.status.description == "bad"
    span.set_status(Status(StatusCode.OK))
    assert span.status.status_code == StatusCode.OK
    err = RuntimeError("x")
    span.record_exception(err)
    assert span.exceptions == (err,)
    assert span.get_span_context().is_valid
    span.end()
    span.end()
    assert span.ended
    assert not span.is_recording()
    span.set_attribute("z", 1)
    span.set_status(StatusCode.ERROR)
    span.record_exception(err)
    span.update_name("late")
    assert "z" not in span.attributes
    assert span.status.status_code == StatusCode.OK
    assert span.exceptions == (err,)
    assert span.name == "t"


def test_recording_span_caps_attributes_and_exceptions() -> None:
    span = RecordingSpan("s")
    for index in range(300):
        span.set_attribute(f"k{index}", index)
        span.record_exception(RuntimeError(str(index)))
    span.set_attribute("k0", "changed")
    assert len(span.attributes) == 128
    assert span.attributes["k0"] == "changed"
    assert len(span.exceptions) == 128


def test_recording_tracer_parenting_and_current_span() -> None:
    tracer = RecordingTracer()
    with tracer.start_as_current_span("outer") as outer:
        inner = tracer.start_span("inner", kind=SpanKind.SERVER)
        assert inner.parent is outer
        assert trace.get_current_span() is outer
    assert not isinstance(trace.get_current_span(), RecordingSpan)
    assert outer.is_recording() is False
    assert inner.is_recording()
    assert tracer.spans[0].parent is None
    assert [s.name for s in tracer.spans] == ["outer", "inner"]


def test_recording_tracer_end_on_exit_false_and_exception_propagates() -> None:
    tracer = RecordingTracer()
    with tracer.start_as_current_span("keep", end_on_exit=False) as span:
        assert isinstance(span, RecordingSpan)
    assert not span.ended
    err = KeyError("k")
    cm = tracer.start_as_current_span("fail")
    with pytest.raises(KeyError) as info, cm:
        raise err
    assert info.value is err
    assert not isinstance(trace.get_current_span(), RecordingSpan)


def test_recording_tracer_evicts_oldest() -> None:
    tracer = RecordingTracer(max_spans=2)
    for name in ("a", "b", "c"):
        tracer.start_span(name)
    assert [s.name for s in tracer.spans] == ["b", "c"]


def test_recording_meter_behaviour() -> None:
    meter = RecordingMeter(max_measurements=2, max_histograms=1)
    histogram = meter.create_histogram("a", unit="s", description="d")
    assert meter.create_histogram("a") is histogram
    assert (histogram.name, histogram.unit, histogram.description) == ("a", "s", "d")
    for value in (1, 2, 3):
        histogram.record(value)
    histogram.record(4, {"k": "v"})
    assert [m.value for m in histogram.measurements] == [3, 4]
    assert histogram.measurements[1].attributes == {"k": "v"}
    meter.create_histogram("b")
    with pytest.raises(KeyError):
        meter.histogram("a")
    assert meter.histogram("b").name == "b"
