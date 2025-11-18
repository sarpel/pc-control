package com.pccontrol.voice.presentation.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pccontrol.voice.R
import com.pccontrol.voice.presentation.ui.components.VoiceCommandButton
import com.pccontrol.voice.presentation.ui.components.ConnectionStatusCard
import com.pccontrol.voice.presentation.viewmodel.VoiceCommandViewModel

/**
 * Main voice command screen for interacting with the PC.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoiceCommandScreen(
    onNavigateToPairing: () -> Unit,
    onNavigateToConnectionStatus: () -> Unit,
    viewModel: VoiceCommandViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.initialize()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Top bar
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineMedium
            )

            IconButton(onClick = onNavigateToConnectionStatus) {
                Icon(Icons.Default.Settings, contentDescription = "Connection Status")
            }
        }

        // Connection status card
        ConnectionStatusCard(
            isConnected = uiState.isConnected,
            pcName = uiState.connectedPcName,
            onPairDevice = onNavigateToPairing,
            modifier = Modifier.fillMaxWidth()
        )

        // Voice command button
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f),
            contentAlignment = Alignment.Center
        ) {
            VoiceCommandButton(
                isListening = uiState.isListening,
                voiceLevel = uiState.voiceLevel,
                transcription = uiState.currentTranscription,
                onStartListening = viewModel::startListening,
                onStopListening = viewModel::stopListening,
                modifier = Modifier.size(200.dp)
            )
        }

        // Recent commands
        if (uiState.recentCommands.isNotEmpty()) {
            Text(
                text = "Son Komutlar",
                style = MaterialTheme.typography.titleMedium
            )

            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(uiState.recentCommands) { command ->
                    CommandHistoryItem(
                        transcription = command.transcription,
                        success = command.success,
                        timestamp = command.timestamp
                    )
                }
            }
        }

        // Status message
        if (uiState.statusMessage.isNotEmpty()) {
            Text(
                text = uiState.statusMessage,
                style = MaterialTheme.typography.bodyMedium,
                textAlign = TextAlign.Center,
                color = if (uiState.isError) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onSurface
                },
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
private fun CommandHistoryItem(
    transcription: String,
    success: Boolean,
    timestamp: Long
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (success) {
                MaterialTheme.colorScheme.surfaceVariant
            } else {
                MaterialTheme.colorScheme.errorContainer
            }
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = transcription,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2
                )
                Text(
                    text = formatTimestamp(timestamp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Icon(
                imageVector = if (success) Icons.Default.CheckCircle else Icons.Default.Error,
                contentDescription = if (success) "Success" else "Failed",
                tint = if (success) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.error
                }
            )
        }
    }
}

private fun formatTimestamp(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp

    return when {
        diff < 60_000 -> "Az önce"
        diff < 3_600_000 -> "${diff / 60_000} dakika önce"
        diff < 86_400_000 -> "${diff / 3_600_000} saat önce"
        else -> "${diff / 86_400_000} gün önce"
    }
}