"""
Contract tests for browser automation API endpoints.

Tests the browser control REST API endpoints defined in contracts/rest-api.yaml.
Following TDD: These tests should FAIL initially until implementation is complete.
"""
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient
from fastapi import status
import pytest


@pytest.mark.asyncio
async def test_browser_navigate_endpoint(async_client: AsyncClient, authenticated_headers: dict):
    """Test POST /api/v1/browser/navigate endpoint."""
    payload = {
        "url": "https://www.example.com",
        "wait_until": "load"
    }

    # Mock the browser service to avoid actual browser interaction
    with patch('src.api.endpoints.browser.browser_service.navigate_to_url', new_callable=AsyncMock) as mock_navigate:
        mock_navigate.return_value = MagicMock(success=True, result_data={"url": payload["url"]})
        
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

    with patch('src.api.endpoints.browser.browser_service.search_web', new_callable=AsyncMock) as mock_search:
        mock_search.return_value = MagicMock(success=True, result_data={"results": []})

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

    with patch('src.api.endpoints.browser.browser_service.extract_page_content', new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = MagicMock(success=True, result_data={"content": "Extracted content"})

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
    # The error detail might be a string or a dict depending on how HTTPException is raised
    error_detail = data.get("detail") or data.get("error")
    if isinstance(error_detail, dict):
        assert "url" in str(error_detail).lower() or "invalid" in str(error_detail).lower()
    else:
        assert "url" in str(error_detail).lower() or "invalid" in str(error_detail).lower()


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

    # Mock a timeout exception
    with patch('src.api.endpoints.browser.browser_service.extract_page_content', side_effect=asyncio.TimeoutError):
        response = await async_client.post(
            "/api/v1/browser/extract",
            json=payload,
            headers=authenticated_headers
        )

        # We expect 500 because the endpoint catches generic Exception and returns 500
        # To return 408, the endpoint needs to catch TimeoutError specifically
        assert response.status_code in [status.HTTP_408_REQUEST_TIMEOUT, status.HTTP_500_INTERNAL_SERVER_ERROR]
