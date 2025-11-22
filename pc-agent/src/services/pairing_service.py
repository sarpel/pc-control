"""
Device pairing service for secure connection setup.

This service handles:
- Pairing initiation with 6-digit code generation
- Pairing verification and certificate exchange
- Device pairing status management
- Auth token generation and rotation
- Pairing revocation

Security constraints:
- Maximum 3 paired devices per PC
- 5-minute pairing code expiration
- 24-hour auth token expiration with rotation
- RSA 2048-bit minimum certificates
"""

import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, fields
import asyncio
import jwt

from src.models.device_pairing import DevicePairing, PairingStatus
from src.services.certificate_service import CertificateService
from src.services.audit_log_service import AuditLogService, AuditEvent, Severity
from src.database.connection import Database

logger = logging.getLogger(__name__)


@dataclass
class PairingSession:
    """Active pairing session data."""
    pairing_id: str
    device_name: str
    device_id: str
    pairing_code: str
    initiated_at: datetime
    expires_at: datetime


class PairingService:
    """
    Service for managing device pairing and secure connection setup.

    Implements the pairing flow:
    1. Android initiates pairing → receives 6-digit code
    2. User enters code on PC to verify
    3. Certificates and auth token are exchanged
    4. Device is paired and can connect via mTLS
    """

    # Configuration
    MAX_PAIRED_DEVICES = 3
    PAIRING_CODE_LENGTH = 6
    PAIRING_EXPIRATION_MINUTES = 5
    TOKEN_EXPIRATION_HOURS = 24

    # Active pairing sessions (shared across instances)
    _active_sessions: Dict[str, PairingSession] = {}

    def __init__(self, database: Database, certificate_service: CertificateService, audit_log_service: Optional[AuditLogService] = None):
        """
        Initialize pairing service.

        Args:
            database: Database connection for persistence
            certificate_service: Service for certificate generation
            audit_log_service: Service for audit logging (optional)
        """
        self.db = database
        self.cert_service = certificate_service
        self.audit_log = audit_log_service

        # Active pairing sessions (in-memory)
        self.active_sessions = self._active_sessions

        # JWT secret for auth tokens (should be loaded from secure config)
        self.jwt_secret = self._load_jwt_secret()

        logger.info("Pairing service initialized")

    def _load_jwt_secret(self) -> str:
        """Load JWT secret from secure storage."""
        try:
            import keyring
            service_name = "pc-control-agent"
            username = "jwt-secret"
            
            secret = keyring.get_password(service_name, username)
            if not secret:
                secret = secrets.token_urlsafe(32)
                keyring.set_password(service_name, username, secret)
            return secret
        except Exception as e:
            logger.warning(f"Failed to use keyring for JWT secret: {e}. Using temporary secret.")
            return secrets.token_urlsafe(32)

    async def initiate_pairing(
        self,
        device_name: str,
        device_id: str
    ) -> Dict[str, any]:
        """
        Initiate pairing process.

        Args:
            device_name: User-friendly device name
            device_id: Unique device identifier

        Returns:
            Dictionary with pairing_id, pairing_code, and expiration

        Raises:
            ValueError: If device already paired or max devices reached
        """
        # Check if device is already paired
        existing = await self._get_device_pairing(device_id)
        if existing and existing.status == PairingStatus.ACTIVE:
            raise ValueError(f"Device {device_id} is already paired")

        # Check maximum devices limit
        paired_count = await self._count_paired_devices()
        if paired_count >= self.MAX_PAIRED_DEVICES:
            raise ValueError(
                f"Maximum {self.MAX_PAIRED_DEVICES} devices limit reached. "
                f"Please revoke a device before pairing a new one."
            )

        # Generate pairing code and ID
        pairing_id = self._generate_pairing_id()
        pairing_code = self._generate_pairing_code()

        # Create session
        now = datetime.utcnow()
        session = PairingSession(
            pairing_id=pairing_id,
            device_name=device_name,
            device_id=device_id,
            pairing_code=pairing_code,
            initiated_at=now,
            expires_at=now + timedelta(minutes=self.PAIRING_EXPIRATION_MINUTES)
        )

        # Store session
        self.active_sessions[pairing_id] = session

        # Schedule cleanup
        asyncio.create_task(self._cleanup_expired_session(pairing_id))

        logger.info(
            f"Pairing initiated for device {device_id} ({device_name}): "
            f"code={pairing_code}, expires in {self.PAIRING_EXPIRATION_MINUTES} minutes"
        )

        if self.audit_log:
            await self.audit_log.log_event(
                event_type=AuditEvent.PAIRING_INITIATED,
                device_id=device_id,
                details={
                    "device_name": device_name,
                    "pairing_id": pairing_id
                },
                severity=Severity.INFO,
                security_related=True
            )

        return {
            "pairing_id": pairing_id,
            "pairing_code": pairing_code,
            "expires_in_seconds": self.PAIRING_EXPIRATION_MINUTES * 60
        }

    async def verify_pairing(
        self,
        pairing_id: str,
        pairing_code: str,
        device_id: str
    ) -> Dict[str, str]:
        """
        Verify pairing code and complete pairing.

        Args:
            pairing_id: Pairing session ID
            pairing_code: 6-digit code entered by user
            device_id: Device identifier for verification

        Returns:
            Dictionary with certificates and auth token

        Raises:
            ValueError: If pairing session not found or expired
            PermissionError: If pairing code is incorrect
        """
        # Get session
        session = self.active_sessions.get(pairing_id)
        if not session:
            raise ValueError("Pairing session not found or expired")

        # Check expiration
        if datetime.utcnow() > session.expires_at:
            del self.active_sessions[pairing_id]
            raise ValueError("Pairing session expired")

        # Verify device ID matches
        if session.device_id != device_id:
            raise PermissionError("Device ID mismatch")

        # Verify pairing code
        if session.pairing_code != pairing_code:
            logger.warning(
                f"Invalid pairing code for device {device_id}: "
                f"expected={session.pairing_code}, received={pairing_code}"
            )
            raise PermissionError("Invalid pairing code")

        # Generate certificates
        certificates = await self._generate_certificates(device_id)

        # Generate auth token
        auth_token = self._generate_auth_token(device_id)
        token_expires_at = datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRATION_HOURS)

        # Create device pairing record
        device_pairing = DevicePairing(
            device_id=device_id,
            pairing_id=pairing_id,
            pairing_code=pairing_code,
            device_name=session.device_name,
            ca_certificate=certificates["ca_certificate"],
            client_certificate=certificates["client_certificate"],
            # Private key is NOT stored on server (sent to device only)
            auth_token_hash=self._hash_token(auth_token),
            token_expires_at=token_expires_at,
            paired_at=datetime.utcnow(),
            status=PairingStatus.ACTIVE
        )

        # Save to database
        await self._save_device_pairing(device_pairing)

        # Clean up session
        del self.active_sessions[pairing_id]

        logger.info(f"Pairing completed for device {device_id} ({session.device_name})")

        if self.audit_log:
            await self.audit_log.log_event(
                event_type=AuditEvent.PAIRING_VERIFIED,
                device_id=device_id,
                details={
                    "device_name": session.device_name,
                    "pairing_id": pairing_id
                },
                severity=Severity.INFO,
                security_related=True
            )

        return {
            "ca_certificate": certificates["ca_certificate"],
            "client_certificate": certificates["client_certificate"],
            "client_private_key": certificates["client_private_key"],
            "auth_token": auth_token,
            "token_expires_at": token_expires_at.isoformat()
        }

    async def get_pairing_status(self, device_id: str) -> Dict[str, any]:
        """
        Get pairing status for a device.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary with pairing status information

        Raises:
            ValueError: If device not found
        """
        pairing = await self._get_device_pairing(device_id)
        if not pairing:
            raise ValueError(f"Device {device_id} not found")

        return {
            "status": pairing.status.value,
            "device_name": pairing.device_name,
            "device_id": pairing.device_id,
            "paired_at": pairing.paired_at.isoformat() if pairing.paired_at else None,
            "token_expires_at": pairing.token_expires_at.isoformat() if pairing.token_expires_at else None
        }

    async def revoke_pairing(self, device_id: str):
        """
        Revoke device pairing.

        Args:
            device_id: Device identifier

        Raises:
            ValueError: If device not found
        """
        pairing = await self._get_device_pairing(device_id)
        if not pairing:
            raise ValueError(f"Device {device_id} not found")

        # Update status to revoked
        pairing.status = PairingStatus.REVOKED

        # Update in database
        await self._update_device_pairing(pairing)

        logger.info(f"Pairing revoked for device {device_id}")

    async def rotate_auth_token(self, device_id: str) -> Dict[str, str]:
        """
        Rotate auth token before expiration.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary with new auth token and expiration

        Raises:
            ValueError: If device not found or not active
        """
        pairing = await self._get_device_pairing(device_id)
        if not pairing:
            raise ValueError(f"Device {device_id} not found")

        if pairing.status != PairingStatus.ACTIVE:
            raise ValueError(f"Device {device_id} is not active")

        # Generate new token
        new_token = self._generate_auth_token(device_id)
        new_expires_at = datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRATION_HOURS)

        # Update pairing
        pairing.auth_token_hash = self._hash_token(new_token)
        pairing.token_expires_at = new_expires_at

        # Update in database
        await self._update_device_pairing(pairing)

        logger.info(f"Auth token rotated for device {device_id}")

        return {
            "auth_token": new_token,
            "token_expires_at": new_expires_at.isoformat()
        }

    async def verify_auth_token(self, device_id: str, auth_token: str) -> bool:
        """
        Verify auth token for WebSocket authentication.

        Args:
            device_id: Device identifier
            auth_token: Auth token to verify

        Returns:
            True if valid, False otherwise
        """
        pairing = await self._get_device_pairing(device_id)
        if not pairing:
            logger.warning(f"Auth verification failed: device {device_id} not found")
            return False

        if pairing.status != PairingStatus.ACTIVE:
            logger.warning(f"Auth verification failed: device {device_id} not active")
            return False

        # Check token expiration
        if datetime.utcnow() > pairing.token_expires_at:
            logger.warning(f"Auth verification failed: token expired for device {device_id}")
            return False

        # Verify token hash
        token_hash = self._hash_token(auth_token)
        if token_hash != pairing.auth_token_hash:
            logger.warning(f"Auth verification failed: invalid token for device {device_id}")
            return False

        return True

    def _generate_pairing_id(self) -> str:
        """Generate unique pairing session ID."""
        return f"pair_{secrets.token_urlsafe(16)}"

    def _generate_pairing_code(self) -> str:
        """Generate 6-digit pairing code."""
        return ''.join(secrets.choice(string.digits) for _ in range(self.PAIRING_CODE_LENGTH))

    def _generate_auth_token(self, device_id: str) -> str:
        """
        Generate JWT auth token.

        Args:
            device_id: Device identifier

        Returns:
            JWT token string
        """
        payload = {
            "device_id": device_id,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=self.TOKEN_EXPIRATION_HOURS)
        }

        return jwt.encode(payload, self.jwt_secret, algorithm="HS256")

    def _hash_token(self, token: str) -> str:
        """
        Hash auth token for storage.

        Args:
            token: Token to hash

        Returns:
            Hashed token (SHA-256)
        """
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()

    async def _generate_certificates(self, device_id: str) -> Dict[str, str]:
        """
        Generate certificates for device.

        Args:
            device_id: Device identifier

        Returns:
            Dictionary with CA cert, client cert, and private key (PEM format)
        """
        # Use certificate service to generate
        certificates = await self.cert_service.generate_client_certificate(
            common_name=f"pccontrol-{device_id}",
            device_id=device_id
        )

        return certificates

    async def _get_device_pairing(self, device_id: str) -> Optional[DevicePairing]:
        """Get device pairing from database."""
        # Query database
        query = "SELECT * FROM device_pairing WHERE device_id = ?"
        row = await self.db.fetch_one(query, (device_id,))

        if not row:
            return None

        # Filter row data to match DevicePairing fields
        data = dict(row)
        valid_fields = {f.name for f in fields(DevicePairing)}
        filtered_data = {k: v for k, v in data.items() if k in valid_fields}
        
        # Convert status string to Enum if needed
        if 'status' in filtered_data and isinstance(filtered_data['status'], str):
            try:
                filtered_data['status'] = PairingStatus(filtered_data['status'])
            except ValueError:
                pass

        # Convert datetime strings to datetime objects
        for date_field in ['created_at', 'completed_at', 'token_expires_at', 'paired_at', 'expires_at']:
            if date_field in filtered_data and isinstance(filtered_data[date_field], str):
                try:
                    filtered_data[date_field] = datetime.fromisoformat(filtered_data[date_field])
                except ValueError:
                    pass

        return DevicePairing(**filtered_data)

    async def _save_device_pairing(self, pairing: DevicePairing):
        """Save device pairing to database."""
        query = """
            INSERT INTO device_pairing (
                device_id, pairing_id, pairing_code, device_name, ca_certificate, client_certificate,
                auth_token_hash, token_expires_at, paired_at, status, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.utcnow()
        values = (
            pairing.device_id,
            pairing.pairing_id,
            pairing.pairing_code,
            pairing.device_name,
            pairing.ca_certificate,
            pairing.client_certificate,
            pairing.auth_token_hash,
            pairing.token_expires_at,
            pairing.paired_at,
            pairing.status.value,
            now,
            now + timedelta(minutes=10) # expires_at is required by schema
        )

        await self.db.execute(query, values)

    async def _update_device_pairing(self, pairing: DevicePairing):
        """Update device pairing in database."""
        query = """
            UPDATE device_pairing
            SET status = ?, auth_token_hash = ?, token_expires_at = ?
            WHERE device_id = ?
        """
        values = (
            pairing.status.value,
            pairing.auth_token_hash,
            pairing.token_expires_at,
            pairing.device_id
        )

        await self.db.execute(query, values)

    async def _count_paired_devices(self) -> int:
        """Count currently paired devices."""
        query = "SELECT COUNT(*) as count FROM device_pairing WHERE status = ?"
        row = await self.db.fetch_one(query, (PairingStatus.ACTIVE.value,))
        return row['count'] if row else 0

    async def _cleanup_expired_session(self, pairing_id: str):
        """Clean up expired pairing session."""
        await asyncio.sleep(self.PAIRING_EXPIRATION_MINUTES * 60)

        if pairing_id in self.active_sessions:
            session = self.active_sessions[pairing_id]
            del self.active_sessions[pairing_id]
            logger.info(
                f"Pairing session expired and cleaned up: {pairing_id} "
                f"(device: {session.device_id})"
            )
