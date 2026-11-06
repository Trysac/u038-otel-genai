"""In-memory recorders for testing code instrumented with otel_genai.

Every recorder keeps at most 10_000 entries and drops the oldest first.
"""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from itertools import count
from typing import Any, NamedTuple

from opentelemetry import trace
from opentelemetry.context import Context, attach, detach
from opentelemetry.trace import Link, Span, SpanContext, SpanKind, Status, StatusCode, Tracer
from opentelemetry.util.types import AttributeValue

MAX_RECORDS = 10_000
MAX_PER_SPAN = 128
MAX_HISTOGRAMS = 1000


class RecordingSpan(Span):
    """A span that stores what was done to it."""

    def __init__(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, AttributeValue] | None = None,
        parent: RecordingSpan | None = None,
        span_id: int = 1,
    ) -> None:
        self._name = name
        self._kind = kind
        self._attributes: dict[str, AttributeValue] = {}
        self._status = Status(StatusCode.UNSET)
        self._exceptions: list[BaseException] = []
        self._parent = parent
        self._ended = False
        self._context = SpanContext(trace_id=1, span_id=span_id, is_remote=False)
        if attributes:
            self.set_attributes(attributes)

    @property
    def name(self) -> str:
        """Current span name."""
        return self._name

    @property
    def kind(self) -> SpanKind:
        """Span kind."""
        return self._kind

    @property
    def attributes(self) -> dict[str, AttributeValue]:
        """Copy of the recorded attributes."""
        return dict(self._attributes)

    @property
    def status(self) -> Status:
        """Current status."""
        return self._status

    @property
    def exceptions(self) -> tuple[BaseException, ...]:
        """Exceptions recorded on the span."""
        return tuple(self._exceptions)

    @property
    def parent(self) -> RecordingSpan | None:
        """The recording span that was current when this one started."""
        return self._parent

    @property
    def ended(self) -> bool:
        """Whether ``end`` was called."""
        return self._ended

    def end(self, end_time: int | None = None) -> None:
        """Mark the span as ended."""
        self._ended = True

    def get_span_context(self) -> SpanContext:
        """Return a deterministic valid span context."""
        return self._context

    def set_attributes(self, attributes: Mapping[str, AttributeValue]) -> None:
        """Set several attributes."""
        for key, value in attributes.items():
            self.set_attribute(key, value)

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        """Set one attribute; ignored after end or beyond 128 attributes."""
        if self._ended:
            return
        if key not in self._attributes and len(self._attributes) >= MAX_PER_SPAN:
            return
        if isinstance(value, list | tuple):
            self._attributes[key] = tuple(value)
        else:
            self._attributes[key] = value

    def add_event(
        self,
        name: str,
        attributes: Mapping[str, AttributeValue] | None = None,
        timestamp: int | None = None,
    ) -> None:
        """Events are accepted and not stored."""

    def update_name(self, name: str) -> None:
        """Rename the span."""
        if not self._ended:
            self._name = name

    def is_recording(self) -> bool:
        """True until the span ends."""
        return not self._ended

    def set_status(self, status: Status | StatusCode, description: str | None = None) -> None:
        """Set the status; ignored after end."""
        if self._ended:
            return
        if isinstance(status, StatusCode):
            status = Status(status, description)
        self._status = status

    def record_exception(
        self,
        exception: BaseException,
        attributes: Mapping[str, AttributeValue] | None = None,
        timestamp: int | None = None,
        escaped: bool = False,
    ) -> None:
        """Store the exception; ignored after end or beyond 128 exceptions."""
        if self._ended or len(self._exceptions) >= MAX_PER_SPAN:
            return
        self._exceptions.append(exception)


@contextmanager
def _current(span: RecordingSpan, end_on_exit: bool) -> Iterator[Span]:
    token = attach(trace.set_span_in_context(span))
    try:
        yield span
    finally:
        detach(token)
        if end_on_exit:
            span.end()


class RecordingTracer(Tracer):
    """A tracer that keeps started spans in memory."""

    def __init__(self, max_spans: int = MAX_RECORDS) -> None:
        self._spans: deque[RecordingSpan] = deque(maxlen=max_spans)
        self._ids = count(1)

    @property
    def spans(self) -> tuple[RecordingSpan, ...]:
        """Recorded spans, oldest first."""
        return tuple(self._spans)

    def _create(
        self,
        name: str,
        context: Context | None,
        kind: SpanKind,
        attributes: Mapping[str, AttributeValue] | None,
    ) -> RecordingSpan:
        current = trace.get_current_span(context)
        parent = current if isinstance(current, RecordingSpan) else None
        span = RecordingSpan(name, kind, attributes, parent, next(self._ids))
        self._spans.append(span)
        return span

    def start_span(
        self,
        name: str,
        context: Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, AttributeValue] | None = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
    ) -> RecordingSpan:
        """Start a span without making it current."""
        return self._create(name, context, kind, attributes)

    def start_as_current_span(
        self,
        name: str,
        context: Context | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Mapping[str, AttributeValue] | None = None,
        links: Sequence[Link] | None = None,
        start_time: int | None = None,
        record_exception: bool = True,
        set_status_on_exception: bool = True,
        end_on_exit: bool = True,
    ) -> Any:
        """Start a span and return a context manager that makes it current."""
        span = self._create(name, context, kind, attributes)
        return _current(span, end_on_exit)


class Measurement(NamedTuple):
    """One recorded histogram value."""

    value: float
    attributes: Mapping[str, str]


class RecordingHistogram:
    """A histogram that keeps its measurements in memory."""

    def __init__(
        self,
        name: str,
        unit: str = "",
        description: str = "",
        max_measurements: int = MAX_RECORDS,
    ) -> None:
        self.name = name
        self.unit = unit
        self.description = description
        self._measurements: deque[Measurement] = deque(maxlen=max_measurements)

    @property
    def measurements(self) -> tuple[Measurement, ...]:
        """Recorded measurements, oldest first."""
        return tuple(self._measurements)

    def record(self, amount: float, attributes: Mapping[str, str] | None = None) -> None:
        """Record one measurement."""
        self._measurements.append(Measurement(amount, dict(attributes or {})))


class RecordingMeter:
    """A meter that implements ``create_histogram`` only."""

    def __init__(
        self,
        max_measurements: int = MAX_RECORDS,
        max_histograms: int = MAX_HISTOGRAMS,
    ) -> None:
        self._max_measurements = max_measurements
        self._max_histograms = max_histograms
        self._histograms: OrderedDict[str, RecordingHistogram] = OrderedDict()

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
    ) -> RecordingHistogram:
        """Create (or return the existing) histogram called ``name``."""
        existing = self._histograms.get(name)
        if existing is not None:
            return existing
        histogram = RecordingHistogram(name, unit, description, self._max_measurements)
        self._histograms[name] = histogram
        while len(self._histograms) > self._max_histograms:
            self._histograms.popitem(last=False)
        return histogram

    def histogram(self, name: str) -> RecordingHistogram:
        """Return a created histogram; raises ``KeyError`` if unknown."""
        return self._histograms[name]
