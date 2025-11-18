"""
Command History data model.

Represents recent commands for context awareness (retained for 10 minutes or 5 commands).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
import uuid

from .voice_command import VoiceCommand
from .action import Action, ActionStatus


@dataclass
class CommandHistory:
    """
    Command history model for tracking recent commands.

    Attributes:
        history_id: Unique identifier (UUID v4)
        command_id: Foreign key to VoiceCommand
        transcription: Command text for quick reference
        action_summary: Brief description of actions taken
        success: Whether all actions completed successfully
        timestamp: Timestamp when command was executed
        expires_at: Timestamp when this history entry expires (10 minutes from creation)
    """
    history_id: str
    command_id: str
    transcription: str
    action_summary: str
    success: bool
    timestamp: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        """Validate command history data after initialization."""
        # Validate history_id format
        try:
            uuid.UUID(self.history_id)
        except ValueError as e:
            raise ValueError(f"Invalid history_id format: {e}")

        # Validate command_id format
        try:
            uuid.UUID(self.command_id)
        except ValueError as e:
            raise ValueError(f"Invalid command_id format: {e}")

        # Validate expires_at is after timestamp
        if self.expires_at <= self.timestamp:
            raise ValueError("expires_at must be after timestamp")

    @classmethod
    def create(cls, command: VoiceCommand, actions: List[Action]) -> "CommandHistory":
        """
        Factory method to create CommandHistory from VoiceCommand and Actions.

        Args:
            command: The voice command that was executed
            actions: List of actions taken for this command

        Returns:
            New CommandHistory instance
        """
        action_summary = cls._generate_summary(actions)
        success = all(action.status == ActionStatus.COMPLETED for action in actions)
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        return cls(
            history_id=str(uuid.uuid4()),
            command_id=command.command_id,
            transcription=command.transcription,
            action_summary=action_summary,
            success=success,
            timestamp=command.timestamp,
            expires_at=expires_at
        )

    @staticmethod
    def _generate_summary(actions: List[Action]) -> str:
        """
        Generate a brief summary of actions taken.

        Args:
            actions: List of actions

        Returns:
            Human-readable summary string in Turkish
        """
        if not actions:
            return "Hiçbir işlem yapılmadı"

        action_descriptions = []
        for action in actions:
            if action.action_type.value.startswith("system_"):
                if "launch" in action.action_type.value:
                    app_name = action.parameters.get("application_name", "uygulama")
                    action_descriptions.append(f"{app_name} açıldı")
                elif "volume" in action.action_type.value:
                    level = action.parameters.get("level", "bilinmeyen")
                    action_descriptions.append(f"Ses seviyesi {level}% olarak ayarlandı")
                elif "find" in action.action_type.value:
                    pattern = action.parameters.get("pattern", "dosya")
                    action_descriptions.append(f"'{pattern}' arandı")
                elif "info" in action.action_type.value:
                    action_descriptions.append("Sistem bilgisi gösterildi")
                elif "delete" in action.action_type.value:
                    file_path = action.parameters.get("file_path", "dosya")
                    action_descriptions.append(f"'{file_path}' silindi")

            elif action.action_type.value.startswith("browser_"):
                if "navigate" in action.action_type.value:
                    url = action.parameters.get("url", "site")
                    action_descriptions.append(f"'{url}' açıldı")
                elif "search" in action.action_type.value:
                    query = action.parameters.get("query", "arama")
                    action_descriptions.append(f"'{query}' arandı")
                elif "extract" in action.action_type.value:
                    action_descriptions.append("Sayfa içeriği çıkartıldı")

        if not action_descriptions:
            return f"{len(actions)} işlem gerçekleştirildi"

        return ", ".join(action_descriptions[:3])  # Limit to first 3 actions

    def is_expired(self) -> bool:
        """
        Check if this history entry has expired.

        Returns:
            True if entry has expired (past expires_at time)
        """
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> dict:
        """Convert command history to dictionary representation."""
        return {
            "history_id": self.history_id,
            "command_id": self.command_id,
            "transcription": self.transcription,
            "action_summary": self.action_summary,
            "success": self.success,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_expired": self.is_expired(),
        }
