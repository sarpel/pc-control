"""
Comprehensive Audit Logger

Provides centralized security audit logging for all security-related events
including authentication, authorization, command execution, and system access.
Implements structured logging with retention policies and query capabilities.

Task: T088 Add comprehensive audit logging for all security events
"""

import enum
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AuditEventType(enum.Enum):
    """Audit event types for categorization"""
    # Authentication events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    AUTH_TOKEN_CREATED = "auth_token_created"
    AUTH_TOKEN_EXPIRED = "auth_token_expired"
    AUTH_TOKEN_REVOKED = "auth_token_revoked"

    # Connection events
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_FAILED = "connection_failed"
    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_TIMEOUT = "connection_timeout"

    # Device pairing events
    PAIRING_INITIATED = "pairing_initiated"
    PAIRING_SUCCESS = "pairing_success"
    PAIRING_FAILURE = "pairing_failure"
    PAIRING_REVOKED = "pairing_revoked"

    # Certificate events
    CERTIFICATE_GENERATED = "certificate_generated"
    CERTIFICATE_VALIDATED = "certificate_validated"
    CERTIFICATE_INVALID = "certificate_invalid"
    CERTIFICATE_EXPIRED = "certificate_expired"

    # Command execution events
    COMMAND_RECEIVED = "command_received"
    COMMAND_EXECUTED = "command_executed"
    COMMAND_FAILED = "command_failed"
    COMMAND_BLOCKED = "command_blocked"

    # System operations
    SYSTEM_OPERATION = "system_operation"
    FILE_ACCESS = "file_access"
    FILE_DELETE = "file_delete"
    BROWSER_OPERATION = "browser_operation"

    # Security events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    ACCESS_DENIED = "access_denied"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"

    # Service lifecycle
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_ERROR = "service_error"
    CONFIG_CHANGED = "config_changed"


class AuditSeverity(enum.Enum):
    """Audit event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event"""
    event_type: AuditEventType
    severity: AuditSeverity
    message: str
    timestamp: datetime
    user_id: Optional[str] = None
    device_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    command_id: Optional[str] = None
    action_type: Optional[str] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.details:
            data['details'] = json.dumps(self.details)
        return data


class AuditLogger:
    """
    Comprehensive audit logger for security events.
    Stores events in SQLite with retention policies and query capabilities.
    """

    DEFAULT_RETENTION_DAYS = 90

    def __init__(self, db_path: str = "audit.db"):
        """
        Initialize the audit logger.

        Args:
            db_path: Path to the SQLite audit database
        """
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the audit database schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create audit_events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    device_id TEXT,
                    ip_address TEXT,
                    details TEXT,
                    command_id TEXT,
                    action_type TEXT,
                    success INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for common queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_event_type ON audit_events(event_type)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_severity ON audit_events(severity)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_events(timestamp)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_id ON audit_events(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_device_id ON audit_events(device_id)
            ''')

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def log(self, event: AuditEvent):
        """
        Log an audit event.

        Args:
            event: The audit event to log
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                event_dict = event.to_dict()

                cursor.execute('''
                    INSERT INTO audit_events (
                        event_type, severity, message, timestamp, user_id, device_id,
                        ip_address, details, command_id, action_type, success
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event_dict['event_type'],
                    event_dict['severity'],
                    event_dict['message'],
                    event_dict['timestamp'],
                    event_dict.get('user_id'),
                    event_dict.get('device_id'),
                    event_dict.get('ip_address'),
                    json.dumps(event_dict.get('details')) if isinstance(event_dict.get('details'), dict) else event_dict.get('details'),
                    event_dict.get('command_id'),
                    event_dict.get('action_type'),
                    1 if event_dict['success'] else 0
                ))

                conn.commit()

                # Also log to standard logger
                log_level = {
                    AuditSeverity.INFO: logging.INFO,
                    AuditSeverity.WARNING: logging.WARNING,
                    AuditSeverity.ERROR: logging.ERROR,
                    AuditSeverity.CRITICAL: logging.CRITICAL
                }[event.severity]

                logger.log(
                    log_level,
                    f"AUDIT [{event.event_type.value}] {event.message}",
                    extra={
                        'user_id': event.user_id,
                        'device_id': event.device_id,
                        'ip_address': event.ip_address
                    }
                )

        except Exception as e:
            logger.error(f"Failed to log audit event: {e}", exc_info=True)

    # Convenience methods for common audit events

    def log_auth_success(self, user_id: str, device_id: str, ip_address: str):
        """Log successful authentication"""
        self.log(AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            severity=AuditSeverity.INFO,
            message=f"User {user_id} authenticated successfully",
            timestamp=datetime.now(),
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            success=True
        ))

    def log_auth_failure(self, user_id: Optional[str], device_id: Optional[str], ip_address: str, reason: str):
        """Log failed authentication attempt"""
        self.log(AuditEvent(
            event_type=AuditEventType.AUTH_FAILURE,
            severity=AuditSeverity.WARNING,
            message=f"Authentication failed: {reason}",
            timestamp=datetime.now(),
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            details={'reason': reason},
            success=False
        ))

    def log_command_executed(self, command_id: str, action_type: str, user_id: str, details: Dict[str, Any]):
        """Log successful command execution"""
        self.log(AuditEvent(
            event_type=AuditEventType.COMMAND_EXECUTED,
            severity=AuditSeverity.INFO,
            message=f"Command executed: {action_type}",
            timestamp=datetime.now(),
            user_id=user_id,
            command_id=command_id,
            action_type=action_type,
            details=details,
            success=True
        ))

    def log_command_blocked(self, command_id: str, action_type: str, user_id: str, reason: str):
        """Log blocked command attempt"""
        self.log(AuditEvent(
            event_type=AuditEventType.COMMAND_BLOCKED,
            severity=AuditSeverity.WARNING,
            message=f"Command blocked: {action_type} - {reason}",
            timestamp=datetime.now(),
            user_id=user_id,
            command_id=command_id,
            action_type=action_type,
            details={'reason': reason},
            success=False
        ))

    def log_file_delete(self, file_path: str, user_id: str, success: bool, error: Optional[str] = None):
        """Log file deletion attempt"""
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING
        message = f"File deleted: {file_path}" if success else f"File deletion failed: {file_path}"

        self.log(AuditEvent(
            event_type=AuditEventType.FILE_DELETE,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            user_id=user_id,
            details={'file_path': file_path, 'error': error},
            success=success
        ))

    def log_rate_limit_exceeded(self, user_id: str, device_id: str, ip_address: str):
        """Log rate limit exceeded"""
        self.log(AuditEvent(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            severity=AuditSeverity.WARNING,
            message=f"Rate limit exceeded for user {user_id}",
            timestamp=datetime.now(),
            user_id=user_id,
            device_id=device_id,
            ip_address=ip_address,
            success=False
        ))

    def log_suspicious_activity(self, description: str, user_id: Optional[str], ip_address: str, details: Dict[str, Any]):
        """Log suspicious activity"""
        self.log(AuditEvent(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            severity=AuditSeverity.ERROR,
            message=f"Suspicious activity detected: {description}",
            timestamp=datetime.now(),
            user_id=user_id,
            ip_address=ip_address,
            details=details,
            success=False
        ))

    # Query methods

    def query_events(
        self,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        user_id: Optional[str] = None,
        device_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query audit events with filters.

        Args:
            event_type: Filter by event type
            severity: Filter by severity
            user_id: Filter by user ID
            device_id: Filter by device ID
            start_time: Filter by start timestamp
            end_time: Filter by end timestamp
            limit: Maximum number of results

        Returns:
            List of audit events
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM audit_events WHERE 1=1"
            params = []

            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)

            if severity:
                query += " AND severity = ?"
                params.append(severity.value)

            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)

            if device_id:
                query += " AND device_id = ?"
                params.append(device_id)

            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time.isoformat())

            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [dict(row) for row in rows]

    def get_failed_auth_attempts(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent failed authentication attempts"""
        start_time = datetime.now() - timedelta(hours=hours)
        return self.query_events(
            event_type=AuditEventType.AUTH_FAILURE,
            start_time=start_time,
            limit=limit
        )

    def get_suspicious_activity(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent suspicious activity"""
        start_time = datetime.now() - timedelta(hours=hours)
        return self.query_events(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            start_time=start_time,
            limit=limit
        )

    def get_user_activity(self, user_id: str, days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
        """Get activity for a specific user"""
        start_time = datetime.now() - timedelta(days=days)
        return self.query_events(
            user_id=user_id,
            start_time=start_time,
            limit=limit
        )

    def cleanup_old_events(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
        """
        Remove audit events older than retention period.

        Args:
            retention_days: Number of days to retain events

        Returns:
            Number of events deleted
        """
        cutoff_date = datetime.now() - timedelta(days=retention_days)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM audit_events WHERE timestamp < ?",
                    (cutoff_date.isoformat(),)
                )
                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted_count} audit events older than {retention_days} days")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old audit events: {e}", exc_info=True)
            return 0

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total events
            cursor.execute("SELECT COUNT(*) as total FROM audit_events")
            total = cursor.fetchone()['total']

            # Events by type
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_events
                GROUP BY event_type
                ORDER BY count DESC
                LIMIT 10
            """)
            by_type = [dict(row) for row in cursor.fetchall()]

            # Events by severity
            cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM audit_events
                GROUP BY severity
            """)
            by_severity = [dict(row) for row in cursor.fetchall()]

            # Recent activity (last 24 hours)
            yesterday = (datetime.now() - timedelta(days=1)).isoformat()
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM audit_events
                WHERE timestamp >= ?
            """, (yesterday,))
            recent_count = cursor.fetchone()['count']

            return {
                'total_events': total,
                'events_by_type': by_type,
                'events_by_severity': by_severity,
                'recent_activity_24h': recent_count
            }


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(db_path: str = "audit.db") -> AuditLogger:
    """Get or create the global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db_path)
    return _audit_logger
