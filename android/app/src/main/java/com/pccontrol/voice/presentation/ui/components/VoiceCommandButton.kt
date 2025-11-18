package com.pccontrol.voice.presentation.ui.components

import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Voice command button with visual feedback for recording state.
 */
@Composable
fun VoiceCommandButton(
    isListening: Boolean,
    voiceLevel: Float,
    transcription: String,
    onStartListening: () -> Unit,
    onStopListening: () -> Unit,
    modifier: Modifier = Modifier
) {
    var pulseAnimation by remember { mutableStateOf(1f) }

    LaunchedEffect(isListening) {
        if (isListening) {
            while (true) {
                pulseAnimation = 1f + (0.1f * kotlin.math.sin(System.currentTimeMillis() * 0.005))
                delay(50)
            }
        } else {
            pulseAnimation = 1f
        }
    }

    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Box(
            contentAlignment = Alignment.Center
        ) {
            // Voice level visualization
            if (isListening) {
                VoiceLevelVisualizer(
                    voiceLevel = voiceLevel,
                    modifier = Modifier.size(250.dp)
                )
            }

            // Main button
            FloatingActionButton(
                onClick = if (isListening) onStopListening else onStartListening,
                modifier = Modifier
                    .size(120.dp)
                    .scale(pulseAnimation),
                containerColor = if (isListening) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.primary
                },
                contentColor = MaterialTheme.colorScheme.onPrimary
            ) {
                Icon(
                    imageVector = if (isListening) {
                        Icons.Default.Stop
                    } else {
                        Icons.Default.Mic
                    },
                    contentDescription = if (isListening) {
                        "Dinlemeyi Durdur"
                    } else {
                        "Dinlemeye Başla"
                    },
                    modifier = Modifier.size(36.dp)
                )
            }
        }

        // Status text
        Text(
            text = if (isListening) "Dinleniyor..." else "Konuşun",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Medium,
            color = if (isListening) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.primary
            }
        )

        // Transcription display
        AnimatedVisibility(
            visible = transcription.isNotEmpty(),
            enter = fadeIn() + slideInVertically(),
            exit = fadeOut() + slideOutVertically()
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer
                )
            ) {
                Text(
                    text = transcription,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center
                )
            }
        }
    }
}

/**
 * Visualizer for voice level display during recording.
 */
@Composable
private fun VoiceLevelVisualizer(
    voiceLevel: Float,
    modifier: Modifier = Modifier
) {
    val animatedLevel by animateFloatAsState(
        targetValue = voiceLevel,
        animationSpec = tween(100)
    )

    Canvas(modifier = modifier) {
        val centerX = size.width / 2
        val centerY = size.height / 2
        val maxRadius = size.width / 2
        val baseRadius = maxRadius * 0.6f

        // Draw concentric circles based on voice level
        val circles = (1..5).map { i ->
            val progress = i / 5f
            val threshold = animatedLevel * 0.8f
            val isActive = progress <= threshold

            Triple(
                radius = baseRadius + (maxRadius - baseRadius) * progress,
                color = when {
                    progress < 0.3f -> Color.Green
                    progress < 0.6f -> Color.Yellow
                    else -> Color.Red
                },
                alpha = if (isActive) 1f - (1f - progress) * 0.7f else 0.1f
            )
        }

        circles.forEach { (radius, color, alpha) ->
            drawCircle(
                color = color.copy(alpha = alpha),
                radius = radius,
                center = Offset(centerX, centerY),
                style = Stroke(width = 4.dp.toPx(), cap = StrokeCap.Round)
            )
        }
    }
}