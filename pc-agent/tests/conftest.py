"""
Pytest configuration and fixtures for PC Control Agent tests.

This module provides shared test fixtures and configuration for all test types.
"""

import os
import sys

# Ensure we're using test settings before importing app
os.environ["PC_AGENT_ENVIRONMENT"] = "testing"
os.environ["PC_AGENT_USE_SSL"] = "false"

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from src.api.main import app
from src.config.settings import get_settings, Settings


@pytest.fixture
async def cleanup_database():
    """Ensure database connection is closed after each test."""
    yield
    from src.database import connection
    if connection._db_connection:
        await connection._db_connection.close()
        connection._db_connection = None
    # Force GC to release file handles
    import gc
    gc.collect()


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Generator[Settings, None, None]:
    """Provide test settings with temporary database."""
    temp_dir = tempfile.mkdtemp()
    # Use a unique database file for each test to avoid locking
    import uuid
    db_name = f"test_{uuid.uuid4().hex}.db"
    temp_db_path = Path(temp_dir) / db_name

    settings = Settings(
        database_url=f"sqlite:///{temp_db_path}",
        use_ssl=False,
        log_level="ERROR",
        session_timeout=3600,  # 1 hour for tests
        claude_api_key="test-key",
        max_concurrent_connections=5,
        command_timeout=60,
        environment="testing"
    )
    
    yield settings
    
    # Robust cleanup
    import shutil
    import time
    import gc
    
    # Force garbage collection to release file handles
    gc.collect()
    
    # Try to remove the directory with retries
    max_retries = 3
    for i in range(max_retries):
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            break
        except PermissionError:
            if i < max_retries - 1:
                time.sleep(0.5)
            else:
                print(f"Warning: Could not clean up temp dir {temp_dir}")


@pytest.fixture
def client(test_settings: Settings) -> Generator[TestClient, None, None]:
    """Create a FastAPI test client."""
    # Override settings for testing
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    # Clean up
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(test_settings: Settings) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    # Override settings for testing
    app.dependency_overrides[get_settings] = lambda: test_settings
    
    # Reset global database connection to ensure it picks up new settings
    import src.database.connection
    src.database.connection._db_connection = None

    # Patch get_settings globally for direct calls and ensure lifespan
    with patch('src.config.settings.get_settings', return_value=test_settings), \
         patch('src.database.connection.get_settings', return_value=test_settings):
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac

    # Clean up
    app.dependency_overrides.clear()
    # Reset again to be safe
    src.database.connection._db_connection = None


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    websocket = AsyncMock()
    websocket.send_json = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.receive_json = AsyncMock()
    websocket.receive_text = AsyncMock()
    websocket.receive_bytes = AsyncMock()
    websocket.accept = AsyncMock()
    websocket.close = AsyncMock()
    websocket.client = ("127.0.0.1", 12345)
    websocket.scope = {"type": "websocket", "path": "/ws"}
    yield websocket
    # No explicit cleanup needed for mock, but yield ensures consistency


@pytest.fixture
def sample_audio_data() -> bytes:
    """Sample audio data for testing."""
    # This would normally be Opus-encoded audio data
    return b"fake_audio_data_for_testing"


@pytest.fixture
def sample_voice_command() -> dict:
    """Sample voice command data."""
    return {
        "type": "voice_command",
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-11-18T10:30:00Z",
        "transcription": "Chrome'u aç",
        "confidence": 0.95,
        "language": "tr",
        "duration_ms": 1500
    }


@pytest.fixture
def sample_action() -> dict:
    """Sample action data."""
    return {
        "type": "action_execution",
        "id": "660e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-11-18T10:30:01Z",
        "command_id": "550e8400-e29b-41d4-a716-446655440000",
        "action_id": "660e8400-e29b-41d4-a716-446655440001",
        "action_type": "system_launch",
        "status": "completed",
        "parameters": {
            "application_name": "Chrome"
        },
        "result": {
            "success": True,
            "message": "Chrome başarıyla açıldı",
            "execution_time_ms": 1200
        }
    }


@pytest.fixture
def mock_claude_response() -> dict:
    """Mock Claude API response for command interpretation."""
    return {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": """{
    "action_type": "system_launch",
    "parameters": {
        "application_name": "Chrome"
    },
    "confidence": 0.9
}"""
            }
        ]
    }


@pytest.fixture
def authenticated_headers() -> dict:
    """Return headers for authenticated requests."""
    return {"Authorization": "Bearer test-token"}


# Test markers for categorizing tests


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security-related"
    )
    config.addinivalue_line(
        "markers", "websocket: marks tests that use WebSocket connections"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on file location
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.contract)

        # Add security marker for security-related tests
        if "security" in str(item.fspath) or "auth" in str(item.fspath):
            item.add_marker(pytest.mark.security)

        # Add websocket marker for websocket tests
        if "websocket" in item.nodeid or "WebSocket" in item.name:
            item.add_marker(pytest.mark.websocket)


# Environment setup for tests
os.environ["PYTHONPATH"] = str(Path(__file__).parent.parent)