"""
Unit tests for Audit Logger

Tests audit event logging, querying, and retention management.
Target: 90%+ code coverage
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.services.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    get_audit_logger
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def audit_logger(temp_db):
    """Create an AuditLogger instance with temporary database"""
    return AuditLogger(db_path=temp_db)


class TestAuditEvent:
    """Tests for AuditEvent data class"""

    def test_audit_event_creation(self):
        """Test creating an audit event"""
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            severity=AuditSeverity.INFO,
            message="User authenticated",
            timestamp=datetime.now(),
            user_id="user123",
            device_id="device456",
            ip_address="192.168.1.100"
        )

        assert event.event_type == AuditEventType.AUTH_SUCCESS
        assert event.severity == AuditSeverity.INFO
        assert event.message == "User authenticated"
        assert event.user_id == "user123"
        assert event.device_id == "device456"
        assert event.ip_address == "192.168.1.100"
        assert event.success is True

    def test_audit_event_to_dict(self):
        """Test converting audit event to dictionary"""
        timestamp = datetime.now()
        event = AuditEvent(
            event_type=AuditEventType.COMMAND_EXECUTED,
            severity=AuditSeverity.INFO,
            message="Command executed",
            timestamp=timestamp,
            user_id="user123",
            details={"command": "test"}
        )

        event_dict = event.to_dict()

        assert event_dict['event_type'] == 'command_executed'
        assert event_dict['severity'] == 'info'
        assert event_dict['message'] == "Command executed"
        assert event_dict['timestamp'] == timestamp.isoformat()
        assert event_dict['user_id'] == "user123"
        assert '"command": "test"' in event_dict['details']


class TestAuditLogger:
    """Tests for AuditLogger class"""

    def test_database_initialization(self, audit_logger, temp_db):
        """Test that database is initialized with correct schema"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        # Check that table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'"
        )
        assert cursor.fetchone() is not None

        # Check indexes exist
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_event_type'"
        )
        assert cursor.fetchone() is not None

        conn.close()

    def test_log_event(self, audit_logger, temp_db):
        """Test logging an audit event"""
        event = AuditEvent(
            event_type=AuditEventType.AUTH_SUCCESS,
            severity=AuditSeverity.INFO,
            message="Test authentication",
            timestamp=datetime.now(),
            user_id="user123",
            ip_address="192.168.1.100"
        )

        audit_logger.log(event)

        # Verify event was logged
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_events")
        count = cursor.fetchone()[0]
        assert count == 1

        cursor.execute("SELECT * FROM audit_events")
        row = cursor.fetchone()
        assert row is not None
        conn.close()

    def test_log_auth_success(self, audit_logger, temp_db):
        """Test logging successful authentication"""
        audit_logger.log_auth_success(
            user_id="user123",
            device_id="device456",
            ip_address="192.168.1.100"
        )

        # Verify
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, user_id FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'auth_success'
        assert row[1] == 'user123'
        conn.close()

    def test_log_auth_failure(self, audit_logger, temp_db):
        """Test logging failed authentication"""
        audit_logger.log_auth_failure(
            user_id="user123",
            device_id="device456",
            ip_address="192.168.1.100",
            reason="Invalid password"
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, success FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'auth_failure'
        assert row[1] == 0  # False
        conn.close()

    def test_log_command_executed(self, audit_logger, temp_db):
        """Test logging command execution"""
        audit_logger.log_command_executed(
            command_id="cmd123",
            action_type="system_launch",
            user_id="user123",
            details={"app": "notepad.exe"}
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, command_id, action_type FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'command_executed'
        assert row[1] == 'cmd123'
        assert row[2] == 'system_launch'
        conn.close()

    def test_log_command_blocked(self, audit_logger, temp_db):
        """Test logging blocked command"""
        audit_logger.log_command_blocked(
            command_id="cmd123",
            action_type="file_delete",
            user_id="user123",
            reason="Protected directory"
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, success FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'command_blocked'
        assert row[1] == 0  # False
        conn.close()

    def test_log_file_delete_success(self, audit_logger, temp_db):
        """Test logging successful file deletion"""
        audit_logger.log_file_delete(
            file_path="C:/temp/test.txt",
            user_id="user123",
            success=True
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, severity, success FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'file_delete'
        assert row[1] == 'info'
        assert row[2] == 1  # True
        conn.close()

    def test_log_file_delete_failure(self, audit_logger, temp_db):
        """Test logging failed file deletion"""
        audit_logger.log_file_delete(
            file_path="C:/Windows/system32/important.dll",
            user_id="user123",
            success=False,
            error="Access denied"
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, severity, success FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'file_delete'
        assert row[1] == 'warning'
        assert row[2] == 0  # False
        conn.close()

    def test_log_rate_limit_exceeded(self, audit_logger, temp_db):
        """Test logging rate limit exceeded"""
        audit_logger.log_rate_limit_exceeded(
            user_id="user123",
            device_id="device456",
            ip_address="192.168.1.100"
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, severity FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'rate_limit_exceeded'
        assert row[1] == 'warning'
        conn.close()

    def test_log_suspicious_activity(self, audit_logger, temp_db):
        """Test logging suspicious activity"""
        audit_logger.log_suspicious_activity(
            description="Multiple failed login attempts",
            user_id="user123",
            ip_address="192.168.1.100",
            details={"attempts": 5}
        )

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, severity FROM audit_events")
        row = cursor.fetchone()
        assert row[0] == 'suspicious_activity'
        assert row[1] == 'error'
        conn.close()

    def test_query_events_by_type(self, audit_logger):
        """Test querying events by type"""
        # Log multiple events
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")
        audit_logger.log_auth_failure("user2", "device2", "192.168.1.2", "Bad password")
        audit_logger.log_auth_success("user3", "device3", "192.168.1.3")

        # Query
        events = audit_logger.query_events(event_type=AuditEventType.AUTH_SUCCESS)

        assert len(events) == 2
        assert all(e['event_type'] == 'auth_success' for e in events)

    def test_query_events_by_severity(self, audit_logger):
        """Test querying events by severity"""
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")
        audit_logger.log_suspicious_activity("Test", "user2", "192.168.1.2", {})

        events = audit_logger.query_events(severity=AuditSeverity.ERROR)

        assert len(events) == 1
        assert events[0]['severity'] == 'error'

    def test_query_events_by_user(self, audit_logger):
        """Test querying events by user ID"""
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")
        audit_logger.log_auth_success("user2", "device2", "192.168.1.2")
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")

        events = audit_logger.query_events(user_id="user1")

        assert len(events) == 2
        assert all(e['user_id'] == 'user1' for e in events)

    def test_query_events_by_time_range(self, audit_logger):
        """Test querying events by time range"""
        now = datetime.now()
        start_time = now - timedelta(hours=1)
        end_time = now + timedelta(hours=1)

        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")

        events = audit_logger.query_events(start_time=start_time, end_time=end_time)

        assert len(events) == 1

    def test_query_events_with_limit(self, audit_logger):
        """Test querying events with result limit"""
        for i in range(10):
            audit_logger.log_auth_success(f"user{i}", f"device{i}", "192.168.1.1")

        events = audit_logger.query_events(limit=5)

        assert len(events) == 5

    def test_get_failed_auth_attempts(self, audit_logger):
        """Test getting failed authentication attempts"""
        audit_logger.log_auth_failure("user1", "device1", "192.168.1.1", "Bad password")
        audit_logger.log_auth_success("user2", "device2", "192.168.1.2")
        audit_logger.log_auth_failure("user3", "device3", "192.168.1.3", "Invalid token")

        events = audit_logger.get_failed_auth_attempts(hours=24)

        assert len(events) == 2
        assert all(e['event_type'] == 'auth_failure' for e in events)

    def test_get_suspicious_activity(self, audit_logger):
        """Test getting suspicious activity"""
        audit_logger.log_suspicious_activity("Test 1", "user1", "192.168.1.1", {})
        audit_logger.log_auth_success("user2", "device2", "192.168.1.2")
        audit_logger.log_suspicious_activity("Test 2", "user3", "192.168.1.3", {})

        events = audit_logger.get_suspicious_activity(hours=24)

        assert len(events) == 2
        assert all(e['event_type'] == 'suspicious_activity' for e in events)

    def test_get_user_activity(self, audit_logger):
        """Test getting activity for specific user"""
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")
        audit_logger.log_command_executed("cmd1", "test", "user1", {})
        audit_logger.log_auth_success("user2", "device2", "192.168.1.2")

        events = audit_logger.get_user_activity("user1", days=7)

        assert len(events) == 2
        assert all(e['user_id'] == 'user1' for e in events)

    def test_cleanup_old_events(self, audit_logger, temp_db):
        """Test cleaning up old audit events"""
        # Create old and recent events
        old_time = datetime.now() - timedelta(days=100)
        recent_time = datetime.now()

        # Manually insert old event
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_events (event_type, severity, message, timestamp, success)
            VALUES (?, ?, ?, ?, ?)
        """, ('test', 'info', 'Old event', old_time.isoformat(), 1))
        conn.commit()
        conn.close()

        # Add recent event
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")

        # Cleanup events older than 90 days
        deleted_count = audit_logger.cleanup_old_events(retention_days=90)

        assert deleted_count == 1

        # Verify only recent event remains
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_events")
        count = cursor.fetchone()[0]
        assert count == 1
        conn.close()

    def test_get_statistics(self, audit_logger):
        """Test getting audit log statistics"""
        # Log various events
        audit_logger.log_auth_success("user1", "device1", "192.168.1.1")
        audit_logger.log_auth_failure("user2", "device2", "192.168.1.2", "Bad password")
        audit_logger.log_command_executed("cmd1", "test", "user1", {})
        audit_logger.log_suspicious_activity("Test", "user3", "192.168.1.3", {})

        stats = audit_logger.get_statistics()

        assert stats['total_events'] == 4
        assert len(stats['events_by_type']) > 0
        assert len(stats['events_by_severity']) > 0
        assert stats['recent_activity_24h'] == 4

    def test_get_audit_logger_singleton(self, temp_db):
        """Test global audit logger singleton"""
        logger1 = get_audit_logger(temp_db)
        logger2 = get_audit_logger(temp_db)

        assert logger1 is logger2


class TestAuditEventTypes:
    """Tests for AuditEventType enum"""

    def test_all_event_types_have_values(self):
        """Test that all event types have string values"""
        for event_type in AuditEventType:
            assert isinstance(event_type.value, str)
            assert len(event_type.value) > 0

    def test_event_types_are_unique(self):
        """Test that event type values are unique"""
        values = [event_type.value for event_type in AuditEventType]
        assert len(values) == len(set(values))


class TestAuditSeverity:
    """Tests for AuditSeverity enum"""

    def test_all_severities_have_values(self):
        """Test that all severities have string values"""
        for severity in AuditSeverity:
            assert isinstance(severity.value, str)
            assert len(severity.value) > 0

    def test_severities_are_unique(self):
        """Test that severity values are unique"""
        values = [severity.value for severity in AuditSeverity]
        assert len(values) == len(set(values))
