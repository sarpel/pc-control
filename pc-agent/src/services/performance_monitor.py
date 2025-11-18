"""
End-to-End Performance Monitor Service with Battery Drain Reporting

This service provides comprehensive performance monitoring for the complete
voice command pipeline: audio capture → transcription → interpretation → execution.
Additionally monitors and reports battery usage patterns from connected Android devices.

Features:
- End-to-end latency tracking and validation
- Component-level performance metrics aggregation
- Real-time performance dashboards and alerts
- SLA compliance monitoring (<2s latency requirement)
- Performance bottleneck detection
- Historical performance data analysis
- Android battery usage monitoring and reporting
- Battery drain analysis and optimization recommendations

Following requirements from spec FR-008: <2s end-to-end latency
"""

import asyncio
import logging
import time
import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from collections import deque
from datetime import datetime, timedelta
import statistics
import threading

logger = logging.getLogger(__name__)


class PerformanceLevel(Enum):
    """Performance levels based on latency thresholds."""
    EXCELLENT = "excellent"  # <1s
    GOOD = "good"           # <1.5s
    ACCEPTABLE = "acceptable"  # <2s (meets FR-008)
    SLOW = "slow"          # 2s-3s
    CRITICAL = "critical"   # >3s


class AlertType(Enum):
    """Types of performance alerts."""
    LATENCY_HIGH = "latency_high"
    COMPONENT_SLOW = "component_slow"
    ERROR_RATE_HIGH = "error_rate_high"
    BATTERY_DRAIN = "battery_drain"
    BATTERY_LOW = "battery_low"
    BATTERY_CRITICAL = "battery_critical"
    BATTERY_OVERHEATING = "battery_overheating"
    NETWORK_ISSUES = "network_issues"


@dataclass
class BatteryMetrics:
    """Battery usage metrics from Android devices."""
    device_id: str
    battery_level: float  # Percentage
    is_charging: bool
    temperature: float   # Celsius
    drain_rate: float     # % per hour
    voice_assistant_usage: float  # % attributed to voice assistant
    estimated_time_remaining: float  # Minutes
    timestamp: float = field(default_factory=time.time)
    health_status: str = "unknown"


@dataclass
class BatteryAlert:
    """Battery-related alert."""
    device_id: str
    alert_type: AlertType
    severity: str  # "low", "medium", "high", "critical"
    message: str
    metrics: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class ComponentMetrics:
    """Metrics for individual components."""
    component_name: str
    processing_time_ms: float
    success: bool
    error_message: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EndToEndMetrics:
    """Complete end-to-end command metrics."""
    command_id: str
    total_latency_ms: float
    audio_capture_ms: float
    transcription_ms: float
    interpretation_ms: float
    execution_ms: float
    network_latency_ms: float
    success: bool
    performance_level: PerformanceLevel
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    component_breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class PerformanceAlert:
    """Performance alert notification."""
    alert_type: AlertType
    severity: str  # "low", "medium", "high", "critical"
    message: str
    metrics: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False


@dataclass
class PerformanceSummary:
    """Overall performance summary."""
    total_commands: int
    successful_commands: int
    failed_commands: int
    average_latency_ms: float
    p95_latency_ms: float  # 95th percentile
    p99_latency_ms: float  # 99th percentile
    sla_compliance_percent: float  # % of commands meeting <2s SLA
    current_performance_level: PerformanceLevel
    active_alerts: List[PerformanceAlert]
    time_window_minutes: int


class PerformanceMonitor:
    """
    End-to-end performance monitoring service.

    Monitors complete voice command pipeline and provides:
    - Real-time latency tracking and alerts
    - Component-level performance analysis
    - SLA compliance monitoring
    - Performance bottleneck detection
    - Historical performance data
    """

    def __init__(
        self,
        max_history_size: int = 1000,
        alert_threshold_sla: float = 95.0,  # % SLA compliance before alert
        max_active_alerts: int = 50
    ):
        """
        Initialize performance monitor with battery monitoring capabilities.

        Args:
            max_history_size: Maximum number of metrics to keep in memory
            alert_threshold_sla: SLA compliance threshold for alerts
            max_active_alerts: Maximum number of active alerts
        """
        # Metrics storage
        self.command_metrics: deque[EndToEndMetrics] = deque(maxlen=max_history_size)
        self.component_metrics: Dict[str, deque[ComponentMetrics]] = {}
        self.battery_metrics: Dict[str, deque[BatteryMetrics]] = {}  # device_id -> metrics
        self.active_alerts: List[PerformanceAlert] = []
        self.battery_alerts: List[BatteryAlert] = []
        self.alert_callbacks: List[Callable[[PerformanceAlert], None]] = []

        # Performance thresholds (from spec FR-008)
        self.SLA_MAX_LATENCY_MS = 2000.0  # 2 seconds requirement
        self.EXCELLENT_LATENCY_MS = 1000.0
        self.GOOD_LATENCY_MS = 1500.0
        self.CRITICAL_LATENCY_MS = 3000.0

        # Battery monitoring thresholds
        self.BATTERY_LOW_THRESHOLD = 20.0  # %
        self.BATTERY_CRITICAL_THRESHOLD = 5.0  # %
        self.BATTERY_HIGH_DRAIN_RATE = 15.0  # % per hour
        self.BATTERY_OVERHEAT_THRESHOLD = 45.0  # Celsius
        self.BATTERY_VOICE_ASSISTANT_HIGH_USAGE = 10.0  # % attributed to voice assistant

        # Configuration
        self.max_history_size = max_history_size
        self.alert_threshold_sla = alert_threshold_sla
        self.max_active_alerts = max_active_alerts

        # Active command tracking
        self.active_commands: Dict[str, Dict[str, float]] = {}
        self.command_lock = threading.Lock()

        # Background monitoring
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None

        logger.info(f"Performance monitor initialized with SLA threshold: {self.SLA_MAX_LATENCY_MS}ms")

    def start_command_tracking(self, command_id: str) -> str:
        """
        Start tracking a new voice command.

        Args:
            command_id: Unique identifier for the command

        Returns:
            Command ID for tracking
        """
        start_time = time.time()

        with self.command_lock:
            self.active_commands[command_id] = {
                "start_time": start_time,
                "audio_capture_start": start_time
            }

        logger.debug(f"Started tracking command: {command_id}")
        return command_id

    def record_component_metrics(
        self,
        command_id: str,
        component_name: str,
        processing_time_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record metrics for a specific component in the pipeline.

        Args:
            command_id: Command identifier
            component_name: Name of the component
            processing_time_ms: Processing time in milliseconds
            success: Whether the component succeeded
            error_message: Error message if failed
            metadata: Additional component metadata
        """
        metrics = ComponentMetrics(
            component_name=component_name,
            processing_time_ms=processing_time_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )

        # Store component metrics
        if component_name not in self.component_metrics:
            self.component_metrics[component_name] = deque(maxlen=self.max_history_size)
        self.component_metrics[component_name].append(metrics)

        # Update active command tracking
        with self.command_lock:
            if command_id in self.active_commands:
                self.active_commands[command_id][f"{component_name}_time"] = processing_time_ms
                self.active_commands[command_id][f"{component_name}_completed"] = time.time()

        # Check for component performance issues
        if not success or processing_time_ms > 1000:  # 1 second component threshold
            self._check_component_performance_alerts(component_name, metrics)

        logger.debug(f"Recorded {component_name} metrics for {command_id}: {processing_time_ms}ms")

    def record_audio_capture(self, command_id: str, capture_time_ms: float):
        """Record audio capture completion."""
        self.record_component_metrics(command_id, "audio_capture", capture_time_ms)

    def record_transcription(self, command_id: str, transcription_time_ms: float, success: bool = True, error: Optional[str] = None):
        """Record speech-to-text transcription completion."""
        self.record_component_metrics(
            command_id, "transcription", transcription_time_ms, success, error
        )

    def record_interpretation(self, command_id: str, interpretation_time_ms: float, success: bool = True, error: Optional[str] = None):
        """Record command interpretation completion."""
        self.record_component_metrics(
            command_id, "interpretation", interpretation_time_ms, success, error
        )

    def record_execution(self, command_id: str, execution_time_ms: float, success: bool = True, error: Optional[str] = None):
        """Record system command execution completion."""
        self.record_component_metrics(
            command_id, "execution", execution_time_ms, success, error
        )

    def record_network_latency(self, command_id: str, network_latency_ms: float):
        """Record network latency measurement."""
        self.record_component_metrics(command_id, "network", network_latency_ms)

    def complete_command(
        self,
        command_id: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> Optional[EndToEndMetrics]:
        """
        Complete command tracking and calculate end-to-end metrics.

        Args:
            command_id: Command identifier
            success: Whether the entire command succeeded
            error_message: Overall error message if failed

        Returns:
            EndToEndMetrics if command was tracked, None otherwise
        """
        with self.command_lock:
            if command_id not in self.active_commands:
                logger.warning(f"Command {command_id} not found in active tracking")
                return None

            command_data = self.active_commands.pop(command_id)

        # Calculate total latency
        end_time = time.time()
        total_latency_ms = (end_time - command_data["start_time"]) * 1000

        # Extract component times
        audio_capture_ms = command_data.get("audio_capture_time", 0.0)
        transcription_ms = command_data.get("transcription_time", 0.0)
        interpretation_ms = command_data.get("interpretation_time", 0.0)
        execution_ms = command_data.get("execution_time", 0.0)
        network_latency_ms = command_data.get("network_time", 0.0)

        # Create component breakdown
        component_breakdown = {
            "audio_capture": audio_capture_ms,
            "transcription": transcription_ms,
            "interpretation": interpretation_ms,
            "execution": execution_ms,
            "network": network_latency_ms
        }

        # Determine performance level
        performance_level = self._calculate_performance_level(total_latency_ms)

        # Create end-to-end metrics
        metrics = EndToEndMetrics(
            command_id=command_id,
            total_latency_ms=total_latency_ms,
            audio_capture_ms=audio_capture_ms,
            transcription_ms=transcription_ms,
            interpretation_ms=interpretation_ms,
            execution_ms=execution_ms,
            network_latency_ms=network_latency_ms,
            success=success,
            performance_level=performance_level,
            error=error_message,
            component_breakdown=component_breakdown
        )

        # Store metrics
        self.command_metrics.append(metrics)

        # Check for performance alerts
        self._check_end_to_end_performance_alerts(metrics)

        logger.info(f"Completed command {command_id}: {total_latency_ms:.1f}ms ({performance_level.value})")
        return metrics

    def _calculate_performance_level(self, latency_ms: float) -> PerformanceLevel:
        """Calculate performance level based on latency."""
        if latency_ms <= self.EXCELLENT_LATENCY_MS:
            return PerformanceLevel.EXCELLENT
        elif latency_ms <= self.GOOD_LATENCY_MS:
            return PerformanceLevel.GOOD
        elif latency_ms <= self.SLA_MAX_LATENCY_MS:
            return PerformanceLevel.ACCEPTABLE
        elif latency_ms <= self.CRITICAL_LATENCY_MS:
            return PerformanceLevel.SLOW
        else:
            return PerformanceLevel.CRITICAL

    def _check_end_to_end_performance_alerts(self, metrics: EndToEndMetrics):
        """Check for end-to-end performance alerts."""
        # Latency alerts
        if metrics.total_latency_ms > self.SLA_MAX_LATENCY_MS:
            self._create_alert(
                AlertType.LATENCY_HIGH,
                "high" if metrics.total_latency_ms > self.CRITICAL_LATENCY_MS else "medium",
                f"Komut gecikmesi SLA limitini aştı: {metrics.total_latency_ms:.1f}ms (limit: {self.SLA_MAX_LATENCY_MS}ms)",
                {
                    "command_id": metrics.command_id,
                    "latency_ms": metrics.total_latency_ms,
                    "sla_limit_ms": self.SLA_MAX_LATENCY_MS
                }
            )

        # Error alerts
        if not metrics.success:
            self._create_alert(
                AlertType.ERROR_RATE_HIGH,
                "medium",
                f"Komut başarısız oldu: {metrics.error}",
                {
                    "command_id": metrics.command_id,
                    "error": metrics.error
                }
            )

    def _check_component_performance_alerts(self, component_name: str, metrics: ComponentMetrics):
        """Check for component-specific performance alerts."""
        if not metrics.success:
            self._create_alert(
                AlertType.COMPONENT_SLOW,
                "medium",
                f"{component_name} bileşeni başarısız: {metrics.error_message}",
                {
                    "component": component_name,
                    "error": metrics.error_message,
                    "processing_time_ms": metrics.processing_time_ms
                }
            )
        elif metrics.processing_time_ms > 1000:  # 1 second threshold
            severity = "high" if metrics.processing_time_ms > 2000 else "medium"
            self._create_alert(
                AlertType.COMPONENT_SLOW,
                severity,
                f"{component_name} bileşeni yavaş çalışıyor: {metrics.processing_time_ms:.1f}ms",
                {
                    "component": component_name,
                    "processing_time_ms": metrics.processing_time_ms
                }
            )

    def _create_alert(
        self,
        alert_type: AlertType,
        severity: str,
        message: str,
        metrics_data: Dict[str, Any]
    ):
        """Create and store a performance alert."""
        alert = PerformanceAlert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            metrics=metrics_data
        )

        # Add to active alerts (limit size)
        self.active_alerts.append(alert)
        if len(self.active_alerts) > self.max_active_alerts:
            self.active_alerts.pop(0)  # Remove oldest alert

        # Trigger callbacks
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Error in alert callback: {e}")

        logger.warning(f"Performance alert: {message}")

    def get_performance_summary(self, time_window_minutes: int = 60) -> PerformanceSummary:
        """
        Get performance summary for specified time window.

        Args:
            time_window_minutes: Time window in minutes

        Returns:
            PerformanceSummary with overall metrics
        """
        # Filter metrics by time window
        cutoff_time = time.time() - (time_window_minutes * 60)
        recent_metrics = [
            m for m in self.command_metrics
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return PerformanceSummary(
                total_commands=0,
                successful_commands=0,
                failed_commands=0,
                average_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                sla_compliance_percent=100.0,
                current_performance_level=PerformanceLevel.EXCELLENT,
                active_alerts=[],
                time_window_minutes=time_window_minutes
            )

        # Calculate metrics
        total_commands = len(recent_metrics)
        successful_commands = sum(1 for m in recent_metrics if m.success)
        failed_commands = total_commands - successful_commands

        latencies = [m.total_latency_ms for m in recent_metrics]
        average_latency_ms = statistics.mean(latencies)
        p95_latency_ms = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        p99_latency_ms = statistics.quantiles(latencies, n=100)[98]  # 99th percentile

        # SLA compliance (FR-008: <2s latency)
        sla_compliant = sum(1 for m in recent_metrics if m.total_latency_ms <= self.SLA_MAX_LATENCY_MS)
        sla_compliance_percent = (sla_compliant / total_commands) * 100

        # Current performance level (based on last 10 commands)
        last_10_metrics = recent_metrics[-10:]
        last_10_latencies = [m.total_latency_ms for m in last_10_metrics]
        current_avg_latency = statistics.mean(last_10_latencies)
        current_performance_level = self._calculate_performance_level(current_avg_latency)

        return PerformanceSummary(
            total_commands=total_commands,
            successful_commands=successful_commands,
            failed_commands=failed_commands,
            average_latency_ms=average_latency_ms,
            p95_latency_ms=p95_latency_ms,
            p99_latency_ms=p99_latency_ms,
            sla_compliance_percent=sla_compliance_percent,
            current_performance_level=current_performance_level,
            active_alerts=self.active_alerts.copy(),
            time_window_minutes=time_window_minutes
        )

    def get_component_performance(self, component_name: str, time_window_minutes: int = 60) -> Dict[str, Any]:
        """
        Get performance metrics for a specific component.

        Args:
            component_name: Name of the component
            time_window_minutes: Time window in minutes

        Returns:
            Component performance metrics
        """
        if component_name not in self.component_metrics:
            return {"error": f"No metrics available for component: {component_name}"}

        cutoff_time = time.time() - (time_window_minutes * 60)
        recent_metrics = [
            m for m in self.component_metrics[component_name]
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {"message": f"No recent metrics for component: {component_name}"}

        total_operations = len(recent_metrics)
        successful_operations = sum(1 for m in recent_metrics if m.success)
        processing_times = [m.processing_time_ms for m in recent_metrics]

        return {
            "component_name": component_name,
            "total_operations": total_operations,
            "successful_operations": successful_operations,
            "success_rate_percent": (successful_operations / total_operations) * 100,
            "average_processing_time_ms": statistics.mean(processing_times),
            "p95_processing_time_ms": statistics.quantiles(processing_times, n=20)[18],
            "p99_processing_time_ms": statistics.quantiles(processing_times, n=100)[98],
            "time_window_minutes": time_window_minutes
        }

    def acknowledge_alert(self, alert_index: int) -> bool:
        """Acknowledge a performance alert."""
        if 0 <= alert_index < len(self.active_alerts):
            self.active_alerts[alert_index].acknowledged = True
            return True
        return False

    def clear_acknowledged_alerts(self):
        """Clear all acknowledged alerts."""
        self.active_alerts = [a for a in self.active_alerts if not a.acknowledged]

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """Add callback for performance alerts."""
        self.alert_callbacks.append(callback)

    def get_detailed_metrics(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get detailed end-to-end metrics.

        Args:
            limit: Maximum number of metrics to return

        Returns:
            List of detailed metrics as dictionaries
        """
        recent_metrics = list(self.command_metrics)[-limit:]
        return [asdict(m) for m in recent_metrics]

    def start_background_monitoring(self, check_interval_seconds: int = 30):
        """Start background performance monitoring."""
        if self.monitoring_active:
            logger.warning("Performance monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(
            self._background_monitoring_loop(check_interval_seconds)
        )
        logger.info("Started background performance monitoring")

    async def _background_monitoring_loop(self, check_interval_seconds: int):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Check for performance degradation
                summary = self.get_performance_summary(30)  # 30-minute window

                if summary.sla_compliance_percent < self.alert_threshold_sla:
                    self._create_alert(
                        AlertType.LATENCY_HIGH,
                        "high",
                        f"SLA uyumluluğu düştü: {summary.sla_compliance_percent:.1f}% (limit: {self.alert_threshold_sla}%)",
                        {
                            "sla_compliance_percent": summary.sla_compliance_percent,
                            "average_latency_ms": summary.average_latency_ms,
                            "time_window_minutes": 30
                        }
                    )

                await asyncio.sleep(check_interval_seconds)

            except Exception as e:
                logger.error(f"Error in background monitoring: {e}")
                await asyncio.sleep(check_interval_seconds)

    def stop_background_monitoring(self):
        """Stop background performance monitoring."""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
        self.monitoring_active = False
        logger.info("Stopped background performance monitoring")

    def export_metrics(self, filename: Optional[str] = None) -> str:
        """
        Export performance metrics to JSON file.

        Args:
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to exported file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_metrics_{timestamp}.json"

        export_data = {
            "export_timestamp": datetime.now().isoformat(),
            "summary": asdict(self.get_performance_summary(24 * 60)),  # 24-hour window
            "detailed_metrics": self.get_detailed_metrics(1000),
            "active_alerts": [asdict(alert) for alert in self.active_alerts],
            "component_performance": {
                component: self.get_component_performance(component)
                for component in self.component_metrics.keys()
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"Performance metrics exported to: {filename}")
        return filename

    def health_check(self) -> Dict[str, Any]:
        """Perform health check on performance monitor."""
        return {
            "status": "healthy" if self.monitoring_active else "inactive",
            "total_commands_tracked": len(self.command_metrics),
            "active_commands": len(self.active_commands),
            "active_alerts": len(self.active_alerts),
            "max_history_size": self.max_history_size,
            "sla_max_latency_ms": self.SLA_MAX_LATENCY_MS,
            "monitoring_active": self.monitoring_active,
            "components_monitored": list(self.component_metrics.keys())
        }

    def record_battery_metrics(
        self,
        device_id: str,
        battery_level: float,
        is_charging: bool,
        temperature: float,
        drain_rate: float,
        voice_assistant_usage: float,
        estimated_time_remaining: float,
        health_status: str = "unknown"
    ):
        """
        Record battery metrics from Android device.

        Args:
            device_id: Unique device identifier
            battery_level: Battery level percentage (0-100)
            is_charging: Whether device is currently charging
            temperature: Battery temperature in Celsius
            drain_rate: Battery drain rate in % per hour
            voice_assistant_usage: % of battery usage attributed to voice assistant
            estimated_time_remaining: Estimated minutes until battery empty
            health_status: Battery health status string
        """
        metrics = BatteryMetrics(
            device_id=device_id,
            battery_level=battery_level,
            is_charging=is_charging,
            temperature=temperature,
            drain_rate=drain_rate,
            voice_assistant_usage=voice_assistant_usage,
            estimated_time_remaining=estimated_time_remaining,
            health_status=health_status
        )

        # Store battery metrics
        if device_id not in self.battery_metrics:
            self.battery_metrics[device_id] = deque(maxlen=self.max_history_size)
        self.battery_metrics[device_id].append(metrics)

        # Check for battery alerts
        self._check_battery_alerts(device_id, metrics)

        logger.debug(f"Recorded battery metrics for device {device_id}: {battery_level:.1f}%")

    def get_device_battery_metrics(
        self,
        device_id: str,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Get battery metrics for a specific device.

        Args:
            device_id: Device identifier
            time_window_minutes: Time window in minutes

        Returns:
            Device battery metrics summary
        """
        if device_id not in self.battery_metrics:
            return {"error": f"No battery metrics available for device: {device_id}"}

        cutoff_time = time.time() - (time_window_minutes * 60)
        recent_metrics = [
            m for m in self.battery_metrics[device_id]
            if m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {"message": f"No recent battery metrics for device: {device_id}"}

        latest = recent_metrics[-1]
        
        # Calculate averages
        avg_drain_rate = statistics.mean([m.drain_rate for m in recent_metrics])
        avg_temperature = statistics.mean([m.temperature for m in recent_metrics])
        avg_voice_usage = statistics.mean([m.voice_assistant_usage for m in recent_metrics])

        # Calculate trends
        if len(recent_metrics) >= 2:
            first = recent_metrics[0]
            level_change = latest.battery_level - first.battery_level
            time_span = (latest.timestamp - first.timestamp) / 3600  # hours
            trend_drain_rate = level_change / time_span if time_span > 0 else 0
        else:
            trend_drain_rate = latest.drain_rate

        # Determine status
        if latest.is_charging:
            status = "charging"
        elif latest.battery_level <= self.BATTERY_CRITICAL_THRESHOLD:
            status = "critical"
        elif latest.battery_level <= self.BATTERY_LOW_THRESHOLD:
            status = "low"
        elif latest.temperature >= self.BATTERY_OVERHEAT_THRESHOLD:
            status = "overheating"
        else:
            status = "normal"

        return {
            "device_id": device_id,
            "status": status,
            "current_level": latest.battery_level,
            "is_charging": latest.is_charging,
            "temperature": latest.temperature,
            "health_status": latest.health_status,
            "drain_rate": {
                "current": latest.drain_rate,
                "average": avg_drain_rate,
                "trend": trend_drain_rate
            },
            "voice_assistant_usage": {
                "current": latest.voice_assistant_usage,
                "average": avg_voice_usage,
                "is_high": latest.voice_assistant_usage > self.BATTERY_VOICE_ASSISTANT_HIGH_USAGE
            },
            "estimated_time_remaining": latest.estimated_time_remaining,
            "time_window_minutes": time_window_minutes,
            "metrics_count": len(recent_metrics),
            "last_update": latest.timestamp
        }

    def get_all_devices_battery_summary(self) -> Dict[str, Any]:
        """
        Get battery summary for all connected devices.

        Returns:
            Summary of battery metrics across all devices
        """
        summary = {
            "total_devices": len(self.battery_metrics),
            "devices": {},
            "overall_status": "healthy",
            "alerts_count": len(self.battery_alerts)
        }

        for device_id in self.battery_metrics.keys():
            device_summary = self.get_device_battery_metrics(device_id, 60)
            summary["devices"][device_id] = device_summary

            # Update overall status based on worst device
            device_status = device_summary.get("status", "unknown")
            if device_status in ["critical", "overheating"]:
                summary["overall_status"] = "critical"
            elif device_status == "low" and summary["overall_status"] != "critical":
                summary["overall_status"] = "warning"

        return summary

    def get_battery_alerts(
        self,
        device_id: Optional[str] = None,
        alert_type: Optional[AlertType] = None
    ) -> List[BatteryAlert]:
        """
        Get battery alerts with optional filtering.

        Args:
            device_id: Optional device ID filter
            alert_type: Optional alert type filter

        Returns:
            Filtered list of battery alerts
        """
        alerts = self.battery_alerts.copy()

        # Apply filters
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return alerts

    def _check_battery_alerts(self, device_id: str, metrics: BatteryMetrics):
        """Check for battery-related alerts and create them."""
        alerts_to_create = []

        # Low battery alerts
        if not metrics.is_charging:
            if metrics.battery_level <= self.BATTERY_CRITICAL_THRESHOLD:
                alerts_to_create.append((
                    AlertType.BATTERY_CRITICAL,
                    "critical",
                    f"Kritik pil seviyesi: {metrics.battery_level:.1f}%",
                    {
                        "device_id": device_id,
                        "battery_level": metrics.battery_level,
                        "estimated_time_remaining": metrics.estimated_time_remaining
                    },
                    ["Hemen şarj etmeyi başlatın", "Pil tasarruf modunu etkinleştirin"]
                ))
            elif metrics.battery_level <= self.BATTERY_LOW_THRESHOLD:
                alerts_to_create.append((
                    AlertType.BATTERY_LOW,
                    "high",
                    f"Düşük pil seviyesi: {metrics.battery_level:.1f}%",
                    {
                        "device_id": device_id,
                        "battery_level": metrics.battery_level,
                        "estimated_time_remaining": metrics.estimated_time_remaining
                    },
                    ["Pil tasarruf modunu etkinleştirin", "Gereksiz uygulamaları kapatın"]
                ))

        # High drain rate alerts
        if metrics.drain_rate > self.BATTERY_HIGH_DRAIN_RATE:
            alerts_to_create.append((
                AlertType.BATTERY_DRAIN,
                "medium",
                f"Yüksek pil tüketimi: {metrics.drain_rate:.1f}%/saat",
                {
                    "device_id": device_id,
                    "drain_rate": metrics.drain_rate,
                    "voice_assistant_usage": metrics.voice_assistant_usage
                },
                ["Arka plan uygulamalarını kontrol edin", "Ekran parlaklığını azaltın"]
            ))

        # Overheating alerts
        if metrics.temperature >= self.BATTERY_OVERHEAT_THRESHOLD:
            severity = "critical" if metrics.temperature >= 50 else "high"
            alerts_to_create.append((
                AlertType.BATTERY_OVERHEATING,
                severity,
                f"Pil aşırı ısınıyor: {metrics.temperature:.1f}°C",
                {
                    "device_id": device_id,
                    "temperature": metrics.temperature,
                    "health_status": metrics.health_status
                },
                ["Cihazı soğutun", "Ağır uygulamaları kapatın", "Şarjı durdurun"]
            ))

        # Voice assistant high usage alerts
        if metrics.voice_assistant_usage > self.BATTERY_VOICE_ASSISTANT_HIGH_USAGE:
            alerts_to_create.append((
                AlertType.BATTERY_DRAIN,
                "low",
                f"Ses asistanı yüksek pil kullanımı: {metrics.voice_assistant_usage:.1f}%",
                {
                    "device_id": device_id,
                    "voice_assistant_usage": metrics.voice_assistant_usage,
                    "total_drain_rate": metrics.drain_rate
                },
                ["Daha az sıklıkla kullanın", "Mikrofon kalitesini优化优化"]
            ))

        # Create alerts
        for alert_type, severity, message, metrics_data, recommendations in alerts_to_create:
            alert = BatteryAlert(
                device_id=device_id,
                alert_type=alert_type,
                severity=severity,
                message=message,
                metrics=metrics_data,
                recommendations=recommendations
            )

            self.battery_alerts.append(alert)

            # Limit alert history
            if len(self.battery_alerts) > self.max_active_alerts:
                self.battery_alerts = self.battery_alerts[-self.max_active_alerts:]

            # Trigger callbacks
            for callback in self.alert_callbacks:
                try:
                    # Convert to PerformanceAlert for compatibility
                    perf_alert = PerformanceAlert(
                        alert_type=alert.alert_type,
                        severity=alert.severity,
                        message=alert.message,
                        metrics=alert.metrics
                    )
                    callback(perf_alert)
                except Exception as e:
                    logger.error(f"Error in battery alert callback: {e}")

            logger.warning(f"Battery alert for device {device_id}: {message}")

    def clear_device_battery_metrics(self, device_id: str):
        """Clear battery metrics for a specific device."""
        if device_id in self.battery_metrics:
            del self.battery_metrics[device_id]
        
        # Remove related alerts
        self.battery_alerts = [a for a in self.battery_alerts if a.device_id != device_id]
        
        logger.info(f"Cleared battery metrics for device: {device_id}")

    def acknowledge_battery_alert(self, alert_index: int) -> bool:
        """Acknowledge a battery alert."""
        if 0 <= alert_index < len(self.battery_alerts):
            self.battery_alerts[alert_index].acknowledged = True
            return True
        return False


# Global performance monitor instance
performance_monitor = PerformanceMonitor()