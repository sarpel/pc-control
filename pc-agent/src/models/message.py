"""
WebSocket Message models for serialization/deserialization.

This module provides message models for WebSocket communication between
Android client and PC server.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
import json
import uuid


class MessageType(Enum):
    """WebSocket message types."""
    # Connection management
    CONNECTION_REQUEST = "connection_request"
    CONNECTION_RESPONSE = "connection_response"
    HEARTBEAT = "heartbeat"
    HEARTBEAT_ACK = "heartbeat_ack"
    DISCONNECT = "disconnect"

    # Voice command flow
    VOICE_COMMAND_START = "voice_command_start"
    AUDIO_CHUNK = "audio_chunk"
    VOICE_COMMAND_END = "voice_command_end"
    TRANSCRIPTION_RESULT = "transcription_result"
    COMMAND_INTERPRETED = "command_interpreted"

    # Action execution
    ACTION_START = "action_start"
    ACTION_PROGRESS = "action_progress"
    ACTION_COMPLETE = "action_complete"
    ACTION_FAILED = "action_failed"
    ACTION_REQUIRES_CONFIRMATION = "action_requires_confirmation"

    # Status and feedback
    STATUS_UPDATE = "status_update"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


@dataclass
class WebSocketMessage:
    """
    Base WebSocket message model.

    Attributes:
        message_id: Unique message identifier
        message_type: Type of message
        timestamp: When message was created
        data: Message payload (type-specific)
        correlation_id: Optional ID to correlate related messages
    """
    message_id: str
    message_type: MessageType
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None

    def to_json(self) -> str:
        """Serialize message to JSON string."""
        return json.dumps({
            "message_id": self.message_id,
            "message_type": self.message_type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "correlation_id": self.correlation_id
        })

    @classmethod
    def from_json(cls, json_str: str) -> "WebSocketMessage":
        """Deserialize message from JSON string."""
        data = json.loads(json_str)
        return cls(
            message_id=data["message_id"],
            message_type=MessageType(data["message_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            data=data["data"],
            correlation_id=data.get("correlation_id")
        )

    @classmethod
    def create(
        cls,
        message_type: MessageType,
        data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> "WebSocketMessage":
        """Factory method to create a new message."""
        return cls(
            message_id=str(uuid.uuid4()),
            message_type=message_type,
            timestamp=datetime.utcnow(),
            data=data,
            correlation_id=correlation_id
        )


@dataclass
class ConnectionRequestMessage:
    """Connection request message from Android client."""
    authentication_token: str
    device_id: str
    device_name: str
    app_version: str
    protocol_version: str = "1.0"

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.CONNECTION_REQUEST,
            data={
                "authentication_token": self.authentication_token,
                "device_id": self.device_id,
                "device_name": self.device_name,
                "app_version": self.app_version,
                "protocol_version": self.protocol_version
            }
        )

    @classmethod
    def from_websocket_message(cls, msg: WebSocketMessage) -> "ConnectionRequestMessage":
        """Create from WebSocket message."""
        return cls(**msg.data)


@dataclass
class ConnectionResponseMessage:
    """Connection response message from PC server."""
    accepted: bool
    session_id: str
    pc_name: str
    server_version: str
    protocol_version: str = "1.0"
    reason: Optional[str] = None
    capabilities: List[str] = field(default_factory=list)

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.CONNECTION_RESPONSE,
            data={
                "accepted": self.accepted,
                "session_id": self.session_id,
                "pc_name": self.pc_name,
                "server_version": self.server_version,
                "protocol_version": self.protocol_version,
                "reason": self.reason,
                "capabilities": self.capabilities
            }
        )


@dataclass
class AudioChunkMessage:
    """Audio chunk message for streaming."""
    command_id: str
    chunk_index: int
    audio_data: bytes  # Base64-encoded in JSON
    is_final: bool = False
    encoding: str = "opus"
    sample_rate: int = 16000

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        import base64
        return WebSocketMessage.create(
            message_type=MessageType.AUDIO_CHUNK,
            data={
                "command_id": self.command_id,
                "chunk_index": self.chunk_index,
                "audio_data": base64.b64encode(self.audio_data).decode('utf-8'),
                "is_final": self.is_final,
                "encoding": self.encoding,
                "sample_rate": self.sample_rate
            }
        )

    @classmethod
    def from_websocket_message(cls, msg: WebSocketMessage) -> "AudioChunkMessage":
        """Create from WebSocket message."""
        import base64
        data = msg.data.copy()
        data["audio_data"] = base64.b64decode(data["audio_data"])
        return cls(**data)


@dataclass
class TranscriptionResultMessage:
    """Transcription result message."""
    command_id: str
    transcription: str
    confidence: float
    language: str
    duration_ms: int

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.TRANSCRIPTION_RESULT,
            data={
                "command_id": self.command_id,
                "transcription": self.transcription,
                "confidence": self.confidence,
                "language": self.language,
                "duration_ms": self.duration_ms
            }
        )


@dataclass
class ActionProgressMessage:
    """Action execution progress message."""
    action_id: str
    command_id: str
    action_type: str
    progress_percentage: int
    status_message: str

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.ACTION_PROGRESS,
            data={
                "action_id": self.action_id,
                "command_id": self.command_id,
                "action_type": self.action_type,
                "progress_percentage": self.progress_percentage,
                "status_message": self.status_message
            }
        )


@dataclass
class ErrorMessage:
    """Error message."""
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.ERROR,
            data={
                "error_code": self.error_code,
                "error_message": self.error_message,
                "error_details": self.error_details
            },
            correlation_id=self.correlation_id
        )


@dataclass
class StatusUpdateMessage:
    """Status update message in Turkish."""
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_websocket_message(self) -> WebSocketMessage:
        """Convert to WebSocket message."""
        return WebSocketMessage.create(
            message_type=MessageType.STATUS_UPDATE,
            data={
                "status": self.status,
                "message": self.message,
                "details": self.details
            }
        )


# Message factory helpers

def create_connection_request(
    auth_token: str,
    device_id: str,
    device_name: str,
    app_version: str
) -> WebSocketMessage:
    """Create a connection request message."""
    return ConnectionRequestMessage(
        authentication_token=auth_token,
        device_id=device_id,
        device_name=device_name,
        app_version=app_version
    ).to_websocket_message()


def create_connection_response(
    accepted: bool,
    session_id: str,
    pc_name: str,
    server_version: str,
    reason: Optional[str] = None
) -> WebSocketMessage:
    """Create a connection response message."""
    return ConnectionResponseMessage(
        accepted=accepted,
        session_id=session_id,
        pc_name=pc_name,
        server_version=server_version,
        reason=reason
    ).to_websocket_message()


def create_error_message(
    error_code: str,
    error_message: str,
    correlation_id: Optional[str] = None
) -> WebSocketMessage:
    """Create an error message."""
    return ErrorMessage(
        error_code=error_code,
        error_message=error_message,
        correlation_id=correlation_id
    ).to_websocket_message()


def create_status_update(status: str, message: str) -> WebSocketMessage:
    """Create a status update message."""
    return StatusUpdateMessage(
        status=status,
        message=message
    ).to_websocket_message()
