"""
Connection manager for handling concurrent WebSocket connections.

This service manages active connections, enforces single connection
policy, and provides connection queuing functionality.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque
import json

logger = logging.getLogger(__name__)


@dataclass
class ConnectionInfo:
    """Information about an active connection."""
    device_id: str
    device_name: str
    connection_id: str
    connected_at: datetime
    last_heartbeat: datetime
    ip_address: str
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    certificate_fingerprint: Optional[str] = None


@dataclass
class QueuedConnection:
    """Information about a queued connection request."""
    device_id: str
    device_name: str
    queued_at: datetime
    ip_address: str
    request_id: str


class ConnectionManager:
    """
    Manages WebSocket connections and enforces connection policies.

    This class handles:
    - Active connection tracking
    - Single connection enforcement per device
    - Connection queuing with priority
    - Connection health monitoring
    - Automatic cleanup of stale connections
    """

    def __init__(self, max_connections: int = 1, connection_timeout: int = 300):
        """
        Initialize connection manager.

        Args:
            max_connections: Maximum concurrent connections allowed
            connection_timeout: Timeout in seconds for idle connections
        """
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout

        # Active connections (device_id -> ConnectionInfo)
        self.active_connections: Dict[str, ConnectionInfo] = {}

        # Connection queue (deque of QueuedConnection)
        self.connection_queue: deque[QueuedConnection] = deque()

        # WebSocket instances (device_id -> WebSocket)
        self.websockets: Dict[str, Any] = {}

        # Statistics
        self.total_connections_served = 0
        self.connection_rejections = 0

        # Cleanup task (started lazily)
        self._cleanup_task = None
        self._cleanup_started = False

    async def initialize(self):
        """Initialize the connection manager and start background tasks."""
        self._start_cleanup_task()
        logger.info("Connection manager initialized")

    def _start_cleanup_task(self):
        """Start the background cleanup task if event loop is running."""
        if self._cleanup_task is None and not self._cleanup_started:
            try:
                loop = asyncio.get_running_loop()
                self._cleanup_task = asyncio.create_task(self._cleanup_stale_connections())
                self._cleanup_started = True
            except RuntimeError:
                # No event loop running, will start later
                pass

    async def _cleanup_stale_connections(self):
        """Background task to cleanup stale connections."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")

    async def _cleanup_idle_connections(self):
        """Remove idle connections."""
        current_time = datetime.utcnow()
        stale_devices = []

        for device_id, connection_info in self.active_connections.items():
            idle_time = (current_time - connection_info.last_heartbeat).total_seconds()
            if idle_time > self.connection_timeout:
                stale_devices.append(device_id)
                logger.warning(f"Device {device_id} connection timed out after {idle_time:.1f}s")

        # Remove stale connections
        for device_id in stale_devices:
            await self.force_disconnect(device_id, "Connection timeout")

    def register_connection(self, device_id: str, device_info: Dict[str, Any]) -> bool:
        """
        Register a new connection.

        Args:
            device_id: Unique device identifier
            device_info: Device information from certificate

        Returns:
            True if registration successful, False if connection limit reached
        """
        # Start cleanup task if not already started
        self._start_cleanup_task()
        
        # Check if device already has active connection
        if device_id in self.active_connections:
            logger.warning(f"Device {device_id} already has active connection")
            return False

        # Check connection limit
        if len(self.active_connections) >= self.max_connections:
            logger.info(f"Connection limit ({self.max_connections}) reached")
            return False

        # Create connection info
        connection_info = ConnectionInfo(
            device_id=device_id,
            device_name=device_info.get("device_name", "Unknown Device"),
            connection_id=f"conn_{datetime.utcnow().timestamp()}",
            connected_at=datetime.utcnow(),
            last_heartbeat=datetime.utcnow(),
            ip_address=device_info.get("ip_address", "unknown"),
            user_agent=device_info.get("user_agent"),
            certificate_fingerprint=device_info.get("certificate_fingerprint")
        )

        # Register connection
        self.active_connections[device_id] = connection_info
        self.total_connections_served += 1

        logger.info(f"Connection registered: {device_id} ({connection_info.device_name})")

        # Process queue if there are waiting connections
        self._process_queue()

        return True

    def unregister_connection(self, device_id: str) -> bool:
        """
        Unregister a connection.

        Args:
            device_id: Device identifier to unregister

        Returns:
            True if connection was found and removed
        """
        if device_id not in self.active_connections:
            logger.warning(f"Attempted to unregister unknown connection: {device_id}")
            return False

        connection_info = self.active_connections[device_id]
        del self.active_connections[device_id]

        # Remove websocket if exists
        if device_id in self.websockets:
            websocket = self.websockets.pop(device_id)
            logger.debug(f"WebSocket removed for device: {device_id}")

        logger.info(f"Connection unregistered: {device_id} ({connection_info.device_name})")

        # Process queue to allow waiting connections
        self._process_queue()

        return True

    async def force_disconnect(self, device_id: str, reason: str = "Administrative disconnect"):
        """
        Force disconnect a device.

        Args:
            device_id: Device identifier to disconnect
            reason: Reason for disconnection
        """
        if device_id in self.websockets:
            websocket = self.websockets[device_id]
            try:
                await websocket.send_json({
                    "type": "connection_closed",
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat()
                })
                await websocket.close(code=1001, reason=reason)
            except Exception as e:
                logger.error(f"Error closing websocket for {device_id}: {e}")

        self.unregister_connection(device_id)

    def add_to_queue(self, device_info: Dict[str, Any]) -> int:
        """
        Add device to connection queue.

        Args:
            device_info: Device information

        Returns:
            Queue position (1-based)
        """
        device_id = device_info.get("device_id")
        if not device_id:
            raise ValueError("Device ID is required")

        # Check if already in queue
        for queued in self.connection_queue:
            if queued.device_id == device_id:
                logger.warning(f"Device {device_id} already in queue")
                return self._get_queue_position(device_id)

        queued_connection = QueuedConnection(
            device_id=device_id,
            device_name=device_info.get("device_name", "Unknown Device"),
            queued_at=datetime.utcnow(),
            ip_address=device_info.get("ip_address", "unknown"),
            request_id=f"req_{datetime.utcnow().timestamp()}"
        )

        self.connection_queue.append(queued_connection)
        queue_position = len(self.connection_queue)

        logger.info(f"Device {device_id} added to queue at position {queue_position}")

        return queue_position

    def get_queue_position(self, device_id: str) -> Optional[int]:
        """
        Get queue position for a device.

        Args:
            device_id: Device identifier

        Returns:
            Queue position (1-based) or None if not in queue
        """
        for i, queued in enumerate(self.connection_queue, 1):
            if queued.device_id == device_id:
                return i
        return None

    def _get_queue_position(self, device_id: str) -> Optional[int]:
        """Internal method to get queue position."""
        return self.get_queue_position(device_id)

    def _process_queue(self):
        """Process connection queue and allow next device to connect."""
        if len(self.active_connections) >= self.max_connections:
            return  # Still at capacity

        if not self.connection_queue:
            return  # No devices waiting

        # Get next device from queue
        queued_connection = self.connection_queue.popleft()
        logger.info(f"Allowing queued device {queued_connection.device_id} to connect")

        # In a real implementation, this would notify the waiting device
        # For now, we just log that a slot is available

    def has_active_connection(self, device_id: str) -> bool:
        """
        Check if device has active connection.

        Args:
            device_id: Device identifier

        Returns:
            True if device has active connection
        """
        return device_id in self.active_connections

    def get_active_connection_count(self) -> int:
        """
        Get current number of active connections.

        Returns:
            Number of active connections
        """
        return len(self.active_connections)

    def get_queue_length(self) -> int:
        """
        Get current queue length.

        Returns:
            Number of devices waiting in queue
        """
        return len(self.connection_queue)

    def get_connection_info(self, device_id: str) -> Optional[ConnectionInfo]:
        """
        Get connection information for a device.

        Args:
            device_id: Device identifier

        Returns:
            Connection info or None if not connected
        """
        return self.active_connections.get(device_id)

    def get_all_connections(self) -> List[ConnectionInfo]:
        """
        Get all active connections.

        Returns:
            List of all active connection info
        """
        return list(self.active_connections.values())

    def update_heartbeat(self, device_id: str) -> bool:
        """
        Update heartbeat timestamp for a connection.

        Args:
            device_id: Device identifier

        Returns:
            True if connection found and updated
        """
        if device_id in self.active_connections:
            self.active_connections[device_id].last_heartbeat = datetime.utcnow()
            return True
        return False

    def register_websocket(self, device_id: str, websocket: Any) -> bool:
        """
        Register WebSocket instance for a device.

        Args:
            device_id: Device identifier
            websocket: WebSocket instance

        Returns:
            True if registration successful
        """
        if device_id not in self.active_connections:
            logger.warning(f"Attempted to register websocket for unknown device: {device_id}")
            return False

        self.websockets[device_id] = websocket
        logger.debug(f"WebSocket registered for device: {device_id}")
        return True

    def get_websocket(self, device_id: str) -> Optional[Any]:
        """
        Get WebSocket instance for a device.

        Args:
            device_id: Device identifier

        Returns:
            WebSocket instance or None if not found
        """
        return self.websockets.get(device_id)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get connection manager statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "active_connections": len(self.active_connections),
            "max_connections": self.max_connections,
            "queue_length": len(self.connection_queue),
            "total_connections_served": self.total_connections_served,
            "connection_rejections": self.connection_rejections,
            "uptime": datetime.utcnow().isoformat() if hasattr(self, '_start_time') else None
        }

    async def shutdown(self):
        """Gracefully shutdown connection manager."""
        logger.info("Shutting down connection manager")

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all websockets
        for device_id, websocket in list(self.websockets.items()):
            try:
                await websocket.close(code=1001, reason="Server shutdown")
            except Exception as e:
                logger.error(f"Error closing websocket for {device_id}: {e}")

        # Clear all data
        self.active_connections.clear()
        self.websockets.clear()
        self.connection_queue.clear()

        logger.info("Connection manager shutdown complete")

    def __del__(self):
        """Cleanup when object is destroyed."""
        if hasattr(self, '_cleanup_task') and self._cleanup_task:
            self._cleanup_task.cancel()