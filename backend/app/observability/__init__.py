"""Operational telemetry for the Horus ATC backend.

ADR-009 splits the two kinds of trace deliberately: product provenance is a
product feature and lives in PostgreSQL as ``TrainingSessionEvent`` rows, while
this module covers operational telemetry only. The exporter is a deployment
choice -- console, a collector on the same VPS, or an OTLP endpoint -- never a
product dependency, so nothing here may take a request or a training session
down with it. Every failure path degrades to "no telemetry" and carries on.
"""

from app.observability.telemetry import configure_telemetry, span_for_session

__all__ = ["configure_telemetry", "span_for_session"]
