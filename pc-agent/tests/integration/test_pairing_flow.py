"""
Integration tests for complete device pairing flow.

Tests the end-to-end pairing process:
1. Android initiates pairing
2. User enters 6-digit code on PC
3. Certificates are exchanged
4. mTLS connection is established
5. WebSocket auth succeeds

Following TDD: These tests should FAIL initially, then pass after implementation.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock, patch
from datetime import datetime, timedelta


class TestPairingFlowIntegration:
    """Integration tests for complete pairing workflow."""

    @pytest.mark.asyncio
    async def test_complete_pairing_flow_success(
        self,
        pairing_service,
        certificate_service,
        temp_cert_dir
    ):
        """
        Test: Complete successful pairing flow from initiation to mTLS connection
        Expected to FAIL until T033 is implemented
        """
        # Arrange
        device_name = "Samsung Galaxy S21"
        device_id = "android_samsung_001"

        # Act - Step 1: Initiate pairing
        pairing_session = await pairing_service.initiate_pairing(
            device_name=device_name,
            device_id=device_id
        )

        assert pairing_session is not None
        assert len(pairing_session["pairing_code"]) == 6
        assert pairing_session["pairing_id"] is not None

        # Act - Step 2: Verify pairing code (simulating user entering code)
        verification_result = await pairing_service.verify_pairing(
            pairing_id=pairing_session["pairing_id"],
            pairing_code=pairing_session["pairing_code"],
            device_id=device_id
        )

        assert verification_result is not None
        assert "ca_certificate" in verification_result
        assert "client_certificate" in verification_result
        assert "client_private_key" in verification_result
        assert "auth_token" in verification_result

        # Act - Step 3: Verify certificates are valid PEM format
        ca_cert = verification_result["ca_certificate"]
        client_cert = verification_result["client_certificate"]
        client_key = verification_result["client_private_key"]

        assert "-----BEGIN CERTIFICATE-----" in ca_cert
        assert "-----END CERTIFICATE-----" in ca_cert
        assert "-----BEGIN CERTIFICATE-----" in client_cert
        assert "-----END CERTIFICATE-----" in client_cert
        assert "-----BEGIN PRIVATE KEY-----" in client_key
        assert "-----END PRIVATE KEY-----" in client_key

        # Act - Step 4: Verify pairing is persisted in database
        pairing_status = await pairing_service.get_pairing_status(device_id)

        assert pairing_status["status"] == "active"
        assert pairing_status["device_name"] == device_name
        assert pairing_status["device_id"] == device_id

    @pytest.mark.asyncio
    async def test_pairing_flow_with_incorrect_code_fails(
        self,
        pairing_service
    ):
        """
        Test: Pairing fails when incorrect code is provided
        Expected to FAIL until T033 is implemented
        """
        # Arrange
        device_name = "Test Device"
        device_id = "android_test_002"

        # Act - Step 1: Initiate pairing
        pairing_session = await pairing_service.initiate_pairing(
            device_name=device_name,
            device_id=device_id
        )

        # Act - Step 2: Verify with WRONG code
        with pytest.raises(Exception) as exc_info:
            await pairing_service.verify_pairing(
                pairing_id=pairing_session["pairing_id"],
                pairing_code="000000",  # Wrong code
                device_id=device_id
            )

        # Assert
        assert "invalid" in str(exc_info.value).lower() or "incorrect" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_pairing_flow_expires_after_timeout(
        self,
        pairing_service,
        freezer  # pytest-freezegun for time mocking
    ):
        """
        Test: Pairing session expires after 5 minutes
        Expected to FAIL until T033 is implemented
        """
        # Arrange
        device_name = "Test Device"
        device_id = "android_test_003"

        # Act - Step 1: Initiate pairing
        pairing_session = await pairing_service.initiate_pairing(
            device_name=device_name,
            device_id=device_id
        )

        # Act - Step 2: Simulate 6 minutes passing
        freezer.move_to("+ 6m")

        # Act - Step 3: Try to verify (should fail due to expiration)
        with pytest.raises(Exception) as exc_info:
            await pairing_service.verify_pairing(
                pairing_id=pairing_session["pairing_id"],
                pairing_code=pairing_session["pairing_code"],
                device_id=device_id
            )

        # Assert
        assert "expired" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_pairing_flow_certificate_rotation(
        self,
        pairing_service,
        certificate_service,
        freezer
    ):
        """
        Test: Auth tokens are rotated before 24-hour expiration
        Expected to FAIL until T041 is implemented
        """
        # Arrange - Complete initial pairing
        device_id = "android_test_004"
        pairing_session = await pairing_service.initiate_pairing(
            device_name="Test Device",
            device_id=device_id
        )

        verification_result = await pairing_service.verify_pairing(
            pairing_id=pairing_session["pairing_id"],
            pairing_code=pairing_session["pairing_code"],
            device_id=device_id
        )

        original_token = verification_result["auth_token"]

        # Act - Simulate 23 hours passing (before expiration)
        freezer.move_to("+ 23h")

        # Request token rotation
        rotated_result = await pairing_service.rotate_auth_token(device_id)

        # Assert
        assert rotated_result["auth_token"] != original_token
        assert rotated_result["token_expires_at"] > verification_result["token_expires_at"]

    @pytest.mark.asyncio
    async def test_pairing_flow_revocation_prevents_connection(
        self,
        pairing_service,
        websocket_server
    ):
        """
        Test: Revoked pairing prevents WebSocket connection
        Expected to FAIL until T037 is implemented
        """
        # Arrange - Complete pairing
        device_id = "android_test_005"
        pairing_session = await pairing_service.initiate_pairing(
            device_name="Test Device",
            device_id=device_id
        )

        verification_result = await pairing_service.verify_pairing(
            pairing_id=pairing_session["pairing_id"],
            pairing_code=pairing_session["pairing_code"],
            device_id=device_id
        )

        # Act - Revoke pairing
        await pairing_service.revoke_pairing(device_id)

        # Act - Try to connect with revoked credentials
        with pytest.raises(Exception) as exc_info:
            await websocket_server.authenticate_connection(
                auth_token=verification_result["auth_token"],
                device_id=device_id
            )

        # Assert
        assert "revoked" in str(exc_info.value).lower() or "unauthorized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_pairing_flow_concurrent_pairings(
        self,
        pairing_service
    ):
        """
        Test: Multiple concurrent pairing sessions work independently
        Expected to FAIL until T040 is implemented
        """
        # Arrange
        devices = [
            ("Device 1", "device_1"),
            ("Device 2", "device_2"),
            ("Device 3", "device_3")
        ]

        # Act - Initiate multiple pairings concurrently
        pairing_sessions = await asyncio.gather(*[
            pairing_service.initiate_pairing(name, device_id)
            for name, device_id in devices
        ])

        # Assert - All sessions should be unique
        pairing_ids = [session["pairing_id"] for session in pairing_sessions]
        pairing_codes = [session["pairing_code"] for session in pairing_sessions]

        assert len(set(pairing_ids)) == 3  # All unique
        assert len(set(pairing_codes)) == 3  # All unique

        # Act - Verify all pairings independently
        verifications = await asyncio.gather(*[
            pairing_service.verify_pairing(
                pairing_id=session["pairing_id"],
                pairing_code=session["pairing_code"],
                device_id=device_id
            )
            for session, (_, device_id) in zip(pairing_sessions, devices)
        ])

        # Assert - All verifications should succeed
        assert len(verifications) == 3
        for verification in verifications:
            assert "auth_token" in verification
            assert "ca_certificate" in verification

    @pytest.mark.asyncio
    async def test_pairing_flow_audit_logging(
        self,
        pairing_service,
        audit_log
    ):
        """
        Test: Pairing attempts are logged for security audit
        Expected to FAIL until T041 is implemented
        """
        # Arrange
        device_id = "android_test_006"

        # Act - Complete pairing flow
        pairing_session = await pairing_service.initiate_pairing(
            device_name="Test Device",
            device_id=device_id
        )

        await pairing_service.verify_pairing(
            pairing_id=pairing_session["pairing_id"],
            pairing_code=pairing_session["pairing_code"],
            device_id=device_id
        )

        # Act - Retrieve audit logs
        logs = await audit_log.get_logs_for_device(device_id)

        # Assert - Verify audit entries exist
        assert len(logs) >= 2  # At least initiate and verify

        initiate_log = next((log for log in logs if log["event"] == "pairing_initiated"), None)
        verify_log = next((log for log in logs if log["event"] == "pairing_verified"), None)

        assert initiate_log is not None
        assert verify_log is not None
        assert initiate_log["device_id"] == device_id
        assert verify_log["device_id"] == device_id


# Fixtures

@pytest.fixture
async def test_db(test_settings):
    """
    Fixture providing a fresh database connection for each test.
    """
    from src.database import connection
    
    # Reset global connection to ensure we get a new one
    connection._db_connection = None
    
    # Patch get_settings to return our test settings (with temp DB path)
    with patch('src.database.connection.get_settings', return_value=test_settings):
        db = connection.get_database_connection()
        await db.initialize()
        yield db
        await db.close()
        connection._db_connection = None


@pytest.fixture
async def pairing_service(test_db, certificate_service):
    """
    Fixture providing pairing service instance.
    """
    from src.services.pairing_service import PairingService
    service = PairingService(test_db, certificate_service)
    yield service


@pytest.fixture
async def certificate_service(temp_cert_dir):
    """
    Fixture providing certificate service instance.
    """
    from src.services.certificate_service import CertificateService

    service = CertificateService(cert_dir=temp_cert_dir)
    yield service


@pytest.fixture
def temp_cert_dir():
    """
    Fixture providing temporary directory for certificates.
    """
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
async def websocket_server():
    """
    Fixture providing WebSocket server instance for testing.
    """
    # Mock WebSocketServer since it's not exported or doesn't exist as a class
    server = Mock()
    server.active_connections = {}
    yield server


@pytest.fixture
async def audit_log(test_db):
    """
    Fixture providing audit log interface.
    """
    from src.services.audit_log_service import AuditLogService
    audit_service = AuditLogService(test_db)
    yield audit_service


@pytest.fixture
def freezer():
    """
    Fixture providing time freezing capability (pytest-freezegun).
    Install with: pip install pytest-freezegun
    """
    pytest.importorskip("freezegun")
    from freezegun import freeze_time

    with freeze_time() as frozen_time:
        yield frozen_time
