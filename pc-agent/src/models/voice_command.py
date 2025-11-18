"""
Voice Command data model.

Represents a user's spoken instruction in Turkish with embedded English technical terms.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class CommandStatus(Enum):
    """Status of a voice command."""
    PENDING = "pending"
    PROCESSING = "processing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VoiceCommand:
    """
    Voice command model representing user's spoken instruction.

    Attributes:
        command_id: Unique identifier (UUID v4)
        audio_data: Opus-encoded audio chunks
        transcription: Turkish text with English technical terms
        confidence: STT confidence score (0.0-1.0)
        timestamp: UTC timestamp when command was received
        duration_ms: Audio length in milliseconds
        language: Primary language (default: "tr")
        status: Current processing status of the command
    """
    command_id: str
    audio_data: bytes
    transcription: str
    confidence: float
    timestamp: datetime
    duration_ms: int
    language: str = "tr"
    status: CommandStatus = CommandStatus.PENDING

    def __post_init__(self) -> None:
        """Validate voice command data after initialization."""
        # Validate command_id format
        try:
            uuid.UUID(self.command_id)
        except ValueError as e:
            raise ValueError(f"Invalid command_id format: {e}")

        # Validate audio_data size (max 10MB)
        if len(self.audio_data) > 10 * 1024 * 1024:
            raise ValueError("Audio data exceeds 10MB limit")

        # Validate transcription length (max 1000 characters)
        if len(self.transcription) > 1000:
            raise ValueError("Transcription exceeds 1000 character limit")

        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        # Validate duration range (100ms to 30s)
        if not 100 <= self.duration_ms <= 30000:
            raise ValueError("Duration must be between 100ms and 30000ms")

    @classmethod
    def create(
        cls,
        audio_data: bytes,
        transcription: str,
        confidence: float,
        duration_ms: int,
        language: str = "tr"
    ) -> "VoiceCommand":
        """
        Factory method to create a new VoiceCommand.

        Args:
            audio_data: Opus-encoded audio data
            transcription: Transcribed text
            confidence: STT confidence score
            duration_ms: Audio duration in milliseconds
            language: Language code (default: "tr")

        Returns:
            New VoiceCommand instance
        """
        return cls(
            command_id=str(uuid.uuid4()),
            audio_data=audio_data,
            transcription=transcription,
            confidence=confidence,
            timestamp=datetime.utcnow(),
            duration_ms=duration_ms,
            language=language,
            status=CommandStatus.PENDING
        )

    def to_dict(self) -> dict:
        """Convert voice command to dictionary representation."""
        return {
            "command_id": self.command_id,
            "transcription": self.transcription,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "language": self.language,
            "status": self.status.value,
        }
