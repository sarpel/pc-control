package com.pccontrol.voice.presentation.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pccontrol.voice.R
import com.pccontrol.voice.presentation.ui.components.PairingCodeCard
import com.pccontrol.voice.presentation.viewmodel.DevicePairingViewModel

/**
 * Device pairing screen for establishing secure connection with PC.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DevicePairingScreen(
    onNavigateBack: () -> Unit,
    viewModel: DevicePairingViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Cihaz Eşleştirme") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Geri")
                    }
                }
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Instructions
            Text(
                text = "PC'nizle güvenli bağlantı kurmak için aşağıdaki adımları izleyin:",
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium
            )

            // Step 1
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Numbers,
                            contentDescription = null,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "1. PC Agent'i Başlatın",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                    Text(
                        text = "PC'nizde PC Voice Controller uygulamasını açın ve eşleştirme modunu başlatın.",
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            // Step 2
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.QrCodeScanner,
                            contentDescription = null,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "2. Eşleştirme Kodunu Girin",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }
                    Text(
                        text = "PC ekranında görünen 6 haneli eşleştirme kodunu girin:",
                        style = MaterialTheme.typography.bodyMedium
                    )

                    // Pairing code input
                    OutlinedTextField(
                        value = uiState.pairingCode,
                        onValueChange = viewModel::updatePairingCode,
                        label = { Text("Eşleştirme Kodu") },
                        placeholder = { Text("123456") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                        isError = uiState.pairingCodeError != null,
                        supportingText = uiState.pairingCodeError?.let {
                            { Text(it) }
                        }
                    )
                }
            }

            // Step 3 - Show pairing code if initiated
            val pairingCode = uiState.generatedPairingCode
            if (uiState.showPairingCode && pairingCode != null) {
                PairingCodeCard(
                    pairingCode = pairingCode,
                    onCopyCode = viewModel::copyPairingCode,
                    modifier = Modifier.fillMaxWidth()
                )
            }

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = viewModel::generatePairingCode,
                    modifier = Modifier.weight(1f),
                    enabled = !uiState.isLoading
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            strokeWidth = 2.dp
                        )
                    } else {
                        Text("Kod Oluştur")
                    }
                }

                Button(
                    onClick = viewModel::startPairing,
                    modifier = Modifier.weight(1f),
                    enabled = uiState.pairingCode.length == 6 && !uiState.isLoading
                ) {
                    if (uiState.isLoading) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                    } else {
                        Text("Eşleştir")
                    }
                }
            }

            // Status message
            if (uiState.statusMessage.isNotEmpty()) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = if (uiState.isError) {
                            MaterialTheme.colorScheme.errorContainer
                        } else {
                            MaterialTheme.colorScheme.primaryContainer
                        }
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = if (uiState.isError) {
                                Icons.Default.Error
                            } else {
                                Icons.Default.Info
                            },
                            contentDescription = null,
                            tint = if (uiState.isError) {
                                MaterialTheme.colorScheme.error
                            } else {
                                MaterialTheme.colorScheme.primary
                            }
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = uiState.statusMessage,
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }

            // Help section
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Help,
                            contentDescription = null,
                            modifier = Modifier.size(24.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Yardım",
                            style = MaterialTheme.typography.titleMedium
                        )
                    }

                    Text(
                        text = "• Eşleştirme kodu 10 dakika boyunca geçerlidir\n" +
                              "• Her iki cihazın aynı Wi-Fi ağına bağlı olduğundan emin olun\n" +
                              "• Kod girildikten sonra PC'de onay gerekebilir",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}