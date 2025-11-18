"""
Security audit logging service.

Logs all security-relevant events for compliance and debugging:
- Authentication attempts (success/failure)
- Pairing events (initiate, verify, revoke)
- Connection attempts and errors
- Certificate operations

Retention: 90 days per FR-012
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from src.database.connection import Database

logger = logging.getLogger(__name__)


class AuditEvent(Enum):
    """Audit event types."""
    PAIRING_INITIATED = "pairing_initiated"
    PAIRING_INITIATE_FAILED = "pairing_initiate_failed"
    PAIRING_VERIFICATION_FAILED = "pairing_verification_failed"
    PAIRING_VERIFIED = "pairing_verified"
    PAIRING_STATUS_CHECKED = "pairing_status_checked"
    PAIRING_REVOKED = "pairing_revoked"
    AUTH_TOKEN_ROTATED = "auth_token_rotated"
    WEBSOCKET_CONNECTION_ESTABLISHED = "websocket_connection_established"
    WEBSOCKET_CONNECTION_FAILED = "websocket_connection_failed"
    WEBSOCKET_AUTHENTICATION_FAILED = "websocket_authentication_failed"
    CERTIFICATE_GENERATION_FAILED = "certificate_generation_failed"
    CONNECTION_LIMIT_EXCEEDED = "connection_limit_exceeded"


class Severity(Enum):
    """Event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditLogEntry:
    """Single audit log entry."""
    id: Optional[int] = None
    timestamp: datetime = None
    event_type: str = ""
    device_id: str = ""
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = None
    severity: str = Severity.INFO.value
    security_related: bool = False
    session_id: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.details is None:
            self.details = {}


class AuditLogService:
    """
    Service for security audit logging.

    Features:
    - Structured logging for security events
    - 90-day retention
    - Query capabilities for investigations
    - JSON serialization
    """

    RETENTION_DAYS = 90

    def __init__(self, database: Database):
        """
        Initialize audit log service.

        Args:
            database: Database connection for persistence
        """
        self.db = database
        logger.info("Audit log service initialized")

    async def log_event(
        self,
        event_type: AuditEvent,
        device_id: str,
        details: Optional[Dict[str, Any]] = None,
        severity: Severity = Severity.INFO,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        security_related: bool = False
    ):
        """
        Log an audit event.

        Args:
            event_type: Type of event
            device_id: Device identifier
            details: Additional event details
            severity: Event severity
            ip_address: Client IP address
            user_agent: Client user agent
            user_id: User identifier (if applicable)
            session_id: Session identifier
            security_related: Whether this is a security-relevant event
        """
        try:
            # Create log entry
            entry = AuditLogEntry(
                event_type=event_type.value,
                device_id=device_id,
                details=details or {},
                severity=severity.value,
                ip_address=ip_address,
                user_agent=user_agent,
                user_id=user_id,
                session_id=session_id,
                security_related=security_related
            )

            # Save to database
            await self._save_log_entry(entry)

            # Also log to application logger for immediate visibility
            self._log_to_file_logger(entry)

            # For security events, also trigger immediate alert if needed
            if security_related and severity in [Severity.ERROR, Severity.CRITICAL]:
                await self._handle_security_alert(entry)

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)
            # Don't raise - logging failures shouldn't break the application

    async def get_logs_for_device(
        self,
        device_id: str,
        limit: int = 100,
        since_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs for a specific device.

        Args:
            device_id: Device identifier
            limit: Maximum number of entries to return
            since_days: How many days back to search

        Returns:
            List of log entries as dictionaries
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=since_days)

            query = """
                SELECT * FROM audit_logs
                WHERE device_id = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """

            rows = await self.db.fetch_all(query, (device_id, cutoff_date, limit))

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get logs for device {device_id}: {e}", exc_info=True)
            return []

    async def get_security_events(
        self,
        limit: int = 50,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent security-related events.

        Args:
            limit: Maximum number of entries
            since_hours: How many hours back to search

        Returns:
            List of security event logs
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=since_hours)

            query = """
                SELECT * FROM audit_logs
                WHERE security_related = 1 AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """

            rows = await self.db.fetch_all(query, (cutoff_date, limit))

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get security events: {e}", exc_info=True)
            return []

    async def get_failed_authentications(
        self,
        limit: int = 100,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent failed authentication attempts.

        Args:
            limit: Maximum number of entries
            since_hours: How many hours back to search

        Returns:
            List of failed authentication logs
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=since_hours)

            # Look for failed pairing verifications and WebSocket auth failures
            failed_events = [
                AuditEvent.PAIRING_VERIFICATION_FAILED.value,
                "websocket_authentication_failed"
            ]

            query = """
                SELECT * FROM audit_logs
                WHERE event_type IN ({}) AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """.format(','.join(f"'{event}'" for event in failed_events))

            rows = await self.db.fetch_all(query, (cutoff_date, limit))

            return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get failed authentications: {e}", exc_info=True)
            return []

    async def cleanup_old_logs(self):
        """Clean up logs older than retention period."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.RETENTION_DAYS)

            query = "DELETE FROM audit_logs WHERE timestamp < ?"
            result = await self.db.execute(query, (cutoff_date,))

            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} old audit log entries")

        except Exception as e:
            logger.error(f"Failed to cleanup old audit logs: {e}", exc_info=True)

    async def get_audit_statistics(
        self,
        since_days: int = 7
    ) -> Dict[str, Any]:
        """
        Get audit statistics for monitoring.

        Args:
            since_days: How many days to include in statistics

        Returns:
            Dictionary with various statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=since_days)

            # Total events
            total_query = "SELECT COUNT(*) as count FROM audit_logs WHERE timestamp >= ?"
            total_row = await self.db.fetch_one(total_query, (cutoff_date,))
            total_events = total_row[0] if total_row else 0

            # Security events
            security_query = """
                SELECT COUNT(*) as count
                FROM audit_logs
                WHERE security_related = 1 AND timestamp >= ?
            """
            security_row = await self.db.fetch_one(security_query, (cutoff_date,))
            security_events = security_row[0] if security_row else 0

            # Failed authentications
            failed_query = """
                SELECT COUNT(*) as count
                FROM audit_logs
                WHERE event_type LIKE '%failed%' AND timestamp >= ?
            """
            failed_row = await self.db.fetch_one(failed_query, (cutoff_date,))
            failed_events = failed_row[0] if failed_row else 0

            # Unique devices
            devices_query = """
                SELECT COUNT(DISTINCT device_id) as count
                FROM audit_logs
                WHERE timestamp >= ?
            """
            devices_row = await self.db.fetch_one(devices_query, (cutoff_date,))
            unique_devices = devices_row[0] if devices_row else 0

            return {
                "total_events": total_events,
                "security_events": security_events,
                "failed_authentications": failed_events,
                "unique_devices": unique_devices,
                "period_days": since_days
            }

        except Exception as e:
            logger.error(f"Failed to get audit statistics: {e}", exc_info=True)
            return {}

    async def _save_log_entry(self, entry: AuditLogEntry):
        """Save audit log entry to database."""
        query = """
            INSERT INTO audit_logs (
                timestamp, event_type, device_id, user_id, ip_address,
                user_agent, details, severity, security_related, session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        values = (
            entry.timestamp,
            entry.event_type,
            entry.device_id,
            entry.user_id,
            entry.ip_address,
            entry.user_agent,
            json.dumps(entry.details),
            entry.severity,
            int(entry.security_related),
            entry.session_id
        )

        await self.db.execute(query, values)

    def _log_to_file_logger(self, entry: AuditLogEntry):
        """Also log to application logger for immediate visibility."""
        # Create log message
        log_message = f"[{entry.event_type}] Device: {entry.device_id}"
        if entry.security_related:
            log_message = f"[SECURITY] {log_message}"

        if entry.details:
            log_message += f" Details: {json.dumps(entry.details, default=str)}"

        # Log at appropriate level
        if entry.severity == Severity.CRITICAL.value:
            logger.critical(log_message)
        elif entry.severity == Severity.ERROR.value:
            logger.error(log_message)
        elif entry.severity == Severity.WARNING.value:
            logger.warning(log_message)
        else:
            logger.info(log_message)

    async def _handle_security_alert(self, entry: AuditLogEntry):
        """Handle security alerts for immediate monitoring."""
        # For MVP, just log critical security events
        # In production, this could trigger:
        # - Email/SMS alerts
        # - SIEM integration
        # - Temporary IP blocking
        # - Rate limiting

        logger.critical(
            f"SECURITY ALERT: {entry.event_type} from {entry.ip_address} "
            f"for device {entry.device_id}"
        )