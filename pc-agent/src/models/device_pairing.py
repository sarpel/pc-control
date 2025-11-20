"""
Device Pairing data model.

Represents the one-time security setup between Android phone and PC.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
import re


class PairingStatus(Enum):
    """Status of device pairing process."""
    INITIATED = "initiated"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass
class DevicePairing:
    """
    Device pairing model representing security setup between devices.

    Attributes:
        device_id: Unique device identifier
        status: Current pairing status
        pairing_id: Unique identifier (UUID v4)
        device_name: Human-readable device name
        pairing_code: 6-digit numeric code for verification
        created_at: Timestamp when pairing was initiated
        
        # Optional fields
        pc_fingerprint: PC certificate fingerprint (SHA-256)
        android_fingerprint: Android certificate fingerprint (SHA-256)
        completed_at: Timestamp when pairing was completed
        pc_name: Human-readable PC name
        pc_ip_address: IPv4 address of PC
        
        # Certificate and Auth fields
        ca_certificate: CA certificate PEM
        client_certificate: Client certificate PEM
        auth_token_hash: Hashed auth token
        token_expires_at: Token expiration timestamp
        paired_at: Timestamp when pairing was completed/active
    """
    device_id: str
    status: PairingStatus
    pairing_id: Optional[str] = None
    device_name: Optional[str] = None
    pairing_code: Optional[str] = None
    created_at: Optional[datetime] = None
    
    pc_fingerprint: Optional[str] = None
    android_fingerprint: Optional[str] = None
    completed_at: Optional[datetime] = None
    pc_name: Optional[str] = None
    pc_ip_address: Optional[str] = None
    
    ca_certificate: Optional[str] = None
    client_certificate: Optional[str] = None
    auth_token_hash: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    paired_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate device pairing data after initialization."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
            
        # Validate pairing_id format if present
        if self.pairing_id:
            try:
                # Check if it's a UUID or our custom format "pair_..."
                if not self.pairing_id.startswith("pair_"):
                    uuid.UUID(self.pairing_id)
            except ValueError:
                # Allow custom format
                pass

        # Validate pairing code format (6-digit numeric) if present
        if self.pairing_code and not re.match(r'^\d{6}$', self.pairing_code):
            raise ValueError("Pairing code must be a 6-digit numeric string")

        # Validate fingerprints if present
        if self.pc_fingerprint and not re.match(r'^[a-fA-F0-9]{64}$', self.pc_fingerprint):
            raise ValueError("PC fingerprint must be a 64-character hex string (SHA-256)")
        if self.android_fingerprint and not re.match(r'^[a-fA-F0-9]{64}$', self.android_fingerprint):
            raise ValueError("Android fingerprint must be a 64-character hex string (SHA-256)")

    @classmethod
    def create(
        cls,
        device_id: str,
        pairing_code: str,
        pc_fingerprint: Optional[str] = None,
        android_fingerprint: Optional[str] = None,
        pc_name: Optional[str] = None,
        pc_ip_address: Optional[str] = None
    ) -> "DevicePairing":
        """
        Factory method to create a new DevicePairing.
        """
        return cls(
            device_id=device_id,
            pairing_code=pairing_code,
            pairing_id=str(uuid.uuid4()),
            status=PairingStatus.INITIATED,
            created_at=datetime.utcnow(),
            pc_fingerprint=pc_fingerprint,
            android_fingerprint=android_fingerprint,
            pc_name=pc_name,
            pc_ip_address=pc_ip_address
        )

    def await_confirmation(self) -> None:
        """Mark pairing as awaiting user confirmation."""
        if self.status == PairingStatus.INITIATED:
            self.status = PairingStatus.AWAITING_CONFIRMATION
        else:
            raise ValueError(f"Cannot await confirmation from status: {self.status}")

    def complete(self) -> None:
        """Mark pairing as successfully completed."""
        if self.status == PairingStatus.AWAITING_CONFIRMATION:
            self.status = PairingStatus.COMPLETED
            self.completed_at = datetime.utcnow()
        else:
            raise ValueError(f"Cannot complete pairing from status: {self.status}")

    def fail(self, reason: str = "Pairing failed") -> None:
        """
        Mark pairing as failed.

        Args:
            reason: Reason for failure
        """
        self.status = PairingStatus.FAILED
        # In a real implementation, you might want to log the reason

    def is_expired(self) -> bool:
        """
        Check if pairing has expired (10 minutes timeout).

        Returns:
            True if pairing has expired
        """
        if self.status in (PairingStatus.COMPLETED, PairingStatus.EXPIRED, PairingStatus.FAILED):
            return self.status == PairingStatus.EXPIRED

        time_elapsed = (datetime.utcnow() - self.created_at).total_seconds()
        if time_elapsed > 600:  # 10 minutes
            self.status = PairingStatus.EXPIRED
            return True
        return False

    def verify_code(self, code: str) -> bool:
        """
        Verify the provided pairing code matches.

        Args:
            code: 6-digit code to verify

        Returns:
            True if code matches and pairing not expired
        """
        if self.is_expired():
            return False
        return self.pairing_code == code

    def to_dict(self) -> dict:
        """Convert device pairing to dictionary representation."""
        return {
            "pairing_id": self.pairing_id,
            "android_device_id": self.android_device_id,
            "pc_fingerprint": self.pc_fingerprint,
            "android_fingerprint": self.android_fingerprint,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "pc_name": self.pc_name,
            "pc_ip_address": self.pc_ip_address,
            "is_expired": self.is_expired(),
        }
