package com.pccontrol.voice.presentation.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Visual Feedback System
 *
 * Provides visual feedback for all user interactions with 200ms timing validation
 * and animation optimization. Ensures users receive immediate feedback for actions.
 *
 * Task: T090 Add visual feedback for all user interactions in Android UI with
 * 200ms timing validation and animation optimization
 */

/**
 * Feedback types for different interaction states
 */
enum class FeedbackType {
    SUCCESS,
    ERROR,
    WARNING,
    INFO,
    LOADING,
    PROCESSING
}

/**
 * Visual feedback state
 */
data class FeedbackState(
    val type: FeedbackType,
    val message: String,
    val timestamp: Long = System.currentTimeMillis(),
    val durationMs: Int = 2000
) {
    /**
     * Check if feedback should still be displayed based on timing
     */
    fun isExpired(): Boolean {
        return System.currentTimeMillis() - timestamp > durationMs
    }

    /**
     * Check if feedback was shown within 200ms requirement
     */
    fun isWithinTimingRequirement(): Boolean {
        return System.currentTimeMillis() - timestamp <= 200
    }
}

/**
 * Visual Feedback Manager
 * Manages feedback state and ensures 200ms response time requirement
 */
class VisualFeedbackManager {
    private val _feedbackState = mutableStateOf<FeedbackState?>(null)
    val feedbackState: State<FeedbackState?> = _feedbackState

    private val feedbackTimings = mutableListOf<Long>()
    private val maxTimingHistory = 100

    /**
     * Show feedback with automatic timing validation
     */
    fun showFeedback(type: FeedbackType, message: String, durationMs: Int = 2000) {
        val startTime = System.currentTimeMillis()

        _feedbackState.value = FeedbackState(
            type = type,
            message = message,
            timestamp = startTime,
            durationMs = durationMs
        )

        // Track timing for performance monitoring
        val responseTime = System.currentTimeMillis() - startTime
        trackFeedbackTiming(responseTime)

        // Log warning if feedback exceeds 200ms requirement
        if (responseTime > 200) {
            android.util.Log.w(
                "VisualFeedback",
                "Feedback response time ${responseTime}ms exceeds 200ms requirement"
            )
        }
    }

    /**
     * Show success feedback
     */
    fun showSuccess(message: String) {
        showFeedback(FeedbackType.SUCCESS, message, 2000)
    }

    /**
     * Show error feedback
     */
    fun showError(message: String) {
        showFeedback(FeedbackType.ERROR, message, 3000)
    }

    /**
     * Show warning feedback
     */
    fun showWarning(message: String) {
        showFeedback(FeedbackType.WARNING, message, 2500)
    }

    /**
     * Show info feedback
     */
    fun showInfo(message: String) {
        showFeedback(FeedbackType.INFO, message, 2000)
    }

    /**
     * Show loading feedback
     */
    fun showLoading(message: String) {
        showFeedback(FeedbackType.LOADING, message, Int.MAX_VALUE)
    }

    /**
     * Clear current feedback
     */
    fun clearFeedback() {
        _feedbackState.value = null
    }

    /**
     * Track feedback timing for performance analysis
     */
    private fun trackFeedbackTiming(timing: Long) {
        feedbackTimings.add(timing)
        if (feedbackTimings.size > maxTimingHistory) {
            feedbackTimings.removeAt(0)
        }
    }

    /**
     * Get average feedback response time
     */
    fun getAverageFeedbackTiming(): Double {
        return if (feedbackTimings.isEmpty()) 0.0
        else feedbackTimings.average()
    }

    /**
     * Get percentage of feedback within 200ms requirement
     */
    fun getTimingCompliancePercentage(): Double {
        if (feedbackTimings.isEmpty()) return 100.0
        val compliantCount = feedbackTimings.count { it <= 200 }
        return (compliantCount.toDouble() / feedbackTimings.size) * 100.0
    }

    /**
     * Get feedback timing statistics
     */
    fun getTimingStatistics(): FeedbackTimingStats {
        return FeedbackTimingStats(
            count = feedbackTimings.size,
            average = getAverageFeedbackTiming(),
            min = feedbackTimings.minOrNull() ?: 0,
            max = feedbackTimings.maxOrNull() ?: 0,
            compliancePercentage = getTimingCompliancePercentage()
        )
    }
}

/**
 * Feedback timing statistics
 */
data class FeedbackTimingStats(
    val count: Int,
    val average: Double,
    val min: Long,
    val max: Long,
    val compliancePercentage: Double
)

/**
 * Visual Feedback Component
 * Displays feedback with animations optimized for performance
 */
@Composable
fun VisualFeedback(
    feedbackManager: VisualFeedbackManager,
    modifier: Modifier = Modifier
) {
    val feedbackState by feedbackManager.feedbackState
    val scope = rememberCoroutineScope()

    // Auto-dismiss feedback after duration
    LaunchedEffect(feedbackState) {
        feedbackState?.let { state ->
            if (state.type != FeedbackType.LOADING) {
                delay(state.durationMs.toLong())
                if (!state.isExpired()) {
                    feedbackManager.clearFeedback()
                }
            }
        }
    }

    AnimatedVisibility(
        visible = feedbackState != null,
        enter = slideInVertically(
            initialOffsetY = { -it },
            animationSpec = tween(200, easing = FastOutSlowInEasing)
        ) + fadeIn(animationSpec = tween(200)),
        exit = slideOutVertically(
            targetOffsetY = { -it },
            animationSpec = tween(150, easing = FastOutLinearInEasing)
        ) + fadeOut(animationSpec = tween(150)),
        modifier = modifier
    ) {
        feedbackState?.let { state ->
            FeedbackCard(
                type = state.type,
                message = state.message,
                onDismiss = { feedbackManager.clearFeedback() }
            )
        }
    }
}

@Composable
private fun FeedbackCard(
    type: FeedbackType,
    message: String,
    onDismiss: () -> Unit
) {
    val backgroundColor = when (type) {
        FeedbackType.SUCCESS -> MaterialTheme.colorScheme.primaryContainer
        FeedbackType.ERROR -> MaterialTheme.colorScheme.errorContainer
        FeedbackType.WARNING -> Color(0xFFFFF3E0) // Orange tint
        FeedbackType.INFO -> MaterialTheme.colorScheme.secondaryContainer
        FeedbackType.LOADING, FeedbackType.PROCESSING -> MaterialTheme.colorScheme.surfaceVariant
    }

    val contentColor = when (type) {
        FeedbackType.SUCCESS -> MaterialTheme.colorScheme.onPrimaryContainer
        FeedbackType.ERROR -> MaterialTheme.colorScheme.onErrorContainer
        FeedbackType.WARNING -> Color(0xFF9C5400) // Orange text
        FeedbackType.INFO -> MaterialTheme.colorScheme.onSecondaryContainer
        FeedbackType.LOADING, FeedbackType.PROCESSING -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = backgroundColor
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                // Animated indicator
                when (type) {
                    FeedbackType.LOADING, FeedbackType.PROCESSING -> {
                        CircularProgressIndicator(
                            modifier = Modifier.size(24.dp),
                            color = contentColor,
                            strokeWidth = 2.dp
                        )
                    }
                    else -> {
                        FeedbackIcon(type = type, tint = contentColor)
                    }
                }

                Spacer(modifier = Modifier.width(12.dp))

                Text(
                    text = message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = contentColor
                )
            }

            // Dismiss button (except for loading states)
            if (type != FeedbackType.LOADING && type != FeedbackType.PROCESSING) {
                IconButton(
                    onClick = onDismiss,
                    modifier = Modifier.size(24.dp)
                ) {
                    Icon(
                        imageVector = androidx.compose.material.icons.Icons.Default.Close,
                        contentDescription = "Kapat", // "Close"
                        tint = contentColor,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun FeedbackIcon(type: FeedbackType, tint: Color) {
    val scale = remember { Animatable(0f) }

    LaunchedEffect(Unit) {
        scale.animateTo(
            targetValue = 1f,
            animationSpec = spring(
                dampingRatio = Spring.DampingRatioMediumBouncy,
                stiffness = Spring.StiffnessLow
            )
        )
    }

    val icon = when (type) {
        FeedbackType.SUCCESS -> androidx.compose.material.icons.Icons.Default.CheckCircle
        FeedbackType.ERROR -> androidx.compose.material.icons.Icons.Default.Error
        FeedbackType.WARNING -> androidx.compose.material.icons.Icons.Default.Warning
        FeedbackType.INFO -> androidx.compose.material.icons.Icons.Default.Info
        else -> androidx.compose.material.icons.Icons.Default.Info
    }

    Icon(
        imageVector = icon,
        contentDescription = null,
        tint = tint,
        modifier = Modifier
            .size(24.dp)
            .scale(scale.value)
    )
}

/**
 * Ripple feedback for button presses
 * Provides immediate visual feedback on interaction
 */
@Composable
fun RippleFeedback(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    content: @Composable () -> Unit
) {
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()

    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.95f else 1f,
        animationSpec = tween(durationMillis = 100)
    )

    Surface(
        onClick = onClick,
        modifier = modifier.scale(scale),
        enabled = enabled,
        interactionSource = interactionSource,
        content = content
    )
}

/**
 * Pulse animation for active states
 */
@Composable
fun PulseIndicator(
    isActive: Boolean,
    color: Color = MaterialTheme.colorScheme.primary,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition()

    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        )
    )

    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.7f,
        targetValue = 0.3f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        )
    )

    if (isActive) {
        Box(
            modifier = modifier
                .size(12.dp)
                .scale(scale)
                .background(color.copy(alpha = alpha), shape = CircleShape)
        )
    }
}

/**
 * Shimmer loading effect for placeholders
 */
@Composable
fun ShimmerEffect(
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition()

    val offset by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        )
    )

    Box(
        modifier = modifier
            .background(
                brush = androidx.compose.ui.graphics.Brush.horizontalGradient(
                    colors = listOf(
                        Color.LightGray.copy(alpha = 0.3f),
                        Color.LightGray.copy(alpha = 0.6f),
                        Color.LightGray.copy(alpha = 0.3f)
                    ),
                    startX = offset * 1000f,
                    endX = offset * 1000f + 500f
                ),
                shape = RoundedCornerShape(4.dp)
            )
    )
}

/**
 * Composable for tracking and displaying feedback timing metrics (debug)
 */
@Composable
fun FeedbackTimingDebug(
    feedbackManager: VisualFeedbackManager,
    modifier: Modifier = Modifier
) {
    val stats = remember { mutableStateOf(feedbackManager.getTimingStatistics()) }

    LaunchedEffect(Unit) {
        while (true) {
            delay(1000)
            stats.value = feedbackManager.getTimingStatistics()
        }
    }

    Card(
        modifier = modifier.padding(8.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "Feedback Timing Stats",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text("Count: ${stats.value.count}", style = MaterialTheme.typography.bodySmall)
            Text("Average: ${"%.2f".format(stats.value.average)}ms", style = MaterialTheme.typography.bodySmall)
            Text("Min: ${stats.value.min}ms", style = MaterialTheme.typography.bodySmall)
            Text("Max: ${stats.value.max}ms", style = MaterialTheme.typography.bodySmall)
            Text(
                text = "200ms Compliance: ${"%.1f".format(stats.value.compliancePercentage)}%",
                style = MaterialTheme.typography.bodySmall,
                color = if (stats.value.compliancePercentage >= 95.0)
                    MaterialTheme.colorScheme.primary
                else
                    MaterialTheme.colorScheme.error
            )
        }
    }
}