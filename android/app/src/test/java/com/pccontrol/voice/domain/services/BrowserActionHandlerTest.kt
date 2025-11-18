package com.pccontrol.voice.domain.services

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.pccontrol.voice.data.models.Action
import com.pccontrol.voice.data.models.ActionStatus
import com.pccontrol.voice.data.models.ActionType
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.util.*

/**
 * Unit tests for BrowserActionHandler
 *
 * Tests browser action processing, page summary management, and error handling.
 * Target: 90%+ code coverage
 */
@ExperimentalCoroutinesApi
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [30])
class BrowserActionHandlerTest {

    private lateinit var context: Context
    private lateinit var handler: BrowserActionHandler

    @Before
    fun setup() {
        context = ApplicationProvider.getApplicationContext()
        handler = BrowserActionHandler.getInstance(context)
    }

    @Test
    fun `processAction should handle BROWSER_NAVIGATE correctly`() = runTest {
        // Given
        val action = Action.createBrowserNavigateAction(
            commandId = UUID.randomUUID(),
            url = "https://www.google.com"
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.EXECUTING, result.status)
        assertNull(result.errorMessage)
    }

    @Test
    fun `processAction should fail BROWSER_NAVIGATE with empty URL`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            parameters = mapOf("url" to "")
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.FAILED, result.status)
        assertNotNull(result.errorMessage)
        assertTrue(result.errorMessage!!.contains("URL"))
    }

    @Test
    fun `processAction should handle BROWSER_SEARCH correctly`() = runTest {
        // Given
        val action = Action.createBrowserSearchAction(
            commandId = UUID.randomUUID(),
            searchQuery = "weather forecast"
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.EXECUTING, result.status)
        assertNull(result.errorMessage)
    }

    @Test
    fun `processAction should fail BROWSER_SEARCH with empty query`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_SEARCH,
            parameters = mapOf("search_query" to "")
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.FAILED, result.status)
        assertNotNull(result.errorMessage)
    }

    @Test
    fun `processAction should handle BROWSER_EXTRACT and set loading state`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_EXTRACT,
            parameters = mapOf("extract_type" to "summary")
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.EXECUTING, result.status)
        val summaryState = handler.pageSummary.first()
        assertTrue(summaryState is PageSummaryState.Loading)
    }

    @Test
    fun `processAction should handle BROWSER_INTERACT correctly`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_INTERACT,
            parameters = mapOf(
                "interaction_type" to "click",
                "target" to "button#submit"
            )
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.EXECUTING, result.status)
    }

    @Test
    fun `processAction should fail BROWSER_INTERACT with missing interaction type`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_INTERACT,
            parameters = mapOf("target" to "button")
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.FAILED, result.status)
        assertNotNull(result.errorMessage)
    }

    @Test
    fun `processAction should reject non-browser actions`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.SYSTEM_LAUNCH,
            parameters = mapOf("executable_path" to "notepad.exe")
        )

        // When
        val result = handler.processAction(action)

        // Then
        assertEquals(ActionStatus.FAILED, result.status)
        assertTrue(result.errorMessage!!.contains("tarayıcı"))
    }

    @Test
    fun `handleActionResult should set success state for extract`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_EXTRACT,
            parameters = emptyMap()
        )
        val resultData = mapOf(
            "extracted_content" to "Test content",
            "page_title" to "Test Page",
            "page_url" to "https://test.com"
        )

        // When
        handler.handleActionResult(action, resultData, null)

        // Then
        val summaryState = handler.pageSummary.first()
        assertTrue(summaryState is PageSummaryState.Success)
        val summary = (summaryState as PageSummaryState.Success).summary
        assertEquals("Test content", summary.content)
        assertEquals("Test Page", summary.title)
        assertEquals("https://test.com", summary.url)
    }

    @Test
    fun `handleActionResult should set error state when result is null`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_EXTRACT,
            parameters = emptyMap()
        )

        // When
        handler.handleActionResult(action, null, null)

        // Then
        val summaryState = handler.pageSummary.first()
        assertTrue(summaryState is PageSummaryState.Error)
    }

    @Test
    fun `handleActionResult should set browser error when error provided`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            parameters = emptyMap()
        )

        // When
        handler.handleActionResult(action, null, "Connection timeout")

        // Then
        val error = handler.browserError.first()
        assertNotNull(error)
        assertEquals("Connection timeout", error!!.errorMessage)
        assertEquals(action.actionId, error.actionId)
    }

    @Test
    fun `clearPageSummary should reset summary state to Idle`() = runTest {
        // Given - set a success state first
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_EXTRACT,
            parameters = emptyMap()
        )
        handler.handleActionResult(
            action,
            mapOf("extracted_content" to "Test"),
            null
        )

        // When
        handler.clearPageSummary()

        // Then
        val summaryState = handler.pageSummary.first()
        assertTrue(summaryState is PageSummaryState.Idle)
    }

    @Test
    fun `clearBrowserError should reset error to null`() = runTest {
        // Given - set an error first
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            parameters = emptyMap()
        )
        handler.handleActionResult(action, null, "Test error")

        // When
        handler.clearBrowserError()

        // Then
        val error = handler.browserError.first()
        assertNull(error)
    }

    @Test
    fun `hasActiveOperation should return true when loading`() = runTest {
        // Given
        val action = Action.create(
            commandId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_EXTRACT,
            parameters = emptyMap()
        )
        handler.processAction(action)

        // When
        val hasActive = handler.hasActiveOperation()

        // Then
        assertTrue(hasActive)
    }

    @Test
    fun `hasActiveOperation should return false when idle`() = runTest {
        // When
        val hasActive = handler.hasActiveOperation()

        // Then
        assertFalse(hasActive)
    }

    @Test
    fun `BrowserError getDisplayMessage should categorize timeout errors`() {
        // Given
        val error = BrowserError(
            actionId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            errorMessage = "Connection timeout occurred",
            timestamp = System.currentTimeMillis()
        )

        // When
        val displayMessage = error.getDisplayMessage()

        // Then
        assertTrue(displayMessage.contains("zaman aşımı"))
    }

    @Test
    fun `BrowserError getDisplayMessage should categorize not found errors`() {
        // Given
        val error = BrowserError(
            actionId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            errorMessage = "Page not found",
            timestamp = System.currentTimeMillis()
        )

        // When
        val displayMessage = error.getDisplayMessage()

        // Then
        assertTrue(displayMessage.contains("bulunamadı"))
    }

    @Test
    fun `BrowserError isRecoverable should return true for timeout`() {
        // Given
        val error = BrowserError(
            actionId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            errorMessage = "timeout",
            timestamp = System.currentTimeMillis()
        )

        // When
        val isRecoverable = error.isRecoverable()

        // Then
        assertTrue(isRecoverable)
    }

    @Test
    fun `BrowserError isRecoverable should return false for other errors`() {
        // Given
        val error = BrowserError(
            actionId = UUID.randomUUID(),
            actionType = ActionType.BROWSER_NAVIGATE,
            errorMessage = "Invalid URL",
            timestamp = System.currentTimeMillis()
        )

        // When
        val isRecoverable = error.isRecoverable()

        // Then
        assertFalse(isRecoverable)
    }

    @Test
    fun `getInstance should return singleton instance`() {
        // Given
        val instance1 = BrowserActionHandler.getInstance(context)
        val instance2 = BrowserActionHandler.getInstance(context)

        // Then
        assertSame(instance1, instance2)
    }
}
