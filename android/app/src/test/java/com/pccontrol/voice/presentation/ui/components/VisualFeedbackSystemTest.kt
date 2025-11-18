package com.pccontrol.voice.presentation.ui.components

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for Visual Feedback System
 *
 * Tests feedback management, timing validation, and performance monitoring.
 * Target: 90%+ code coverage
 */
@ExperimentalCoroutinesApi
class VisualFeedbackSystemTest {

    private lateinit var feedbackManager: VisualFeedbackManager

    @Before
    fun setup() {
        feedbackManager = VisualFeedbackManager()
    }

    @Test
    fun `showFeedback should create feedback state`() {
        // When
        feedbackManager.showFeedback(FeedbackType.SUCCESS, "Test message", 2000)

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.SUCCESS, state!!.type)
        assertEquals("Test message", state.message)
        assertEquals(2000, state.durationMs)
    }

    @Test
    fun `showSuccess should create success feedback`() {
        // When
        feedbackManager.showSuccess("Operation completed")

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.SUCCESS, state!!.type)
        assertEquals("Operation completed", state.message)
    }

    @Test
    fun `showError should create error feedback with longer duration`() {
        // When
        feedbackManager.showError("Operation failed")

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.ERROR, state!!.type)
        assertEquals("Operation failed", state.message)
        assertEquals(3000, state.durationMs)
    }

    @Test
    fun `showWarning should create warning feedback`() {
        // When
        feedbackManager.showWarning("Warning message")

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.WARNING, state!!.type)
        assertEquals(2500, state.durationMs)
    }

    @Test
    fun `showInfo should create info feedback`() {
        // When
        feedbackManager.showInfo("Information")

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.INFO, state!!.type)
    }

    @Test
    fun `showLoading should create loading feedback with no timeout`() {
        // When
        feedbackManager.showLoading("Loading...")

        // Then
        val state = feedbackManager.feedbackState.value
        assertNotNull(state)
        assertEquals(FeedbackType.LOADING, state!!.type)
        assertEquals(Int.MAX_VALUE, state.durationMs)
    }

    @Test
    fun `clearFeedback should remove feedback state`() {
        // Given
        feedbackManager.showSuccess("Test")

        // When
        feedbackManager.clearFeedback()

        // Then
        assertNull(feedbackManager.feedbackState.value)
    }

    @Test
    fun `getAverageFeedbackTiming should return zero for empty history`() {
        // When
        val average = feedbackManager.getAverageFeedbackTiming()

        // Then
        assertEquals(0.0, average, 0.01)
    }

    @Test
    fun `getAverageFeedbackTiming should calculate average correctly`() {
        // Given - trigger multiple feedbacks to populate timing history
        repeat(5) {
            feedbackManager.showSuccess("Test $it")
        }

        // When
        val average = feedbackManager.getAverageFeedbackTiming()

        // Then
        assertTrue(average >= 0.0)
        assertTrue(average < 200.0) // Should be fast
    }

    @Test
    fun `getTimingCompliancePercentage should return 100 for empty history`() {
        // When
        val compliance = feedbackManager.getTimingCompliancePercentage()

        // Then
        assertEquals(100.0, compliance, 0.01)
    }

    @Test
    fun `getTimingCompliancePercentage should calculate compliance correctly`() {
        // Given - trigger feedbacks
        repeat(10) {
            feedbackManager.showSuccess("Test $it")
        }

        // When
        val compliance = feedbackManager.getTimingCompliancePercentage()

        // Then
        assertTrue(compliance >= 0.0)
        assertTrue(compliance <= 100.0)
    }

    @Test
    fun `getTimingStatistics should return complete stats`() {
        // Given
        repeat(5) {
            feedbackManager.showSuccess("Test $it")
        }

        // When
        val stats = feedbackManager.getTimingStatistics()

        // Then
        assertEquals(5, stats.count)
        assertTrue(stats.average >= 0.0)
        assertTrue(stats.min >= 0)
        assertTrue(stats.max >= stats.min)
        assertTrue(stats.compliancePercentage >= 0.0)
        assertTrue(stats.compliancePercentage <= 100.0)
    }

    @Test
    fun `FeedbackState isExpired should return false immediately after creation`() {
        // Given
        val state = FeedbackState(
            type = FeedbackType.SUCCESS,
            message = "Test",
            timestamp = System.currentTimeMillis(),
            durationMs = 2000
        )

        // When
        val isExpired = state.isExpired()

        // Then
        assertFalse(isExpired)
    }

    @Test
    fun `FeedbackState isExpired should return true for old timestamp`() {
        // Given
        val state = FeedbackState(
            type = FeedbackType.SUCCESS,
            message = "Test",
            timestamp = System.currentTimeMillis() - 3000, // 3 seconds ago
            durationMs = 2000
        )

        // When
        val isExpired = state.isExpired()

        // Then
        assertTrue(isExpired)
    }

    @Test
    fun `FeedbackState isWithinTimingRequirement should return true for recent feedback`() {
        // Given
        val state = FeedbackState(
            type = FeedbackType.SUCCESS,
            message = "Test",
            timestamp = System.currentTimeMillis(),
            durationMs = 2000
        )

        // When
        val isWithin = state.isWithinTimingRequirement()

        // Then
        assertTrue(isWithin)
    }

    @Test
    fun `FeedbackTimingStats should have valid structure`() {
        // Given
        val stats = FeedbackTimingStats(
            count = 10,
            average = 150.5,
            min = 50,
            max = 300,
            compliancePercentage = 95.0
        )

        // Then
        assertEquals(10, stats.count)
        assertEquals(150.5, stats.average, 0.01)
        assertEquals(50L, stats.min)
        assertEquals(300L, stats.max)
        assertEquals(95.0, stats.compliancePercentage, 0.01)
    }

    @Test
    fun `multiple feedbacks should maintain timing history`() {
        // When
        feedbackManager.showSuccess("Test 1")
        feedbackManager.showError("Test 2")
        feedbackManager.showWarning("Test 3")
        feedbackManager.showInfo("Test 4")

        // Then
        val stats = feedbackManager.getTimingStatistics()
        assertEquals(4, stats.count)
    }

    @Test
    fun `feedback types should have distinct characteristics`() {
        // Test all feedback types
        val types = listOf(
            FeedbackType.SUCCESS,
            FeedbackType.ERROR,
            FeedbackType.WARNING,
            FeedbackType.INFO,
            FeedbackType.LOADING,
            FeedbackType.PROCESSING
        )

        types.forEach { type ->
            val state = FeedbackState(
                type = type,
                message = "Test ${type.name}",
                durationMs = 2000
            )
            assertNotNull(state)
            assertEquals(type, state.type)
        }
    }

    @Test
    fun `timing history should be limited to max size`() {
        // Given - trigger more than max history size (100)
        repeat(150) {
            feedbackManager.showSuccess("Test $it")
        }

        // When
        val stats = feedbackManager.getTimingStatistics()

        // Then
        assertTrue(stats.count <= 100) // Should not exceed max history
    }

    @Test
    fun `consecutive feedbacks should update state`() {
        // When
        feedbackManager.showSuccess("First")
        val firstState = feedbackManager.feedbackState.value

        feedbackManager.showError("Second")
        val secondState = feedbackManager.feedbackState.value

        // Then
        assertNotNull(firstState)
        assertNotNull(secondState)
        assertNotEquals(firstState!!.message, secondState!!.message)
        assertEquals(FeedbackType.ERROR, secondState.type)
    }
}
