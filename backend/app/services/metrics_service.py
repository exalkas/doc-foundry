"""Metrics service for tracking system metrics and preparing for Prometheus integration."""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.services.logging_service import get_logger

logger = get_logger(__name__)


class MetricsService:
    """Service for tracking and aggregating metrics."""

    def __init__(self):
        """Initialize metrics service."""
        # In-memory metrics storage (in production, use Prometheus or similar)
        self._counters: Dict[str, int] = defaultdict(int)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = defaultdict(list)
        self._timers: Dict[str, List[float]] = defaultdict(list)

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Increment value (default: 1)
            labels: Optional labels for metric
        """
        key = self._build_key(name, labels)
        self._counters[key] += value
        logger.debug(f"Incremented counter: {key} = {self._counters[key]}")

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set a gauge metric value.

        Args:
            name: Metric name
            value: Gauge value
            labels: Optional labels for metric
        """
        key = self._build_key(name, labels)
        self._gauges[key] = value
        logger.debug(f"Set gauge: {key} = {value}")

    def record_histogram(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a histogram value.

        Args:
            name: Metric name
            value: Histogram value
            labels: Optional labels for metric
        """
        key = self._build_key(name, labels)
        self._histograms[key].append(value)
        # Keep only last 1000 values
        if len(self._histograms[key]) > 1000:
            self._histograms[key] = self._histograms[key][-1000:]

    def record_timing(
        self,
        name: str,
        duration_ms: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record a timing metric.

        Args:
            name: Metric name
            duration_ms: Duration in milliseconds
            labels: Optional labels for metric
        """
        key = self._build_key(name, labels)
        self._timers[key].append(duration_ms)
        # Keep only last 1000 values
        if len(self._timers[key]) > 1000:
            self._timers[key] = self._timers[key][-1000:]

    def _build_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Build metric key with labels.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Metric key string
        """
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get counter value.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Counter value
        """
        key = self._build_key(name, labels)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Gauge value or None
        """
        key = self._build_key(name, labels)
        return self._gauges.get(key)

    def get_histogram_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, float]]:
        """Get histogram statistics.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Dict with min, max, avg, count, or None
        """
        key = self._build_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return None

        return {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "count": len(values),
            "p50": sorted(values)[len(values) // 2],
            "p95": sorted(values)[int(len(values) * 0.95)],
            "p99": sorted(values)[int(len(values) * 0.99)],
        }

    def get_timing_stats(
        self,
        name: str,
        labels: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, float]]:
        """Get timing statistics.

        Args:
            name: Metric name
            labels: Optional labels

        Returns:
            Dict with min, max, avg, count, or None
        """
        key = self._build_key(name, labels)
        values = self._timers.get(key, [])
        if not values:
            return None

        return {
            "min_ms": min(values),
            "max_ms": max(values),
            "avg_ms": sum(values) / len(values),
            "count": len(values),
            "p50_ms": sorted(values)[len(values) // 2],
            "p95_ms": sorted(values)[int(len(values) * 0.95)],
            "p99_ms": sorted(values)[int(len(values) * 0.99)],
        }

    def record_job_processing(
        self,
        job_type: str,
        duration_ms: float,
        status: str,
        workspace_id: Optional[UUID] = None,
    ) -> None:
        """Record job processing metrics.

        Args:
            job_type: Job type (document_extraction, webhook_delivery)
            duration_ms: Processing duration in milliseconds
            status: Job status (succeeded, failed)
            workspace_id: Optional workspace ID
        """
        labels = {"job_type": job_type, "status": status}
        if workspace_id:
            labels["workspace_id"] = str(workspace_id)

        self.record_timing(f"job_processing_duration_ms", duration_ms, labels)
        self.increment_counter(f"jobs_processed_total", labels=labels)

        if status == "failed":
            self.increment_counter("jobs_failed_total", labels={"job_type": job_type})

    def record_webhook_delivery(
        self,
        status_code: int,
        duration_ms: float,
        workspace_id: Optional[UUID] = None,
    ) -> None:
        """Record webhook delivery metrics.

        Args:
            status_code: HTTP status code
            duration_ms: Delivery duration in milliseconds
            workspace_id: Optional workspace ID
        """
        status = "success" if 200 <= status_code < 300 else "failure"
        labels = {"status": status, "status_code": str(status_code)}
        if workspace_id:
            labels["workspace_id"] = str(workspace_id)

        self.record_timing("webhook_delivery_duration_ms", duration_ms, labels)
        self.increment_counter("webhooks_delivered_total", labels=labels)

    def get_jobs_per_hour(self, job_type: Optional[str] = None) -> float:
        """Get jobs processed per hour.

        Args:
            job_type: Optional job type filter

        Returns:
            Jobs per hour rate
        """
        # Simple implementation - count jobs in last hour
        # In production, use time-windowed counters
        labels = {"status": "succeeded"}
        if job_type:
            labels["job_type"] = job_type

        count = self.get_counter("jobs_processed_total", labels)
        # Assume this is over 1 hour (in production, use actual time windows)
        return count

    def get_failure_rate(self, job_type: Optional[str] = None) -> float:
        """Get job failure rate.

        Args:
            job_type: Optional job type filter

        Returns:
            Failure rate (0.0 to 1.0)
        """
        succeeded_labels = {"status": "succeeded"}
        failed_labels = {"status": "failed"}
        if job_type:
            succeeded_labels["job_type"] = job_type
            failed_labels["job_type"] = job_type

        succeeded = self.get_counter("jobs_processed_total", succeeded_labels)
        failed = self.get_counter("jobs_failed_total", failed_labels)

        total = succeeded + failed
        if total == 0:
            return 0.0

        return failed / total

    def get_webhook_success_rate(self) -> float:
        """Get webhook delivery success rate.

        Returns:
            Success rate (0.0 to 1.0)
        """
        success_labels = {"status": "success"}
        failure_labels = {"status": "failure"}

        success = self.get_counter("webhooks_delivered_total", success_labels)
        failure = self.get_counter("webhooks_delivered_total", failure_labels)

        total = success + failure
        if total == 0:
            return 1.0

        return success / total

    def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics for Prometheus or monitoring.

        Returns:
            Dict with all metrics
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: self.get_histogram_stats(k.split("{")[0])
                for k in self._histograms.keys()
            },
            "timers": {
                k: self.get_timing_stats(k.split("{")[0])
                for k in self._timers.keys()
            },
        }


# Global metrics instance
_metrics_instance: Optional[MetricsService] = None


def get_metrics() -> MetricsService:
    """Get global metrics service instance.

    Returns:
        MetricsService instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsService()
    return _metrics_instance

