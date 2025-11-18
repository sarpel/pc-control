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


@dataclass
class DevicePairing:
    """
    Device pairing model representing security setup between devices.

    Attributes:
        pairing_id: Unique identifier (UUID v4)
        android_device_id: Unique Android device identifier
        pc_fingerprint: PC certificate fingerprint (SHA-256)
        android_fingerprint: Android certificate fingerprint (SHA-256)
        pairing_code: 6-digit numeric code for verification
        status: Current pairing status
        created_at: Timestamp when pairing was initiated
        completed_at: Timestamp when pairing was completed (optional)
        pc_name: Human-readable PC name (optional)
        pc_ip_address: IPv4 address of PC (optional)
    """
    pairing_id: str
    android_device_id: str
    pc_fingerprint: str
    android_fingerprint: str
    pairing_code: str
    status: PairingStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    pc_name: Optional[str] = None
    pc_ip_address: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate device pairing data after initialization."""
        # Validate pairing_id format
        try:
            uuid.UUID(self.pairing_id)
        except ValueError as e:
            raise ValueError(f"Invalid pairing_id format: {e}")

        # Validate pairing code format (6-digit numeric)
        if not re.match(r'^\d{6}$', self.pairing_code):
            raise ValueError("Pairing code must be a 6-digit numeric string")

        # Validate fingerprints (SHA-256 hash format - 64 hex characters)
        if not re.match(r'^[a-fA-F0-9]{64}$', self.pc_fingerprint):
            raise ValueError("PC fingerprint must be a 64-character hex string (SHA-256)")
        if not re.match(r'^[a-fA-F0-9]{64}$', self.android_fingerprint):
            raise ValueError("Android fingerprint must be a 64-character hex string (SHA-256)")

        # Check if pairing has expired (10 minutes)
        if self.status not in (PairingStatus.COMPLETED, PairingStatus.EXPIRED, PairingStatus.FAILED):
            time_elapsed = (datetime.utcnow() - self.created_at).total_seconds()
            if time_elapsed > 600:  # 10 minutes
                self.status = PairingStatus.EXPIRED

    @classmethod
    def create(
        cls,
        android_device_id: str,
        pc_fingerprint: str,
        android_fingerprint: str,
        pairing_code: str,
        pc_name: Optional[str] = None,
        pc_ip_address: Optional[str] = None
    ) -> "DevicePairing":
        """
        Factory method to create a new DevicePairing.

        Args:
            android_device_id: Android device identifier
            pc_fingerprint: PC certificate fingerprint
            android_fingerprint: Android certificate fingerprint
            pairing_code: 6-digit verification code
            pc_name: PC name (optional)
            pc_ip_address: PC IP address (optional)

        Returns:
            New DevicePairing instance
        """
        return cls(
            pairing_id=str(uuid.uuid4()),
            android_device_id=android_device_id,
            pc_fingerprint=pc_fingerprint,
            android_fingerprint=android_fingerprint,
            pairing_code=pairing_code,
            status=PairingStatus.INITIATED,
            created_at=datetime.utcnow(),
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
