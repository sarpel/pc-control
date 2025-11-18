"""
Command history tracking service for context awareness.

Maintains recent command history for LLM context (FR-016):
- Maximum 5 commands (FIFO queue)
- 10-minute retention
- Turkish action summaries
- Automatic cleanup

Task: T079 - User Story 3
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class ExecutionResult(Enum):
    """Command execution results."""
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class CommandHistoryEntry:
    """Single command history entry."""
    command_text: str
    action_summary: str  # Turkish description
    execution_result: ExecutionResult
    timestamp: datetime
    retention_expires_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "command_text": self.command_text,
            "action_summary": self.action_summary,
            "execution_result": self.execution_result.value,
            "timestamp": self.timestamp.isoformat(),
            "retention_expires_at": self.retention_expires_at.isoformat(),
            "metadata": self.metadata
        }

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return datetime.now() >= self.retention_expires_at


class CommandHistoryService:
    """
    Service for tracking command history with context awareness.

    Features:
    - FIFO queue (max 5 entries)
    - 10-minute retention per entry
    - Turkish action summaries
    - Automatic cleanup of expired entries
    - Context generation for LLM
    """

    def __init__(self, max_entries: int = 5, retention_minutes: int = 10):
        self.max_entries = max_entries
        self.retention_minutes = retention_minutes
        self.history: deque[CommandHistoryEntry] = deque(maxlen=max_entries)

    def add_command(
        self,
        command_text: str,
        action_summary: str,
        execution_result: ExecutionResult,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a command to history.

        Args:
            command_text: The transcribed voice command
            action_summary: Turkish description of the action
            execution_result: Result of execution
            metadata: Optional additional metadata
        """
        now = datetime.now()
        expires_at = now + timedelta(minutes=self.retention_minutes)

        entry = CommandHistoryEntry(
            command_text=command_text,
            action_summary=action_summary,
            execution_result=execution_result,
            timestamp=now,
            retention_expires_at=expires_at,
            metadata=metadata or {}
        )

        # Clean up expired entries before adding
        self._cleanup_expired()

        # Add to history (deque automatically enforces max_entries)
        self.history.append(entry)

        logger.info(f"Added command to history: {action_summary} ({execution_result.value})")

    def get_recent_commands(self, max_count: Optional[int] = None) -> List[CommandHistoryEntry]:
        """
        Get recent commands (most recent first).

        Args:
            max_count: Maximum number of commands to return (default: all)

        Returns:
            List of command history entries
        """
        self._cleanup_expired()

        # Return most recent first
        recent = list(reversed(self.history))

        if max_count is not None:
            recent = recent[:max_count]

        return recent

    def get_context_for_llm(self) -> str:
        """
        Generate context string for LLM from recent commands.

        Returns:
            Formatted context string in Turkish
        """
        self._cleanup_expired()

        if not self.history:
            return "İlk komut (No previous commands)"

        context_lines = ["Son komutlar (Recent commands):"]

        for i, entry in enumerate(reversed(self.history), 1):
            time_ago = self._format_time_ago(entry.timestamp)
            result_icon = "✓" if entry.execution_result == ExecutionResult.SUCCESS else "✗"

            context_lines.append(
                f"{i}. {result_icon} {entry.action_summary} ({time_ago})"
            )

        return "\n".join(context_lines)

    def get_last_successful_command(self) -> Optional[CommandHistoryEntry]:
        """Get the most recent successful command."""
        self._cleanup_expired()

        for entry in reversed(self.history):
            if entry.execution_result == ExecutionResult.SUCCESS:
                return entry

        return None

    def clear_history(self) -> None:
        """Clear all command history."""
        self.history.clear()
        logger.info("Command history cleared")

    def get_statistics(self) -> Dict[str, Any]:
        """Get command history statistics."""
        self._cleanup_expired()

        if not self.history:
            return {
                "total_commands": 0,
                "success_count": 0,
                "failed_count": 0,
                "cancelled_count": 0,
                "success_rate": 0.0
            }

        total = len(self.history)
        success_count = sum(1 for e in self.history if e.execution_result == ExecutionResult.SUCCESS)
        failed_count = sum(1 for e in self.history if e.execution_result == ExecutionResult.FAILED)
        cancelled_count = sum(1 for e in self.history if e.execution_result == ExecutionResult.CANCELLED)

        return {
            "total_commands": total,
            "success_count": success_count,
            "failed_count": failed_count,
            "cancelled_count": cancelled_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0.0
        }

    def _cleanup_expired(self) -> None:
        """Remove expired entries from history."""
        # Filter out expired entries
        self.history = deque(
            (entry for entry in self.history if not entry.is_expired()),
            maxlen=self.max_entries
        )

    def _format_time_ago(self, timestamp: datetime) -> str:
        """Format time difference in Turkish."""
        now = datetime.now()
        diff = now - timestamp

        if diff.total_seconds() < 60:
            return "şimdi"  # now
        elif diff.total_seconds() < 3600:
            minutes = int(diff.total_seconds() / 60)
            return f"{minutes} dakika önce"  # minutes ago
        else:
            hours = int(diff.total_seconds() / 3600)
            return f"{hours} saat önce"  # hours ago

    def to_dict(self) -> Dict[str, Any]:
        """Export history to dictionary."""
        return {
            "max_entries": self.max_entries,
            "retention_minutes": self.retention_minutes,
            "current_count": len(self.history),
            "history": [entry.to_dict() for entry in self.history]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandHistoryService":
        """Create service from dictionary."""
        service = cls(
            max_entries=data.get("max_entries", 5),
            retention_minutes=data.get("retention_minutes", 10)
        )

        # Restore history entries
        for entry_data in data.get("history", []):
            entry = CommandHistoryEntry(
                command_text=entry_data["command_text"],
                action_summary=entry_data["action_summary"],
                execution_result=ExecutionResult(entry_data["execution_result"]),
                timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                retention_expires_at=datetime.fromisoformat(entry_data["retention_expires_at"]),
                metadata=entry_data.get("metadata", {})
            )
            service.history.append(entry)

        return service
