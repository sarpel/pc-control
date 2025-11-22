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

            // Step 1: Enter IP Address
            if (!uiState.isInitiated) {
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
                                Icons.Default.Computer,
                                contentDescription = null,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "1. PC IP Adresini Girin",
                                style = MaterialTheme.typography.titleMedium
                            )
                        }
                        Text(
                            text = "PC'nizin IP adresini girin (örn: 192.168.1.100)",
                            style = MaterialTheme.typography.bodyMedium
                        )

                        OutlinedTextField(
                            value = uiState.ipAddress,
                            onValueChange = viewModel::updateIpAddress,
                            label = { Text("IP Adresi") },
                            placeholder = { Text("192.168.1.x") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )

                        Button(
                            onClick = viewModel::initiatePairing,
                            modifier = Modifier.fillMaxWidth(),
                            enabled = uiState.ipAddress.isNotBlank() && !uiState.isLoading
                        ) {
                            if (uiState.isLoading) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(20.dp),
                                    strokeWidth = 2.dp,
                                    color = MaterialTheme.colorScheme.onPrimary
                                )
                            } else {
                                Text("Bağlan ve Kod İste")
                            }
                        }
                    }
                }
            }

            // Step 2: Enter Pairing Code (Only visible after initiation)
            if (uiState.isInitiated) {
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
                            text = "PC loglarında görünen 6 haneli eşleştirme kodunu girin:",
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

                        Button(
                            onClick = viewModel::startPairing,
                            modifier = Modifier.fillMaxWidth(),
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