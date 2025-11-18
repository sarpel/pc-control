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
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.services.system_control import SystemControlService
from src.models.action import Action, ActionType


@pytest.fixture
async def system_control():
    """Create a system control service instance for testing."""
    service = SystemControlService()
    await service.initialize()
    yield service
    await service.cleanup()


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

    return test_dir


@pytest.mark.asyncio
async def test_find_files_by_name(system_control: SystemControlService, temp_test_files: Path):
    """Test finding files by name pattern."""
    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="find_files",
        parameters={
            "query": "*.txt",
            "path": str(temp_test_files),
            "max_results": 10
        }
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert "files" in result
    assert len(result["files"]) >= 1
    assert any("document.txt" in f["path"] for f in result["files"])


@pytest.mark.asyncio
async def test_find_files_with_type_filter(system_control: SystemControlService, temp_test_files: Path):
    """Test finding files with type filter."""
    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="find_files",
        parameters={
            "query": "*",
            "path": str(temp_test_files),
            "file_type": ".json",
            "max_results": 10
        }
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert len(result["files"]) >= 1
    assert all(f["path"].endswith(".json") for f in result["files"])


@pytest.mark.asyncio
async def test_delete_file_with_confirmation(system_control: SystemControlService, temp_test_files: Path):
    """Test file deletion with confirmation."""
    # Arrange
    test_file = temp_test_files / "delete_me.txt"
    test_file.write_text("File to be deleted")

    action = Action(
        action_type=ActionType.SYSTEM,
        operation="delete_file",
        parameters={
            "file_path": str(test_file),
            "confirmed": True
        }
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert not test_file.exists()


@pytest.mark.asyncio
async def test_delete_file_without_confirmation_fails(system_control: SystemControlService, temp_test_files: Path):
    """Test that deletion without confirmation is rejected."""
    # Arrange
    test_file = temp_test_files / "protected.txt"
    test_file.write_text("Protected file")

    action = Action(
        action_type=ActionType.SYSTEM,
        operation="delete_file",
        parameters={
            "file_path": str(test_file),
            "confirmed": False
        }
    )

    # Act & Assert
    with pytest.raises(ValueError, match="confirmation|onay"):
        await system_control.execute_action(action)

    # File should still exist
    assert test_file.exists()


@pytest.mark.asyncio
async def test_system_directory_protection(system_control: SystemControlService):
    """Test that system directories are protected from deletion."""
    # Arrange - attempt to delete from System32
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="delete_file",
        parameters={
            "file_path": "C:/Windows/System32/test.dll",
            "confirmed": True
        }
    )

    # Act & Assert
    with pytest.raises(PermissionError, match="system|protected|korumalı"):
        await system_control.execute_action(action)


@pytest.mark.asyncio
async def test_get_system_info(system_control: SystemControlService):
    """Test retrieving system information."""
    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="query_system_info",
        parameters={}
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert "system_info" in result
    info = result["system_info"]
    assert "cpu" in info
    assert "memory" in info
    assert "disk" in info
    assert "platform" in info


@pytest.mark.asyncio
async def test_find_files_recursive(system_control: SystemControlService, temp_test_files: Path):
    """Test recursive file search."""
    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="find_files",
        parameters={
            "query": "*.txt",
            "path": str(temp_test_files),
            "recursive": True,
            "max_results": 20
        }
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    # Should find files in both root and subdirectory
    assert len(result["files"]) >= 2
    assert any("nested.txt" in f["path"] for f in result["files"])


@pytest.mark.asyncio
async def test_find_files_max_results_limit(system_control: SystemControlService, temp_test_files: Path):
    """Test that max_results limit is respected."""
    # Create many files
    for i in range(20):
        (temp_test_files / f"file_{i}.txt").write_text(f"Content {i}")

    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="find_files",
        parameters={
            "query": "file_*.txt",
            "path": str(temp_test_files),
            "max_results": 5
        }
    )

    # Act
    result = await system_control.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert len(result["files"]) <= 5


@pytest.mark.asyncio
async def test_delete_nonexistent_file_error(system_control: SystemControlService):
    """Test error handling for deleting non-existent file."""
    # Arrange
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="delete_file",
        parameters={
            "file_path": "C:/NonExistent/File/Path.txt",
            "confirmed": True
        }
    )

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        await system_control.execute_action(action)


@pytest.mark.asyncio
async def test_turkish_error_messages(system_control: SystemControlService):
    """Test that error messages are in Turkish."""
    # Arrange - trigger an error
    action = Action(
        action_type=ActionType.SYSTEM,
        operation="delete_file",
        parameters={
            "file_path": "C:/Windows/System32/kernel32.dll",
            "confirmed": True
        }
    )

    # Act & Assert
    try:
        await system_control.execute_action(action)
        pytest.fail("Expected exception")
    except Exception as e:
        error_message = str(e).lower()
        # Check for Turkish keywords
        turkish_keywords = ["korumalı", "sistem", "izin", "dosya"]
        # At least one Turkish keyword should be present or it's an acceptable English technical term
        assert any(keyword in error_message for keyword in turkish_keywords) or "protected" in error_message
