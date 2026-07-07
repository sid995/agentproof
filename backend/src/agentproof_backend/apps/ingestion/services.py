"""Ingestion pipeline services."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from django.db import IntegrityError, transaction

from agentproof_backend.apps.api_keys.services import VerifiedAPIKey
from agentproof_backend.apps.ingestion.exceptions import BatchEnvelopeInvalid, BatchLimitExceeded
from agentproof_backend.apps.ingestion.models import TraceProcessingEvent
from agentproof_backend.apps.ingestion.redaction import redact_canonical_trace
from agentproof_backend.apps.outbox.publishers import TRACE_ACCEPTED
from agentproof_backend.apps.outbox.services import enqueue_outbox_event
from agentproof_backend.apps.projects.models import Environment
from agentproof_backend.apps.telemetry.exceptions import TelemetryError, UnsupportedTelemetryPayload
from agentproof_backend.apps.telemetry.models import Trace
from agentproof_backend.apps.telemetry.normalizers import normalize_telemetry
from agentproof_backend.apps.telemetry.services import persist_canonical_trace

MAX_RECORDS = 100
MAX_SPANS_TOTAL = 500
SUPPORTED_PAIRS = {
    ("agentproof", "agentproof.v1"),
    ("opentelemetry", "otel.v1"),
}


@dataclass
class AcceptedRecord:
    record_id: str
    external_trace_id: str
    trace_id: str
    status: str = "accepted"


@dataclass
class FailedRecord:
    record_id: str
    status: str
    reason: str


@dataclass
class BatchResult:
    batch_id: str
    accepted: list[AcceptedRecord] = field(default_factory=list)
    duplicates: list[FailedRecord] = field(default_factory=list)
    invalid: list[FailedRecord] = field(default_factory=list)
    rejected: list[FailedRecord] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        return {
            "accepted": len(self.accepted),
            "duplicates": len(self.duplicates),
            "invalid": len(self.invalid),
            "rejected": len(self.rejected),
        }


def ingest_trace_batch(
    *,
    verified: VerifiedAPIKey,
    source: str,
    schema_version: str,
    records: list[dict[str, Any]],
) -> BatchResult:
    """Top-level ingestion pipeline: validate envelope, normalize, redact, persist."""

    if (source, schema_version) not in SUPPORTED_PAIRS:
        raise BatchEnvelopeInvalid(f"Unsupported source/schema_version pair: {source}/{schema_version}")

    if not records:
        raise BatchEnvelopeInvalid("records must not be empty")

    if len(records) > MAX_RECORDS:
        raise BatchLimitExceeded(f"Batch exceeds maximum of {MAX_RECORDS} records")

    environment = Environment.objects.select_related("organization", "project").get(pk=verified.environment_id)
    capture_mode = environment.effective_capture_mode
    organization = environment.organization
    project = environment.project

    batch_id = str(uuid.uuid4())
    result = BatchResult(batch_id=batch_id)

    # Track identities seen within this batch to detect intra-batch duplicates
    seen_identities: set[tuple[str, str]] = set()

    existing_identities: set[tuple[str, str]] = set()

    total_spans = 0

    for record in records:
        record_id = str(record.get("record_id") or "")
        payload = record.get("payload", {})

        try:
            canonical_traces = normalize_telemetry(
                schema_version=schema_version,
                source=source,
                payload=payload,
            )
        except UnsupportedTelemetryPayload as exc:
            result.invalid.append(FailedRecord(record_id=record_id, status="invalid", reason=str(exc)))
            continue
        except Exception as exc:
            result.invalid.append(FailedRecord(record_id=record_id, status="invalid", reason=str(exc)))
            continue

        candidate_identities = {
            (canonical_trace.external_trace_id, canonical_trace.schema_version) for canonical_trace in canonical_traces
        }
        if candidate_identities:
            existing_identities.update(
                Trace.objects.filter(
                    environment_id=verified.environment_id,
                    external_trace_id__in=[identity[0] for identity in candidate_identities],
                    schema_version__in=[identity[1] for identity in candidate_identities],
                ).values_list("external_trace_id", "schema_version")
            )

        for canonical_trace in canonical_traces:
            identity = (canonical_trace.external_trace_id, canonical_trace.schema_version)

            if identity in seen_identities or identity in existing_identities:
                result.duplicates.append(
                    FailedRecord(
                        record_id=record_id,
                        status="duplicate",
                        reason=f"Trace {canonical_trace.external_trace_id} already exists",
                    )
                )
                continue

            total_spans += len(canonical_trace.spans)
            if total_spans > MAX_SPANS_TOTAL:
                result.rejected.append(
                    FailedRecord(
                        record_id=record_id,
                        status="rejected",
                        reason="Batch span limit exceeded",
                    )
                )
                continue

            seen_identities.add(identity)

            redacted = redact_canonical_trace(canonical_trace, capture_mode)

            try:
                trace = _persist_with_processing_event(
                    organization=organization,
                    project=project,
                    environment=environment,
                    canonical_trace=redacted,
                )
            except TelemetryError as exc:
                result.invalid.append(FailedRecord(record_id=record_id, status="invalid", reason=str(exc)))
                continue
            except IntegrityError as exc:
                result.rejected.append(FailedRecord(record_id=record_id, status="rejected", reason=str(exc)))
                continue

            result.accepted.append(
                AcceptedRecord(
                    record_id=record_id,
                    external_trace_id=canonical_trace.external_trace_id,
                    trace_id=str(trace.id),
                )
            )

    return result


@transaction.atomic
def _persist_with_processing_event(
    *,
    organization: Any,
    project: Any,
    environment: Any,
    canonical_trace: Any,
) -> Trace:
    """Persist trace and create processing event in one transaction."""
    trace = persist_canonical_trace(
        organization=organization,
        project=project,
        environment=environment,
        canonical_trace=canonical_trace,
    )

    event, _created = TraceProcessingEvent.objects.get_or_create(
        trace=trace,
        defaults={
            "organization": organization,
        },
    )

    enqueue_outbox_event(
        organization=organization,
        event_type=TRACE_ACCEPTED,
        aggregate_type="trace",
        aggregate_id=trace.id,
        payload={
            "trace_id": str(trace.id),
            "processing_event_id": str(event.id),
        },
    )

    return trace
