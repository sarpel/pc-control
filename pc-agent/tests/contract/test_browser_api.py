"""
Contract tests for browser automation API endpoints.

Tests the browser control REST API endpoints defined in contracts/rest-api.yaml.
Following TDD: These tests should FAIL initially until implementation is complete.
"""
import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_browser_navigate_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/browser/navigate endpoint."""
    payload = {
        "url": "https://www.example.com",
        "wait_until": "load"
    }

    response = await async_client.post(
        "/api/v1/browser/navigate",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert "navigation_id" in data
    assert data["url"] == payload["url"]


@pytest.mark.asyncio
async def test_browser_search_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/browser/search endpoint."""
    payload = {
        "query": "Python programming",
        "search_engine": "google"
    }

    response = await async_client.post(
        "/api/v1/browser/search",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert "search_url" in data
    assert "google.com" in data["search_url"]


@pytest.mark.asyncio
async def test_browser_extract_content_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/browser/extract endpoint."""
    payload = {
        "url": "https://www.example.com",
        "extract_type": "text"
    }

    response = await async_client.post(
        "/api/v1/browser/extract",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "success"
    assert "content" in data
    assert isinstance(data["content"], str)


@pytest.mark.asyncio
async def test_browser_navigate_invalid_url(async_client: AsyncClient, authenticated_headers: dict):
    """Test navigation with invalid URL returns 400."""
    payload = {
        "url": "not-a-valid-url",
        "wait_until": "load"
    }

    response = await async_client.post(
        "/api/v1/browser/navigate",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "error" in data
    assert "url" in data["error"].lower()


@pytest.mark.asyncio
async def test_browser_navigate_unauthorized(async_client: AsyncClient):
    """Test navigation without authentication returns 401."""
    payload = {
        "url": "https://www.example.com",
        "wait_until": "load"
    }

    response = await async_client.post(
        "/api/v1/browser/navigate",
        json=payload
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_browser_search_empty_query(async_client: AsyncClient, authenticated_headers: dict):
    """Test search with empty query returns 400."""
    payload = {
        "query": "",
        "search_engine": "google"
    }

    response = await async_client.post(
        "/api/v1/browser/search",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_browser_extract_timeout(async_client: AsyncClient, authenticated_headers: dict):
    """Test content extraction with timeout."""
    payload = {
        "url": "https://httpstat.us/200?sleep=35000",  # 35 second delay
        "extract_type": "text",
        "timeout": 1  # 1 second timeout
    }

    response = await async_client.post(
        "/api/v1/browser/extract",
        json=payload,
        headers=authenticated_headers
    )

    assert response.status_code == status.HTTP_408_REQUEST_TIMEOUT
    data = response.json()
    assert "timeout" in data["error"].lower()
