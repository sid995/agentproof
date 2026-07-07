"""Native schema tests."""

from datetime import UTC, datetime

from agentproof.schemas import BatchEnvelope, IngestRecord, SpanEnvelope, TraceEnvelope


def test_native_schema_serializes_datetime_for_backend() -> None:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    trace = TraceEnvelope(
        trace_id="trace-1",
        name="agent",
        started_at=started_at,
        ended_at=started_at,
        spans=[
            SpanEnvelope(
                span_id="span-1",
                name="work",
                started_at=started_at,
                ended_at=started_at,
            )
        ],
    )

    payload = BatchEnvelope(records=[IngestRecord(record_id="trace-1", payload=trace)]).model_dump(mode="json")

    assert payload["source"] == "agentproof"
    assert payload["schema_version"] == "agentproof.v1"
    assert payload["records"][0]["payload"]["started_at"] == "2026-01-01T00:00:00Z"
