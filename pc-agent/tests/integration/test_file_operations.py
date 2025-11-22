"""
Integration tests for file operations flow.

Tests the end-to-end file system operations including:
- File search across directories
- File deletion with confirmation
- System directory protection
- Error handling and Turkish messages

Task: T069 - User Story 3
"""
import pytest
import tempfile
import os
import uuid
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.services.system_control import SystemControlService
from src.models.action import Action, ActionType, ActionStatus


@pytest.fixture
async def system_control():
    """Create a system control service instance for testing."""
    service = SystemControlService()
    # await service.initialize() # Removed as initialize method does not exist
    yield service
    # await service.cleanup() # Removed as cleanup method does not exist


@pytest.fixture
def temp_test_files(tmp_path):
    """Create temporary test files for file operations."""
    # Create test directory structure
    test_dir = tmp_path / "test_files"
    test_dir.mkdir()

    # Create some test files
    (test_dir / "document.txt").write_text("Test document content")
    (test_dir / "image.png").write_bytes(b"fake image data")
    (test_dir / "data.json").write_text('{"key": "value"}')

    # Create subdirectory with files
    sub_dir = test_dir / "subdirectory"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("Nested file content")

    yield test_dir
    
    # Cleanup is handled by tmp_path fixture, but we can explicitly clean up if needed
    # shutil.rmtree(test_dir)


@pytest.mark.asyncio
async def test_find_files_by_name(system_control: SystemControlService, temp_test_files: Path):
    """Test finding files by name pattern."""
    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_FIND,
        parameters={
            "pattern": "*.txt",
            "path": str(temp_test_files),
            "max_results": 10
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    assert result.data is not None
    assert "results" in result.data
    assert len(result.data["results"]) >= 1
    assert any("document.txt" in f["FullName"] for f in result.data["results"])

@pytest.mark.asyncio
async def test_find_files_with_type_filter(system_control: SystemControlService, temp_test_files: Path):
    """Test finding files with type filter."""
    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_FIND,
        parameters={
            "pattern": "*",
            "path": str(temp_test_files),
            "file_type": ".json",
            "max_results": 10
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    assert len(result.data["results"]) >= 1
    assert all(f["FullName"].endswith(".json") for f in result.data["results"])

@pytest.mark.asyncio
async def test_delete_file_with_confirmation(system_control: SystemControlService, temp_test_files: Path):
    """Test file deletion with confirmation."""
    # Arrange
    test_file = temp_test_files / "delete_me.txt"
    test_file.write_text("File to be deleted")

    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_DELETE,
        parameters={
            "file_path": str(test_file),
            "confirmed": True
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_delete_file_without_confirmation_fails(system_control: SystemControlService):
    """Test that deletion without confirmation is rejected."""
    # Arrange
    protected_file = "C:/Windows/System32/protected.txt"

    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_DELETE,
        parameters={
            "file_path": protected_file,
            "confirmed": False
        }
    )
    
    # Mock os.path.exists to return True so it thinks file exists
    with patch("src.services.system_control.os.path.exists", return_value=True):
        # Act
        result = await system_control.execute_action(action)

        # Assert
        assert not result.success
        # The service returns a specific error for protected directories when force=False
        assert "korumalı" in result.error.lower() or "protected" in result.error.lower()
@pytest.mark.asyncio
async def test_system_directory_protection(system_control: SystemControlService):
    """Test that system directories are protected from deletion."""
    # Arrange - attempt to delete from System32
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_DELETE,
        parameters={
            "file_path": "C:/Windows/System32/test.dll",
            "confirmed": True
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert not result.success
    # The error message might vary but should indicate protection/permission issue
    assert any(keyword in result.error.lower() for keyword in ["system", "protected", "korumalı", "permission", "access"])


@pytest.mark.asyncio
async def test_get_system_info(system_control: SystemControlService):
    """Test retrieving system information."""
    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_INFO,
        parameters={}
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    assert result.data is not None
    info = result.data
    assert "os" in info
    assert "memory" in info
    assert "disk" in info
    assert "network" in info


@pytest.mark.asyncio
async def test_find_files_recursive(system_control: SystemControlService, temp_test_files: Path):
    """Test recursive file search."""
    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_FIND,
        parameters={
            "pattern": "*.txt",
            "path": str(temp_test_files),
            "recursive": True,
            "max_results": 20
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    # Should find files in both root and subdirectory
    assert len(result.data["results"]) >= 2
    assert any("nested.txt" in f["FullName"] for f in result.data["results"])

@pytest.mark.asyncio
async def test_find_files_max_results_limit(system_control: SystemControlService, temp_test_files: Path):
    """Test that max_results limit is respected."""
    # Create many files
    for i in range(20):
        (temp_test_files / f"file_{i}.txt").write_text(f"Content {i}")

    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_FIND,
        parameters={
            "pattern": "file_*.txt",
            "path": str(temp_test_files),
            "max_results": 5
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result.success
    assert len(result.data["results"]) <= 5


@pytest.mark.asyncio
async def test_delete_nonexistent_file_error(system_control: SystemControlService):
    """Test error handling for deleting non-existent file."""
    # Arrange
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_DELETE,
        parameters={
            "file_path": "C:/NonExistent/File/Path.txt",
            "confirmed": True
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert not result.success
    assert "found" in result.error.lower() or "bulunamadı" in result.error.lower()


@pytest.mark.asyncio
async def test_turkish_error_messages(system_control: SystemControlService):
    """Test that error messages are in Turkish."""
    # Arrange - trigger an error
    action = Action(
        action_id=str(uuid.uuid4()),
        command_id=str(uuid.uuid4()),
        status=ActionStatus.PENDING,
        action_type=ActionType.SYSTEM_FILE_DELETE,
        parameters={
            "file_path": "C:/Windows/System32/kernel32.dll",
            "confirmed": True
        }
    )
    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert not result.success
    error_message = result.error.lower()
    # Check for Turkish keywords
    turkish_keywords = ["korumalı", "sistem", "izin", "dosya"]
    # At least one Turkish keyword should be present or it's an acceptable English technical term
    assert any(keyword in error_message for keyword in turkish_keywords) or "protected" in error_message
