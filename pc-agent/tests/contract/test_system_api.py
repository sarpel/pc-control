"""
Contract tests for system operations API endpoints.

Tests the system control REST API endpoints defined in contracts/rest-api.yaml.
Following TDD: These tests should FAIL initially until implementation is complete.

Task: T068 - User Story 3
"""
import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_find_files_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/system/find-files endpoint."""
    payload = {
        "query": "test.txt",
        "path": "C:/Users",
        "max_results": 10
    }

    response = await async_client.post(
        "/api/v1/system/find-files",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert "files" in data
    assert isinstance(data["files"], list)


@pytest.mark.asyncio
async def test_system_info_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test GET /api/v1/system/info endpoint."""
    response = await async_client.get(
        "/api/v1/system/info",
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert "system_info" in data
    assert "cpu" in data["system_info"]
    assert "memory" in data["system_info"]
    assert "disk" in data["system_info"]


@pytest.mark.asyncio
async def test_delete_file_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test DELETE /api/v1/system/file endpoint."""
    payload = {
        "file_path": "C:/Users/test_file.txt",
        "confirmed": True
    }

    response = await async_client.request(
        "DELETE",
        "/api/v1/system/files",
        json=payload,
        headers=authenticated_headers
    )

    # Should succeed or return appropriate error
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]


@pytest.mark.asyncio
async def test_delete_file_requires_confirmation(async_client: AsyncClient, authenticated_headers: dict):
    """Test that system directory deletions require confirmation."""
    payload = {
        "file_path": "C:/Windows/System32/test.dll",
        "confirmed": False
    }

    response = await async_client.request(
        "DELETE",
        "/api/v1/system/files",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    # Check message in structured error response
    error_msg = data["error"]["message"] if "message" in data["error"] else str(data["error"])
    assert "confirmation" in error_msg.lower()


@pytest.mark.asyncio
async def test_find_files_invalid_path(async_client: AsyncClient, authenticated_headers: dict):
    """Test find files with invalid path returns error."""
    payload = {
        "query": "test.txt",
        "path": "Z:/NonExistent/Path",
        "max_results": 10
    }

    response = await async_client.post(
        "/api/v1/system/find-files",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]


@pytest.mark.asyncio
async def test_system_operations_unauthorized(async_client: AsyncClient):
    """Test system operations without authentication returns 401."""
    response = await async_client.get("/api/v1/system/info")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_launch_application_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/system/launch endpoint."""
    payload = {
        "application": "notepad",
        "arguments": []
    }

    response = await async_client.post(
        "/api/v1/system/launch",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_volume_control_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/system/volume endpoint."""
    payload = {
        "action": "set",
        "level": 50
    }

    response = await async_client.post(
        "/api/v1/system/volume",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
