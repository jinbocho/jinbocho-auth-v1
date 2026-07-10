from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import settings


def instrument_logging() -> None:
    """Patch the logging module so every LogRecord carries otelTraceID/otelSpanID.

    Must run before configure_logging() installs a formatter referencing those
    fields: LoggingInstrumentor patches logging.Logger.makeRecord process-wide,
    so calling it first guarantees the fields exist by the time anything logs.
    No-op unless OTEL_ENABLED=true.

    inject_trace_context=True is required for the fields to actually be set —
    set_logging_format=False only skips calling logging.basicConfig() (we
    install our own formatter via configure_logging()), it does not by itself
    inject otelTraceID/otelSpanID onto records.
    """
    if settings.otel_enabled:
        LoggingInstrumentor().instrument(set_logging_format=False, inject_trace_context=True)


def configure_telemetry(app: FastAPI, *, service_name: str, engine: AsyncEngine) -> None:
    """Wire a /metrics endpoint and OTLP trace export to the local Grafana Alloy
    collector (see ADR-012). No-op unless OTEL_ENABLED=true — a deployment
    without the observability Docker Compose profile behaves exactly as before.
    """
    if not settings.otel_enabled:
        return

    Instrumentator().instrument(app).expose(app, include_in_schema=False, tags=["observability"])

    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name, "service.namespace": "jinbocho"})
    )
    exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_otlp_endpoint.rstrip('/')}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
