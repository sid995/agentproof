"""DRF serializers for the ingestion API."""

from typing import Any

from rest_framework import serializers

MAX_RECORDS = 100


class IngestRecordSerializer(serializers.Serializer[dict[str, Any]]):
    record_id = serializers.CharField(required=False, default="", allow_blank=True)
    payload = serializers.DictField(child=serializers.JSONField(), required=True)


class IngestTraceBatchSerializer(serializers.Serializer[dict[str, Any]]):
    source = serializers.CharField()  # type: ignore[assignment]
    schema_version = serializers.CharField()
    records = serializers.ListField(
        child=IngestRecordSerializer(),
        min_length=1,
        max_length=MAX_RECORDS,
    )

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        supported = {
            ("agentproof", "agentproof.v1"),
            ("opentelemetry", "otel.v1"),
        }
        if (data["source"], data["schema_version"]) not in supported:
            raise serializers.ValidationError(
                f"Unsupported source/schema_version pair: {data['source']}/{data['schema_version']}"
            )
        return data


class AcceptedRecordSerializer(serializers.Serializer[dict[str, Any]]):
    record_id = serializers.CharField()
    external_trace_id = serializers.CharField()
    trace_id = serializers.CharField()
    status = serializers.CharField()


class FailedRecordSerializer(serializers.Serializer[dict[str, Any]]):
    record_id = serializers.CharField()
    status = serializers.CharField()
    reason = serializers.CharField()


class BatchSummarySerializer(serializers.Serializer[dict[str, Any]]):
    accepted = serializers.IntegerField()
    duplicates = serializers.IntegerField()
    invalid = serializers.IntegerField()
    rejected = serializers.IntegerField()


class BatchResultSerializer(serializers.Serializer[dict[str, Any]]):
    batch_id = serializers.CharField()
    summary = BatchSummarySerializer()
    accepted = AcceptedRecordSerializer(many=True)
    duplicates = FailedRecordSerializer(many=True)
    invalid = FailedRecordSerializer(many=True)
    rejected = FailedRecordSerializer(many=True)
