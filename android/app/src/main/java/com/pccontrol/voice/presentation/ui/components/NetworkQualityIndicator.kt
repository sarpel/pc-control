package com.pccontrol.voice.presentation.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Network quality levels matching Python NetworkMonitor
 */
enum class NetworkQuality(
    val displayName: String,
    val color: Color,
    val description: String
) {
    EXCELLENT(
        displayName = "Mükemmel",
        color = Color(0xFF4CAF50),
        description = "Ağ bağlantısı çok iyi"
    ),
    GOOD(
        displayName = "İyi",
        color = Color(0xFF8BC34A),
        description = "Ağ bağlantısı iyi"
    ),
    FAIR(
        displayName = "Orta",
        color = Color(0xFFFFC107),
        description = "Ağ bağlantısı orta seviyede"
    ),
    POOR(
        displayName = "Zayıf",
        color = Color(0xFFFF9800),
        description = "Ağ bağlantısı zayıf"
    ),
    CRITICAL(
        displayName = "Kritik",
        color = Color(0xFFF44336),
        description = "Ağ bağlantısı çok zayıf"
    );

    companion object {
        fun fromString(value: String): NetworkQuality {
            return values().find { it.name.equals(value, ignoreCase = true) } ?: FAIR
        }
    }
}

/**
 * Network metrics data class
 */
data class NetworkMetrics(
    val latencyMs: Float = 0f,
    val jitterMs: Float = 0f,
    val packetLossPercent: Float = 0f,
    val quality: NetworkQuality = NetworkQuality.FAIR,
    val connectionStable: Boolean = true
)

/**
 * Compact network quality indicator for header/status bar
 */
@Composable
fun NetworkQualityBadge(
    metrics: NetworkMetrics,
    modifier: Modifier = Modifier,
    showLabel: Boolean = true
) {
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        // Animated signal strength indicator
        SignalStrengthBars(quality = metrics.quality)

        if (showLabel) {
            Text(
                text = metrics.quality.displayName,
                fontSize = 12.sp,
                color = metrics.quality.color,
                fontWeight = FontWeight.Medium
            )
        }

        // Warning indicator for unstable connection
        if (!metrics.connectionStable) {
            Box(
                modifier = Modifier
                    .size(8.dp)
                    .background(Color(0xFFFFC107), CircleShape)
                    .then(Modifier.blinkingEffect())
            )
        }
    }
}

/**
 * Detailed network quality card with metrics
 */
@Composable
fun NetworkQualityCard(
    metrics: NetworkMetrics,
    modifier: Modifier = Modifier,
    onDismiss: (() -> Unit)? = null
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header with quality status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    SignalStrengthBars(quality = metrics.quality, size = 24.dp)

                    Column {
                        Text(
                            text = metrics.quality.displayName,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = metrics.quality.color
                        )
                        Text(
                            text = metrics.quality.description,
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                if (onDismiss != null) {
                    IconButton(onClick = onDismiss) {
                        Text("✕", fontSize = 20.sp)
                    }
                }
            }

            Divider()

            // Metrics details
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                NetworkMetricRow(
                    label = "Gecikme",
                    value = "${metrics.latencyMs.toInt()}ms",
                    progress = (metrics.latencyMs / 500f).coerceIn(0f, 1f),
                    isGood = metrics.latencyMs < 100
                )

                NetworkMetricRow(
                    label = "Jitter",
                    value = "${metrics.jitterMs.toInt()}ms",
                    progress = (metrics.jitterMs / 100f).coerceIn(0f, 1f),
                    isGood = metrics.jitterMs < 50
                )

                NetworkMetricRow(
                    label = "Paket Kaybı",
                    value = "${metrics.packetLossPercent.toInt()}%",
                    progress = metrics.packetLossPercent / 100f,
                    isGood = metrics.packetLossPercent < 5
                )
            }

            // Connection stability indicator
            if (!metrics.connectionStable) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(
                            Color(0xFFFFF3E0),
                            RoundedCornerShape(8.dp)
                        )
                        .padding(12.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("⚠️", fontSize = 16.sp)
                    Text(
                        text = "Bağlantı kararsız",
                        fontSize = 12.sp,
                        color = Color(0xFFE65100)
                    )
                }
            }
        }
    }
}

/**
 * Signal strength bars indicator
 */
@Composable
fun SignalStrengthBars(
    quality: NetworkQuality,
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = 16.dp
) {
    val barCount = when (quality) {
        NetworkQuality.EXCELLENT -> 4
        NetworkQuality.GOOD -> 3
        NetworkQuality.FAIR -> 2
        NetworkQuality.POOR -> 1
        NetworkQuality.CRITICAL -> 0
    }

    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(2.dp),
        verticalAlignment = Alignment.Bottom
    ) {
        repeat(4) { index ->
            val barHeight = (index + 1) * (size.value / 4).dp
            val isActive = index < barCount

            Box(
                modifier = Modifier
                    .width(size / 5)
                    .height(barHeight)
                    .background(
                        color = if (isActive) quality.color else Color.Gray.copy(alpha = 0.3f),
                        shape = RoundedCornerShape(1.dp)
                    )
            )
        }
    }
}

/**
 * Network metric row with progress bar
 */
@Composable
private fun NetworkMetricRow(
    label: String,
    value: String,
    progress: Float,
    isGood: Boolean
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = label,
                fontSize = 14.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = value,
                fontSize = 14.sp,
                fontWeight = FontWeight.Medium,
                color = if (isGood) Color(0xFF4CAF50) else Color(0xFFFF9800)
            )
        }

        LinearProgressIndicator(
            progress = progress,
            modifier = Modifier
                .fillMaxWidth()
                .height(4.dp),
            color = if (isGood) Color(0xFF4CAF50) else Color(0xFFFF9800),
            trackColor = MaterialTheme.colorScheme.surfaceVariant
        )
    }
}

/**
 * Inline network quality indicator for status updates
 */
@Composable
fun NetworkQualityInline(
    metrics: NetworkMetrics,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier
            .background(
                metrics.quality.color.copy(alpha = 0.1f),
                RoundedCornerShape(8.dp)
            )
            .padding(horizontal = 12.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        SignalStrengthBars(quality = metrics.quality, size = 14.dp)

        Text(
            text = "${metrics.latencyMs.toInt()}ms",
            fontSize = 12.sp,
            color = metrics.quality.color,
            fontWeight = FontWeight.Medium
        )

        if (metrics.packetLossPercent > 0) {
            Text(
                text = "•",
                fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = "${metrics.packetLossPercent.toInt()}% kayıp",
                fontSize = 12.sp,
                color = Color(0xFFFF9800)
            )
        }
    }
}

/**
 * Blinking effect modifier for attention-grabbing indicators
 */
@Composable
private fun Modifier.blinkingEffect(): Modifier {
    val infiniteTransition = rememberInfiniteTransition(label = "blink")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 0.2f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )

    return this.alpha(alpha)
}

/**
 * Network quality alert banner (shown at top when quality degrades)
 */
@Composable
fun NetworkQualityAlert(
    metrics: NetworkMetrics,
    visible: Boolean,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier
) {
    AnimatedVisibility(
        visible = visible && (metrics.quality == NetworkQuality.POOR ||
                             metrics.quality == NetworkQuality.CRITICAL),
        enter = fadeIn(),
        exit = fadeOut()
    ) {
        Card(
            modifier = modifier.fillMaxWidth(),
            colors = CardDefaults.cardColors(
                containerColor = metrics.quality.color.copy(alpha = 0.1f)
            ),
            shape = RoundedCornerShape(bottomStart = 12.dp, bottomEnd = 12.dp)
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text("⚠️", fontSize = 24.sp)

                    Column {
                        Text(
                            text = "Ağ kalitesi düşük",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = metrics.quality.color
                        )
                        Text(
                            text = "Komutlar yavaş çalışabilir",
                            fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                IconButton(onClick = onDismiss) {
                    Text("✕", fontSize = 18.sp)
                }
            }
        }
    }
}
