package com.pccontrol.voice.presentation.ui.main

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.fragment.app.Fragment
import androidx.fragment.app.viewModels
import kotlinx.coroutines.launch
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pccontrol.voice.presentation.viewmodel.CommandStatusViewModel
import com.pccontrol.voice.presentation.viewmodel.ConnectionState
import com.pccontrol.voice.data.repository.CommandStatus
import com.pccontrol.voice.data.repository.VoiceCommand

/**
 * Command Status Fragment
 *
 * Displays real-time voice command status and command history.
 */
class CommandStatusFragment : Fragment() {

    private val viewModel: CommandStatusViewModel by viewModels()

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        return ComposeView(requireContext()).apply {
            setContent {
                CommandStatusScreen(
                    viewModel = viewModel,
                    onRetryConnection = { viewModel.retryConnection() },
                    onClearHistory = { viewModel.clearCommandHistory() },
                    onClose = { /* Handle close if needed */ }
                )
            }
        }
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        // Observe command updates and provide haptic feedback
        viewLifecycleOwner.lifecycleScope.launch {
            viewModel.commandStatusFlow.collect { status ->
                // Provide haptic feedback for status changes
                when (status) {
                    CommandStatus.LISTENING -> {
                        // Subtle vibration for listening start
                    }
                    CommandStatus.PROCESSING -> {
                        // Light pulse for processing
                    }
                    CommandStatus.COMPLETED -> {
                        // Success vibration pattern
                    }
                    CommandStatus.ERROR -> {
                        // Error vibration pattern
                    }
                    else -> { /* No feedback */ }
                }
            }
        }
    }
}

/**
 * Main Compose screen for command status display
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CommandStatusScreen(
    viewModel: CommandStatusViewModel,
    onRetryConnection: () -> Unit,
    onClearHistory: () -> Unit,
    onClose: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val recentCommands by viewModel.recentCommands.collectAsStateWithLifecycle(initialValue = emptyList())

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
        ) {
            // Header with connection status
            ConnectionStatusHeader(
                connectionState = uiState.connectionState,
                onRetryConnection = onRetryConnection
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Main status display
            CommandStatusDisplay(
                commandStatus = uiState.commandStatus,
                currentCommand = uiState.currentCommand
            )

            Spacer(modifier = Modifier.height(24.dp))

            // Voice activity indicator
            if (uiState.commandStatus == CommandStatus.LISTENING) {
                VoiceActivityIndicator(
                    audioLevel = uiState.audioLevel,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(24.dp))
            }

            // Error display
            if (uiState.errorMessage != null) {
                ErrorDisplay(
                    errorMessage = uiState.errorMessage,
                    onRetryConnection = onRetryConnection,
                    modifier = Modifier.fillMaxWidth()
                )
                Spacer(modifier = Modifier.height(24.dp))
            }

            // Command history
            CommandHistorySection(
                commands = recentCommands,
                onClearHistory = onClearHistory,
                modifier = Modifier.weight(1f)
            )

            // Action buttons
            ActionButtons(
                isListening = uiState.commandStatus == CommandStatus.LISTENING,
                onStartListening = { viewModel.startListening() },
                onStopListening = { viewModel.stopListening() },
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

/**
 * Connection status header component
 */
@Composable
fun ConnectionStatusHeader(
    connectionState: ConnectionState,
    onRetryConnection: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = when (connectionState) {
                ConnectionState.Connected -> Color(0xFFE8F5E8)
                ConnectionState.Connecting -> Color(0xFFFFF4E6)
                ConnectionState.Error -> Color(0xFFFFEBEE)
                else -> Color(0xFFF5F5F5)
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "PC Bağlantısı", // "PC Connection" in Turkish
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = connectionState.displayName,
                    style = MaterialTheme.typography.bodyMedium,
                    color = when (connectionState) {
                        ConnectionState.Connected -> Color(0xFF2E7D32)
                        ConnectionState.Connecting -> Color(0xFFF57C00)
                        ConnectionState.Error -> Color(0xFFD32F2F)
                        else -> MaterialTheme.colorScheme.onSurfaceVariant
                    }
                )
            }

            Icon(
                imageVector = when (connectionState) {
                    ConnectionState.Connected -> Icons.Default.Wifi
                    ConnectionState.Connecting -> Icons.Default.Refresh
                    ConnectionState.Error -> Icons.Default.Error
                    else -> Icons.Default.WifiOff
                },
                contentDescription = connectionState.displayName,
                tint = when (connectionState) {
                    ConnectionState.Connected -> Color(0xFF2E7D32)
                    ConnectionState.Connecting -> Color(0xFFF57C00)
                    ConnectionState.Error -> Color(0xFFD32F2F)
                    else -> MaterialTheme.colorScheme.onSurfaceVariant
                }
            )

            if (connectionState == ConnectionState.Error) {
                Spacer(modifier = Modifier.width(8.dp))
                IconButton(onClick = onRetryConnection) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Yeniden Dene" // "Retry" in Turkish
                    )
                }
            }
        }
    }
}

/**
 * Main command status display component
 */
@Composable
fun CommandStatusDisplay(
    commandStatus: CommandStatus?,
    currentCommand: VoiceCommand?
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Status icon
            Box(
                modifier = Modifier
                    .size(80.dp)
                    .clip(CircleShape)
                    .background(
                        when (commandStatus) {
                            CommandStatus.LISTENING -> Color(0xFF2196F3)
                            CommandStatus.PROCESSING -> Color(0xFFFF9800)
                            CommandStatus.COMPLETED -> Color(0xFF4CAF50)
                            CommandStatus.ERROR -> Color(0xFFF44336)
                            else -> Color(0xFF9E9E9E) // Idle or other
                        }
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = when (commandStatus) {
                        CommandStatus.LISTENING -> Icons.Default.Mic
                        CommandStatus.PROCESSING -> Icons.Default.Settings
                        CommandStatus.COMPLETED -> Icons.Default.CheckCircle
                        CommandStatus.ERROR -> Icons.Default.Error
                        else -> Icons.Default.MicNone // Idle
                    },
                    contentDescription = commandStatus?.displayName ?: "Hazır",
                    tint = Color.White,
                    modifier = Modifier.size(40.dp)
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Status text
            Text(
                text = commandStatus?.displayName ?: "Hazır",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center
            )

            // Current command text
            currentCommand?.let { command ->
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "\"${command.transcribedText}\"",
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                if (command.confidenceScore > 0) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "Güven: ${(command.confidenceScore * 100).toInt()}%", // "Confidence: X%" in Turkish
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

/**
 * Voice activity indicator with animated visualization
 */
@Composable
fun VoiceActivityIndicator(
    audioLevel: Float,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFE3F2FD)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "Ses Seviyesi", // "Audio Level" in Turkish
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Audio level bars
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.Bottom
            ) {
                repeat(7) { index ->
                    val height = (audioLevel * 60 * (1 - index * 0.1)).coerceAtLeast(4.dp)

                    Box(
                        modifier = Modifier
                            .width(8.dp)
                            .height(height)
                            .clip(RoundedCornerShape(4.dp))
                            .background(
                                if (audioLevel > 0.1f) Color(0xFF2196F3)
                                else Color(0xFFE0E0E0)
                            )
                    )
                }
            }
        }
    }
}

/**
 * Error display component
 */
@Composable
fun ErrorDisplay(
    errorMessage: String,
    onRetryConnection: () -> Unit,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = Color(0xFFFFEBEE)
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Error,
                    contentDescription = "Hata", // "Error" in Turkish
                    tint = Color(0xFFD32F2F)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = "Hata Oluştu", // "Error Occurred" in Turkish
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = Color(0xFFD32F2F)
                )
            }

            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = errorMessage,
                style = MaterialTheme.typography.bodyMedium,
                color = Color(0xFFD32F2F)
            )

            Spacer(modifier = Modifier.height(12.dp))
            Button(
                onClick = onRetryConnection,
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFD32F2F)
                )
            ) {
                Text("Yeniden Dene") // "Retry" in Turkish
            }
        }
    }
}

/**
 * Command history section component
 */
@Composable
fun CommandHistorySection(
    commands: List<VoiceCommand>,
    onClearHistory: () -> Unit,
    modifier: Modifier = Modifier
) {
    if (commands.isEmpty()) {
        return
    }

    Card(
        modifier = modifier
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Komut Geçmişi", // "Command History" in Turkish
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )

                TextButton(onClick = onClearHistory) {
                    Text("Temizle") // "Clear" in Turkish
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.height(200.dp) // Limit height for performance
            ) {
                items(commands) { command ->
                    CommandHistoryItem(command = command)
                }
            }
        }
    }
}

/**
 * Individual command history item component
 */
@Composable
fun CommandHistoryItem(command: VoiceCommand) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = when (command.status) {
                CommandStatus.COMPLETED -> Icons.Default.CheckCircle
                CommandStatus.ERROR -> Icons.Default.Error
                else -> Icons.Default.History
            },
            contentDescription = null,
            tint = when (command.status) {
                CommandStatus.COMPLETED -> Color(0xFF4CAF50)
                CommandStatus.ERROR -> Color(0xFFF44336)
                else -> Color(0xFF9E9E9E)
            },
            modifier = Modifier.size(20.dp)
        )

        Spacer(modifier = Modifier.width(12.dp))

        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = command.transcribedText,
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 1
            )

            command.actionSummary?.let { summary ->
                Text(
                    text = summary,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Text(
            text = formatCommandTime(command.timestamp.toEpochMilli()), // Fix: Convert Instant to long if needed
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

/**
 * Action buttons component
 */
@Composable
fun ActionButtons(
    isListening: Boolean,
    onStartListening: () -> Unit,
    onStopListening: () -> Unit,
    modifier: Modifier = Modifier
) {
    Row(
        modifier = modifier,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        if (isListening) {
            Button(
                onClick = onStopListening,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFFF44336)
                )
            ) {
                Icon(
                    imageVector = Icons.Default.Stop,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Dinlemeyi Durdur") // "Stop Listening" in Turkish
            }
        } else {
            Button(
                onClick = onStartListening,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Color(0xFF2196F3)
                )
            ) {
                Icon(
                    imageVector = Icons.Default.Mic,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Komut Dinle") // "Listen for Command" in Turkish
            }
        }
    }
}

/**
 * Helper function to format command timestamp
 */
private fun formatCommandTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp

    return when {
        diff < 60000 -> "Az önce" // "Just now"
        diff < 3600000 -> "${diff / 60000} dk önce" // "X minutes ago"
        else -> "${diff / 3600000} saat önce" // "X hours ago"
    }
}
