"""
Network latency monitoring service for tracking connection quality.

This service monitors:
- WebSocket connection latency
- Packet loss detection
- Network quality metrics
- Connection stability indicators
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Callable, List
from collections import deque

logger = logging.getLogger(__name__)


class NetworkQuality(Enum):
    """Network quality levels based on latency and stability."""
    EXCELLENT = "excellent"  # <50ms, 0% loss
    GOOD = "good"           # 50-100ms, <5% loss
    FAIR = "fair"           # 100-200ms, 5-10% loss
    POOR = "poor"           # 200-500ms, 10-20% loss
    CRITICAL = "critical"   # >500ms or >20% loss


@dataclass
class NetworkMetrics:
    """Network quality metrics."""
    latency_ms: float
    jitter_ms: float
    packet_loss_percent: float
    quality: NetworkQuality
    timestamp: float
    connection_stable: bool


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    ping_id: str
    sent_at: float
    received_at: Optional[float] = None
    latency_ms: Optional[float] = None
    timed_out: bool = False


class NetworkMonitor:
    """
    Monitors network latency and quality for WebSocket connections.

    Features:
    - Continuous ping/pong latency tracking
    - Packet loss detection
    - Jitter calculation
    - Network quality assessment
    - Configurable thresholds and alerts
    """

    def __init__(
        self,
        ping_interval: float = 5.0,
        ping_timeout: float = 2.0,
        measurement_window: int = 20,
        alert_threshold_ms: float = 200.0,
        critical_threshold_ms: float = 500.0
    ):
        """
        Initialize network monitor.

        Args:
            ping_interval: Seconds between ping messages
            ping_timeout: Seconds to wait for pong response
            measurement_window: Number of measurements to keep for analysis
            alert_threshold_ms: Latency threshold for alerts
            critical_threshold_ms: Latency threshold for critical alerts
        """
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.measurement_window = measurement_window
        self.alert_threshold_ms = alert_threshold_ms
        self.critical_threshold_ms = critical_threshold_ms

        # Measurement tracking
        self.measurements: deque[LatencyMeasurement] = deque(maxlen=measurement_window)
        self.pending_pings: Dict[str, LatencyMeasurement] = {}

        # Current metrics
        self.current_metrics: Optional[NetworkMetrics] = None

        # Callbacks
        self.metrics_callback: Optional[Callable[[NetworkMetrics], None]] = None
        self.alert_callback: Optional[Callable[[str, NetworkMetrics], None]] = None

        # Monitoring state
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self.total_pings_sent = 0
        self.total_pongs_received = 0
        self.total_timeouts = 0

    async def start_monitoring(self, send_ping_func: Callable[[str], asyncio.Future]):
        """
        Start monitoring network latency.

        Args:
            send_ping_func: Async function to send ping message with ID
        """
        if self.is_monitoring:
            logger.warning("Network monitoring already started")
            return

        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(
            self._monitoring_loop(send_ping_func)
        )
        logger.info("Network monitoring started")

    async def stop_monitoring(self):
        """Stop monitoring network latency."""
        if not self.is_monitoring:
            return

        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Network monitoring stopped")

    async def _monitoring_loop(self, send_ping_func: Callable[[str], asyncio.Future]):
        """
        Main monitoring loop that sends pings and checks for timeouts.

        Args:
            send_ping_func: Function to send ping messages
        """
        while self.is_monitoring:
            try:
                # Send ping
                ping_id = f"ping_{int(time.time() * 1000)}_{self.total_pings_sent}"
                measurement = LatencyMeasurement(
                    ping_id=ping_id,
                    sent_at=time.time()
                )

                self.pending_pings[ping_id] = measurement
                self.total_pings_sent += 1

                # Send ping message
                await send_ping_func(ping_id)

                # Check for timeouts
                await self._check_timeouts()

                # Calculate current metrics
                self._calculate_metrics()

                # Wait for next ping
                await asyncio.sleep(self.ping_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(self.ping_interval)

    def record_pong(self, ping_id: str):
        """
        Record received pong response.

        Args:
            ping_id: ID of the ping message
        """
        measurement = self.pending_pings.get(ping_id)
        if not measurement:
            logger.warning(f"Received pong for unknown ping: {ping_id}")
            return

        # Calculate latency
        measurement.received_at = time.time()
        measurement.latency_ms = (measurement.received_at - measurement.sent_at) * 1000

        # Move to completed measurements
        self.measurements.append(measurement)
        del self.pending_pings[ping_id]
        self.total_pongs_received += 1

        logger.debug(f"Pong received for {ping_id}: {measurement.latency_ms:.2f}ms")

    async def _check_timeouts(self):
        """Check for timed out ping messages."""
        current_time = time.time()
        timed_out_pings = []

        for ping_id, measurement in self.pending_pings.items():
            if current_time - measurement.sent_at > self.ping_timeout:
                measurement.timed_out = True
                timed_out_pings.append(ping_id)
                self.total_timeouts += 1

        # Move timed out pings to measurements
        for ping_id in timed_out_pings:
            measurement = self.pending_pings[ping_id]
            self.measurements.append(measurement)
            del self.pending_pings[ping_id]
            logger.warning(f"Ping timeout: {ping_id}")

    def _calculate_metrics(self):
        """Calculate current network metrics."""
        if not self.measurements:
            return

        # Get successful measurements
        successful = [m for m in self.measurements if not m.timed_out]

        if not successful:
            # All measurements timed out
            self.current_metrics = NetworkMetrics(
                latency_ms=self.ping_timeout * 1000,
                jitter_ms=0.0,
                packet_loss_percent=100.0,
                quality=NetworkQuality.CRITICAL,
                timestamp=time.time(),
                connection_stable=False
            )
        else:
            # Calculate latency statistics
            latencies = [m.latency_ms for m in successful]
            avg_latency = sum(latencies) / len(latencies)

            # Calculate jitter (average deviation from mean)
            jitter = sum(abs(l - avg_latency) for l in latencies) / len(latencies)

            # Calculate packet loss
            total_measurements = len(self.measurements)
            lost_packets = sum(1 for m in self.measurements if m.timed_out)
            packet_loss = (lost_packets / total_measurements) * 100 if total_measurements > 0 else 0

            # Determine quality
            quality = self._determine_quality(avg_latency, packet_loss)

            # Check stability (last 5 measurements should be similar)
            recent = latencies[-5:] if len(latencies) >= 5 else latencies
            connection_stable = len(recent) >= 3 and max(recent) - min(recent) < 100

            self.current_metrics = NetworkMetrics(
                latency_ms=avg_latency,
                jitter_ms=jitter,
                packet_loss_percent=packet_loss,
                quality=quality,
                timestamp=time.time(),
                connection_stable=connection_stable
            )

        # Invoke callbacks
        if self.metrics_callback and self.current_metrics:
            try:
                self.metrics_callback(self.current_metrics)
            except Exception as e:
                logger.error(f"Error in metrics callback: {e}", exc_info=True)

        # Check for alerts
        self._check_alerts()

    def _determine_quality(self, latency_ms: float, packet_loss: float) -> NetworkQuality:
        """
        Determine network quality based on latency and packet loss.

        Args:
            latency_ms: Average latency in milliseconds
            packet_loss: Packet loss percentage

        Returns:
            NetworkQuality level
        """
        if latency_ms > self.critical_threshold_ms or packet_loss > 20:
            return NetworkQuality.CRITICAL
        elif latency_ms > self.alert_threshold_ms or packet_loss > 10:
            return NetworkQuality.POOR
        elif latency_ms > 100 or packet_loss > 5:
            return NetworkQuality.FAIR
        elif latency_ms > 50 or packet_loss > 0:
            return NetworkQuality.GOOD
        else:
            return NetworkQuality.EXCELLENT

    def _check_alerts(self):
        """Check if alerts should be triggered."""
        if not self.current_metrics or not self.alert_callback:
            return

        # Check for critical latency
        if self.current_metrics.latency_ms > self.critical_threshold_ms:
            self.alert_callback("critical_latency", self.current_metrics)

        # Check for high packet loss
        elif self.current_metrics.packet_loss_percent > 20:
            self.alert_callback("high_packet_loss", self.current_metrics)

        # Check for poor quality
        elif self.current_metrics.quality == NetworkQuality.POOR:
            self.alert_callback("poor_quality", self.current_metrics)

    def set_metrics_callback(self, callback: Callable[[NetworkMetrics], None]):
        """
        Set callback for metrics updates.

        Args:
            callback: Function to call with NetworkMetrics
        """
        self.metrics_callback = callback

    def set_alert_callback(self, callback: Callable[[str, NetworkMetrics], None]):
        """
        Set callback for network alerts.

        Args:
            callback: Function to call with alert type and metrics
        """
        self.alert_callback = callback

    def get_current_metrics(self) -> Optional[NetworkMetrics]:
        """Get current network metrics."""
        return self.current_metrics

    def get_statistics(self) -> Dict:
        """
        Get monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        return {
            "total_pings_sent": self.total_pings_sent,
            "total_pongs_received": self.total_pongs_received,
            "total_timeouts": self.total_timeouts,
            "success_rate": (
                (self.total_pongs_received / self.total_pings_sent * 100)
                if self.total_pings_sent > 0 else 0
            ),
            "current_quality": self.current_metrics.quality.value if self.current_metrics else None,
            "current_latency_ms": self.current_metrics.latency_ms if self.current_metrics else None,
            "is_monitoring": self.is_monitoring
        }

    def reset_statistics(self):
        """Reset monitoring statistics."""
        self.total_pings_sent = 0
        self.total_pongs_received = 0
        self.total_timeouts = 0
        self.measurements.clear()
        self.pending_pings.clear()
        self.current_metrics = None
        logger.info("Network monitor statistics reset")
