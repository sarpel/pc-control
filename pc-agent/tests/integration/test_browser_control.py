"""
Integration tests for browser control flow.

Tests the end-to-end browser automation workflow including:
- Chrome DevTools MCP server integration
- Page navigation and interaction
- Content extraction
- Error handling and recovery

Following TDD: These tests should FAIL initially until implementation is complete.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.services.browser_controller import BrowserController
from src.services.command_interpreter import CommandInterpreter
from src.models.action import Action, ActionType


@pytest.fixture
async def browser_controller():
    """Create a browser controller instance for testing."""
    controller = BrowserController()
    await controller.initialize()
    yield controller
    await controller.cleanup()


@pytest.mark.asyncio
async def test_browser_navigate_flow(browser_controller: BrowserController):
    """Test complete navigation flow from command to execution."""
    # Arrange
    url = "https://www.example.com"
    action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": url, "wait_until": "load"}
    )

    # Act
    result = await browser_controller.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert result["url"] == url
    assert "navigation_id" in result
    assert result["page_loaded"] is True


@pytest.mark.asyncio
async def test_browser_search_flow(browser_controller: BrowserController):
    """Test search operation flow."""
    # Arrange
    query = "weather forecast"
    action = Action(
        action_type=ActionType.BROWSER,
        operation="search",
        parameters={"query": query, "search_engine": "google"}
    )

    # Act
    result = await browser_controller.execute_action(action)

    # Assert
    assert result["status"] == "success"
    assert "search_url" in result
    assert query.replace(" ", "+") in result["search_url"]
    assert "google.com" in result["search_url"]


@pytest.mark.asyncio
async def test_page_content_extraction(browser_controller: BrowserController):
    """Test content extraction from loaded page."""
    # Arrange
    url = "https://www.example.com"

    # First navigate to page
    navigate_action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": url}
    )
    await browser_controller.execute_action(navigate_action)

    # Then extract content
    extract_action = Action(
        action_type=ActionType.BROWSER,
        operation="extract_content",
        parameters={"extract_type": "text"}
    )

    # Act
    result = await browser_controller.execute_action(extract_action)

    # Assert
    assert result["status"] == "success"
    assert "content" in result
    assert isinstance(result["content"], str)
    assert len(result["content"]) > 0


@pytest.mark.asyncio
async def test_browser_error_handling_invalid_url(browser_controller: BrowserController):
    """Test error handling for invalid URL."""
    # Arrange
    action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": "not-a-valid-url"}
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid URL"):
        await browser_controller.execute_action(action)


@pytest.mark.asyncio
async def test_browser_timeout_handling(browser_controller: BrowserController):
    """Test timeout handling for slow page loads."""
    # Arrange
    action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": "https://httpstat.us/200?sleep=35000", "timeout": 1}
    )

    # Act & Assert
    with pytest.raises(TimeoutError, match="Navigation timeout"):
        await browser_controller.execute_action(action)


@pytest.mark.asyncio
async def test_command_interpreter_browser_integration():
    """Test that command interpreter correctly routes browser commands."""
    # Arrange
    interpreter = CommandInterpreter()
    command_text = "Google'da hava durumu ara"  # Turkish: "Search weather on Google"

    # Act
    with patch('src.services.command_interpreter.CommandInterpreter.call_claude_api') as mock_claude:
        mock_claude.return_value = {
            "action_type": "browser",
            "operation": "search",
            "parameters": {"query": "hava durumu", "search_engine": "google"}
        }

        action = await interpreter.interpret_command(command_text)

    # Assert
    assert action.action_type == ActionType.BROWSER
    assert action.operation == "search"
    assert "hava durumu" in action.parameters["query"]


@pytest.mark.asyncio
async def test_browser_page_summary_extraction(browser_controller: BrowserController):
    """Test extracting page summary for display."""
    # Arrange
    url = "https://www.example.com"

    # Navigate to page
    navigate_action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": url}
    )
    await browser_controller.execute_action(navigate_action)

    # Extract summary (max 500 chars)
    summary_action = Action(
        action_type=ActionType.BROWSER,
        operation="extract_summary",
        parameters={"max_length": 500}
    )

    # Act
    result = await browser_controller.execute_action(summary_action)

    # Assert
    assert result["status"] == "success"
    assert "summary" in result
    assert len(result["summary"]) <= 500
    assert isinstance(result["summary"], str)


@pytest.mark.asyncio
async def test_multiple_browser_operations_sequence(browser_controller: BrowserController):
    """Test sequence of browser operations."""
    # Arrange
    operations = [
        Action(ActionType.BROWSER, "navigate", {"url": "https://www.google.com"}),
        Action(ActionType.BROWSER, "search", {"query": "Python", "search_engine": "google"}),
        Action(ActionType.BROWSER, "extract_content", {"extract_type": "text"}),
    ]

    # Act
    results = []
    for action in operations:
        result = await browser_controller.execute_action(action)
        results.append(result)

    # Assert
    assert all(r["status"] == "success" for r in results)
    assert "navigation_id" in results[0]
    assert "search_url" in results[1]
    assert "content" in results[2]


@pytest.mark.asyncio
async def test_browser_cleanup_on_error(browser_controller: BrowserController):
    """Test that browser resources are cleaned up on error."""
    # Arrange
    action = Action(
        action_type=ActionType.BROWSER,
        operation="navigate",
        parameters={"url": "invalid://url"}
    )

    # Act & Assert
    with pytest.raises(ValueError):
        await browser_controller.execute_action(action)

    # Verify cleanup
    assert browser_controller.is_cleaned_up() is True
