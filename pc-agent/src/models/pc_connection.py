"""
PC Connection data model.

Represents the network connection state between Android phone and PC.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid
import re


class ConnectionStatus(Enum):
    """Status of PC connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class PCConnection:
    """
    PC connection model representing network connection state.

    Attributes:
        connection_id: Unique identifier (UUID v4)
        pc_ip_address: IPv4 address of the PC
        pc_mac_address: MAC address for Wake-on-LAN
        pc_name: Human-readable PC name
        status: Current connection status
        latency_ms: Network latency in milliseconds (optional)
        last_heartbeat: Timestamp of last heartbeat (optional)
        authentication_token: JWT token for authentication (optional)
        certificate_fingerprint: SHA-256 fingerprint of PC certificate (optional)
    """
    connection_id: str
    pc_ip_address: str
    pc_mac_address: str
    pc_name: str
    status: ConnectionStatus
    latency_ms: Optional[int] = None
    last_heartbeat: Optional[datetime] = None
    authentication_token: Optional[str] = None
    certificate_fingerprint: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate PC connection data after initialization."""
        # Validate connection_id format
        try:
            uuid.UUID(self.connection_id)
        except ValueError as e:
            raise ValueError(f"Invalid connection_id format: {e}")

        # Validate IPv4 address format
        ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(ipv4_pattern, self.pc_ip_address):
            raise ValueError("Invalid IPv4 address format")

        # Validate MAC address format (colon-separated)
        mac_pattern = r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$'
        if not re.match(mac_pattern, self.pc_mac_address):
            raise ValueError("Invalid MAC address format (expected XX:XX:XX:XX:XX:XX)")

        # Validate PC name length
        if not 1 <= len(self.pc_name) <= 50:
            raise ValueError("PC name must be between 1 and 50 characters")

        # Validate latency range if present
        if self.latency_ms is not None and not 1 <= self.latency_ms <= 10000:
            raise ValueError("Latency must be between 1 and 10000 ms")

    @classmethod
    def create(
        cls,
        pc_ip_address: str,
        pc_mac_address: str,
        pc_name: str,
        status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    ) -> "PCConnection":
        """
        Factory method to create a new PCConnection.

        Args:
            pc_ip_address: IPv4 address
            pc_mac_address: MAC address
            pc_name: Human-readable name
            status: Initial status (default: DISCONNECTED)

        Returns:
            New PCConnection instance
        """
        return cls(
            connection_id=str(uuid.uuid4()),
            pc_ip_address=pc_ip_address,
            pc_mac_address=pc_mac_address,
            pc_name=pc_name,
            status=status
        )

    def update_heartbeat(self, latency_ms: int) -> None:
        """
        Update connection heartbeat with current timestamp and latency.

        Args:
            latency_ms: Network latency in milliseconds
        """
        self.last_heartbeat = datetime.utcnow()
        self.latency_ms = latency_ms

    def authenticate(self, token: str, fingerprint: str) -> None:
        """
        Mark connection as authenticated with token and certificate fingerprint.

        Args:
            token: JWT authentication token
            fingerprint: Certificate fingerprint
        """
        self.authentication_token = token
        self.certificate_fingerprint = fingerprint
        self.status = ConnectionStatus.AUTHENTICATED

    def disconnect(self) -> None:
        """Mark connection as disconnected and clear authentication."""
        self.status = ConnectionStatus.DISCONNECTED
        self.authentication_token = None
        self.last_heartbeat = None

    def to_dict(self) -> dict:
        """Convert PC connection to dictionary representation."""
        return {
            "connection_id": self.connection_id,
            "pc_ip_address": self.pc_ip_address,
            "pc_mac_address": self.pc_mac_address,
            "pc_name": self.pc_name,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "has_token": self.authentication_token is not None,
            "certificate_fingerprint": self.certificate_fingerprint,
        }
