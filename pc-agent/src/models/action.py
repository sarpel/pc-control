"""
Action data model.

Represents an operation to be performed on the PC.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
import uuid


class ActionType(Enum):
    """Type of action to be performed."""
    SYSTEM_LAUNCH = "system_launch"
    SYSTEM_VOLUME = "system_volume"
    SYSTEM_FILE_FIND = "system_file_find"
    SYSTEM_INFO = "system_info"
    SYSTEM_FILE_DELETE = "system_file_delete"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_SEARCH = "browser_search"
    BROWSER_EXTRACT = "browser_extract"
    BROWSER_INTERACT = "browser_interact"


class ActionStatus(Enum):
    """Status of action execution."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REQUIRES_CONFIRMATION = "requires_confirmation"


class ActionResult(Enum):
    """Result of action execution."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    INVALID_PARAMETERS = "invalid_parameters"


@dataclass
class Action:
    """
    Action model representing an operation to be performed.

    Attributes:
        action_id: Unique identifier (UUID v4)
        command_id: Foreign key to VoiceCommand
        action_type: Type of action to perform
        parameters: Action-specific parameters (dictionary)
        status: Current execution status
        result: Execution result (optional)
        error_message: Error details if failed (optional)
        execution_time_ms: Time taken to execute in milliseconds (optional)
        created_at: Timestamp when action was created
    """
    action_id: str
    command_id: str
    action_type: ActionType
    parameters: Dict[str, Any]
    status: ActionStatus
    result: Optional[ActionResult] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Validate action data after initialization."""
        # Validate action_id format
        try:
            uuid.UUID(self.action_id)
        except ValueError as e:
            raise ValueError(f"Invalid action_id format: {e}")

        # Validate command_id format
        try:
            uuid.UUID(self.command_id)
        except ValueError as e:
            raise ValueError(f"Invalid command_id format: {e}")

        # Validate execution time range if present
        if self.execution_time_ms is not None and not 1 <= self.execution_time_ms <= 60000:
            raise ValueError("Execution time must be between 1 and 60000 ms")

        # Validate parameters based on action type
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Validate parameters based on action type."""
        if self.action_type == ActionType.SYSTEM_LAUNCH:
            if "application_name" not in self.parameters:
                raise ValueError("SYSTEM_LAUNCH requires 'application_name' parameter")

        elif self.action_type == ActionType.SYSTEM_VOLUME:
            if "level" not in self.parameters:
                raise ValueError("SYSTEM_VOLUME requires 'level' parameter")
            level = self.parameters["level"]
            if not isinstance(level, int) or not 0 <= level <= 100:
                raise ValueError("Volume level must be an integer between 0 and 100")

        elif self.action_type == ActionType.SYSTEM_FILE_FIND:
            if "pattern" not in self.parameters:
                raise ValueError("SYSTEM_FILE_FIND requires 'pattern' parameter")

        elif self.action_type == ActionType.SYSTEM_FILE_DELETE:
            if "file_path" not in self.parameters:
                raise ValueError("SYSTEM_FILE_DELETE requires 'file_path' parameter")

        elif self.action_type in (ActionType.BROWSER_NAVIGATE, ActionType.BROWSER_SEARCH):
            if self.action_type == ActionType.BROWSER_NAVIGATE and "url" not in self.parameters:
                raise ValueError("BROWSER_NAVIGATE requires 'url' parameter")
            if self.action_type == ActionType.BROWSER_SEARCH and "query" not in self.parameters:
                raise ValueError("BROWSER_SEARCH requires 'query' parameter")

    @classmethod
    def create(
        cls,
        command_id: str,
        action_type: ActionType,
        parameters: Dict[str, Any]
    ) -> "Action":
        """
        Factory method to create a new Action.

        Args:
            command_id: ID of the voice command
            action_type: Type of action
            parameters: Action parameters

        Returns:
            New Action instance
        """
        return cls(
            action_id=str(uuid.uuid4()),
            command_id=command_id,
            action_type=action_type,
            parameters=parameters,
            status=ActionStatus.PENDING,
            created_at=datetime.utcnow()
        )

    def mark_executing(self) -> None:
        """Mark action as currently executing."""
        self.status = ActionStatus.EXECUTING

    def mark_completed(self, result: ActionResult, execution_time_ms: int) -> None:
        """
        Mark action as completed with result.

        Args:
            result: Execution result
            execution_time_ms: Time taken to execute
        """
        self.status = ActionStatus.COMPLETED
        self.result = result
        self.execution_time_ms = execution_time_ms

    def mark_failed(self, error_message: str, execution_time_ms: Optional[int] = None) -> None:
        """
        Mark action as failed with error message.

        Args:
            error_message: Description of the failure
            execution_time_ms: Time taken before failure
        """
        self.status = ActionStatus.FAILED
        self.error_message = error_message
        self.execution_time_ms = execution_time_ms

    def requires_confirmation(self) -> None:
        """Mark action as requiring user confirmation before execution."""
        self.status = ActionStatus.REQUIRES_CONFIRMATION

    def to_dict(self) -> dict:
        """Convert action to dictionary representation."""
        return {
            "action_id": self.action_id,
            "command_id": self.command_id,
            "action_type": self.action_type.value,
            "parameters": self.parameters,
            "status": self.status.value,
            "result": self.result.value if self.result else None,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at.isoformat(),
        }
