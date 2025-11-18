"""
Wake-on-LAN (WoL) Service

Handles Wake-on-LAN functionality for waking sleeping PCs:
- Generate and send WoL magic packets
- Retry logic with exponential backoff
- PC status checking and health monitoring
- Error handling and logging

Following requirements from spec and test T042.
"""

import socket
import struct
import re
import asyncio
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class WoLResult:
    """Result of a Wake-on-LAN operation."""
    success: bool
    message: str
    sent_at: float
    retry_count: int = 0
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None


@dataclass
class PCStatusResult:
    """Result of PC status check."""
    pc_status: str  # "online", "offline", "waking"
    ip_address: str
    last_checked: float
    latency_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class WoLHealthResult:
    """Result of WoL service health check."""
    service_status: str  # "healthy", "degraded", "unhealthy"
    timestamp: float
    version: str
    capabilities: Dict[str, Any]


class WakeOnLANService:
    """
    Wake-on-LAN service implementation.

    Features:
    - WoL magic packet generation and transmission
    - Configurable retry logic (max 3 retries)
    - PC status monitoring via ping
    - Health check endpoint
    - Comprehensive error handling with Turkish messages
    """

    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds
        self.default_port = 9  # Standard WoL port
        self.packet_size = 102  # Standard WoL magic packet size
        self.version = "1.0.0"

    def validate_mac_address(self, mac_address: str) -> bool:
        """
        Validate MAC address format.

        Args:
            mac_address: MAC address in format "AA:BB:CC:DD:EE:FF"

        Returns:
            True if valid, False otherwise
        """
        # Standard MAC address regex
        mac_pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
        return re.match(mac_pattern, mac_address) is not None

    def validate_ip_address(self, ip_address: str) -> bool:
        """
        Validate IPv4 address format.

        Args:
            ip_address: IPv4 address

        Returns:
            True if valid, False otherwise
        """
        try:
            socket.inet_aton(ip_address)
            return True
        except socket.error:
            return False

    def generate_magic_packet(self, mac_address: str) -> bytes:
        """
        Generate WoL magic packet for given MAC address.

        Args:
            mac_address: MAC address in format "AA:BB:CC:DD:EE:FF"

        Returns:
            Magic packet bytes

        Raises:
            ValueError: If MAC address is invalid
        """
        if not self.validate_mac_address(mac_address):
            raise ValueError(f"Geçersiz MAC adresi: {mac_address}")

        # Remove separators and convert to bytes
        mac_clean = mac_address.replace(':', '').replace('-', '')
        mac_bytes = bytes.fromhex(mac_clean)

        # Create magic packet: 6 bytes of FF + MAC repeated 16 times
        magic_packet = b'\xff' * 6 + mac_bytes * 16

        if len(magic_packet) != self.packet_size:
            raise ValueError("Beklenmeyen paket boyutu")

        return magic_packet

    async def send_wol_packet(
        self,
        mac_address: str,
        ip_address: str,
        broadcast_address: Optional[str] = None,
        port: Optional[int] = None
    ) -> WoLResult:
        """
        Send Wake-on-LAN magic packet with retry logic.

        Args:
            mac_address: Target MAC address
            ip_address: Target IP address
            broadcast_address: Broadcast address (defaults to IP with .255)
            port: UDP port (defaults to 9)

        Returns:
            WoLResult with operation details
        """
        start_time = time.time()

        # Validate inputs
        if not self.validate_mac_address(mac_address):
            return WoLResult(
                success=False,
                message="Geçersiz MAC adresi formatı",
                sent_at=start_time,
                error="MAC adresi AA:BB:CC:DD:EE:FF formatında olmalıdır"
            )

        if not self.validate_ip_address(ip_address):
            return WoLResult(
                success=False,
                message="Geçersiz IP adresi formatı",
                sent_at=start_time,
                error="IP adresi geçerli bir IPv4 formatı olmalıdır"
            )

        # Set defaults
        if broadcast_address is None:
            # Calculate broadcast address (last octet = 255)
            ip_parts = ip_address.split('.')
            broadcast_address = '.'.join(ip_parts[:3] + ['255'])

        if port is None:
            port = self.default_port

        # Generate magic packet
        try:
            magic_packet = self.generate_magic_packet(mac_address)
        except ValueError as e:
            return WoLResult(
                success=False,
                message=f"WoL paketi oluşturulamadı: {str(e)}",
                sent_at=start_time,
                error=str(e)
            )

        # Send with retry logic
        last_error = None
        for retry_count in range(self.max_retries + 1):  # Include initial attempt
            try:
                success = await self._send_packet_udp(
                    magic_packet, broadcast_address, port
                )

                if success:
                    execution_time = (time.time() - start_time) * 1000
                    logger.info(f"WoL packet sent successfully to {mac_address} via {broadcast_address}:{port}")

                    return WoLResult(
                        success=True,
                        message="PC uyandırma paketi başarıyla gönderildi",
                        sent_at=start_time,
                        retry_count=retry_count,
                        execution_time_ms=execution_time
                    )

            except Exception as e:
                last_error = e
                logger.warning(f"WoL attempt {retry_count + 1} failed: {str(e)}")

                # Don't wait after the last attempt
                if retry_count < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** retry_count))  # Exponential backoff

        # All attempts failed
        execution_time = (time.time() - start_time) * 1000
        error_message = f"WoL paketi gönderilemedi: {str(last_error)}" if last_error else "WoL paketi gönderilemedi"

        return WoLResult(
            success=False,
            message=error_message,
            sent_at=start_time,
            retry_count=self.max_retries,
            error=str(last_error) if last_error else "Bilinmeyen hata",
            execution_time_ms=execution_time
        )

    async def _send_packet_udp(
        self, packet: bytes, address: str, port: int
    ) -> bool:
        """
        Send UDP packet to specified address and port.

        Args:
            packet: Packet bytes to send
            address: Target address
            port: Target port

        Returns:
            True if successful, False otherwise

        Raises:
            OSError: If there are permission issues or socket errors
        """
        try:
            # Create UDP socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # Set socket options for broadcasting
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(5.0)  # 5 second timeout

                # Send the packet
                bytes_sent = sock.sendto(packet, (address, port))

                if bytes_sent == len(packet):
                    return True
                else:
                    raise socket.error(f"Tüm paket gönderilemedi: {bytes_sent}/{len(packet)} bytes")

        except OSError as e:
            if "Permission denied" in str(e):
                raise OSError("WoL paketi göndermek için ağ izni gerekiyor. Yönetici olarak çalıştırın.")
            else:
                raise OSError(f"Ağ hatası: {str(e)}")
        except socket.error as e:
            raise socket.error(f"Socket hatası: {str(e)}")
        except Exception as e:
            raise Exception(f"Beklenmeyen hata: {str(e)}")

    async def check_pc_status(self, ip_address: str, timeout: float = 3.0) -> PCStatusResult:
        """
        Check if PC is online, offline, or waking up.

        Args:
            ip_address: PC IP address
            timeout: Ping timeout in seconds

        Returns:
            PCStatusResult with status information
        """
        start_time = time.time()

        if not self.validate_ip_address(ip_address):
            return PCStatusResult(
                pc_status="offline",
                ip_address=ip_address,
                last_checked=start_time,
                error="Geçersiz IP adresi formatı"
            )

        try:
            # Attempt to ping the PC
            latency = await self._ping_pc(ip_address, timeout)

            if latency is not None:
                status = "online"
                message = f"PC çevrimiçi ({latency:.1f}ms gecikme)"
            else:
                status = "offline"
                message = "PC çevrimdışı"
                latency = None

        except Exception as e:
            logger.warning(f"PC status check failed for {ip_address}: {str(e)}")
            status = "offline"
            message = f"Durum kontrolü başarısız: {str(e)}"
            latency = None

        return PCStatusResult(
            pc_status=status,
            ip_address=ip_address,
            last_checked=time.time(),
            latency_ms=latency
        )

    async def _ping_pc(self, ip_address: str, timeout: float) -> Optional[float]:
        """
        Ping PC to measure latency.

        Args:
            ip_address: PC IP address
            timeout: Timeout in seconds

        Returns:
            Latency in milliseconds, or None if unreachable
        """
        try:
            # Create a simple TCP connection test to port 80 (commonly open)
            start_ping = time.time()

            # Try connecting to common Windows ports
            test_ports = [80, 443, 135, 445]  # HTTP, HTTPS, RPC, SMB

            for port in test_ports:
                try:
                    future = asyncio.open_connection(ip_address, port)
                    reader, writer = await asyncio.wait_for(future, timeout=timeout)

                    # Connection successful
                    latency = (time.time() - start_ping) * 1000

                    # Clean up
                    writer.close()
                    await writer.wait_closed()

                    return latency

                except (ConnectionRefusedError, OSError, asyncio.TimeoutError):
                    continue  # Try next port

            # No port responded
            return None

        except Exception as e:
            logger.debug(f"Ping test failed: {str(e)}")
            return None

    async def get_service_health(self) -> WoLHealthResult:
        """
        Get WoL service health status.

        Returns:
            WoLHealthResult with service information
        """
        # Check service capabilities
        capabilities = {
            "wol_enabled": True,
            "max_retries": self.max_retries,
            "supported_ports": [7, 9],  # Standard WoL ports
            "packet_size": self.packet_size,
            "encryption": None,  # WoL doesn't use encryption
            "auth_required": False
        }

        # Determine service status based on system permissions
        try:
            # Test if we can create a socket (basic connectivity test)
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.close()

            service_status = "healthy"

        except OSError as e:
            if "Permission denied" in str(e):
                service_status = "degraded"
                capabilities["restriction"] = "requires_admin"
            else:
                service_status = "unhealthy"
            logger.warning(f"Service health check failed: {str(e)}")

        except Exception as e:
            service_status = "unhealthy"
            logger.error(f"Unexpected service health error: {str(e)}")

        return WoLHealthResult(
            service_status=service_status,
            timestamp=time.time(),
            version=self.version,
            capabilities=capabilities
        )

    async def send_multiple_wol_packets(
        self,
        mac_address: str,
        ip_addresses: List[str],
        broadcast_addresses: Optional[List[str]] = None
    ) -> List[WoLResult]:
        """
        Send WoL packets to multiple IP addresses (useful for multi-homed PCs).

        Args:
            mac_address: Target MAC address
            ip_addresses: List of target IP addresses
            broadcast_addresses: Optional list of broadcast addresses

        Returns:
            List of WoLResult for each address
        """
        if broadcast_addresses is None:
            broadcast_addresses = []

        tasks = []
        for i, ip in enumerate(ip_addresses):
            broadcast = broadcast_addresses[i] if i < len(broadcast_addresses) else None
            task = self.send_wol_packet(mac_address, ip, broadcast)
            tasks.append(task)

        # Execute concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failure results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(WoLResult(
                    success=False,
                    message=f"WoL paketi gönderilemedi: {str(result)}",
                    sent_at=time.time(),
                    error=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results


# Global service instance
wol_service = WakeOnLANService()