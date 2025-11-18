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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.pccontrol.voice.presentation.viewmodel.ConnectionStatusViewModel

/**
 * Connection status screen showing detailed connection information and settings.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConnectionStatusScreen(
    onNavigateBack: () -> Unit,
    viewModel: ConnectionStatusViewModel = hiltViewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Bağlantı Durumu") },
                navigationIcon = {
                    IconButton(onClick = onNavigateBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Geri")
                    }
                },
                actions = {
                    IconButton(onClick = viewModel::refreshStatus) {
                        Icon(Icons.Default.Refresh, contentDescription = "Yenile")
                    }
                }
            )
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Overall connection status
            ConnectionStatusCard(
                isConnected = uiState.isConnected,
                pcName = uiState.pcName,
                pcIpAddress = uiState.pcIpAddress,
                lastConnected = uiState.lastConnectedTime,
                modifier = Modifier.fillMaxWidth()
            )

            // Connection details
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        text = "Bağlantı Detayları",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium
                    )

                    DetailItem(
                        label = "PC Adı",
                        value = uiState.pcName ?: "Bilinmiyor"
                    )

                    DetailItem(
                        label = "IP Adresi",
                        value = uiState.pcIpAddress ?: "Bilinmiyor"
                    )

                    DetailItem(
                        label = "Gecikme",
                        value = "${uiState.latencyMs} ms"
                    )

                    DetailItem(
                        label = "Son Bağlantı",
                        value = formatTimestamp(uiState.lastConnectedTime)
                    )

                    DetailItem(
                        label = "Bağlantı Sayısı",
                        value = uiState.connectionCount.toString()
                    )
                }
            }

            // Paired devices
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Eşleştirilmiş Cihazlar",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Medium
                        )
                    }

                    if (uiState.pairedDevices.isNotEmpty()) {
                        uiState.pairedDevices.forEach { device ->
                            PairedDeviceItem(
                                deviceName = device.name,
                                deviceModel = device.model,
                                lastConnected = device.lastConnected,
                                onRemove = { viewModel.removeDevice(device.id) }
                            )
                        }
                    } else {
                        Text(
                            text = "Eşleştirilmiş cihaz bulunamadı",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            // Actions
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = "İşlemler",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium
                    )

                    if (uiState.isConnected) {
                        OutlinedButton(
                            onClick = viewModel::disconnect,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Default.Disconnect, contentDescription = null)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Bağlantıyı Kes")
                        }
                    }

                    Button(
                        onClick = viewModel::testConnection,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.NetworkCheck, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Bağlantıyı Test Et")
                    }

                    OutlinedButton(
                        onClick = viewModel::clearAllDevices,
                        modifier = Modifier.fillMaxWidth(),
                        colors = ButtonDefaults.outlinedButtonColors(
                            contentColor = MaterialTheme.colorScheme.error
                        )
                    ) {
                        Icon(Icons.Default.DeleteForever, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Tüm Cihazları Temizle")
                    }
                }
            }

            // Network information
            Card(
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    Text(
                        text = "Ağ Bilgileri",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium
                    )

                    DetailItem(
                        label = "Wi-Fi Ağı",
                        value = uiState.wifiNetworkName ?: "Bilinmiyor"
                    )

                    DetailItem(
                        label = "Sinyal Gücü",
                        value = uiState.signalStrength?.let { "%${it}" } ?: "Bilinmiyor"
                    )

                    DetailItem(
                        label = "Eşleştirme Yöntemi",
                        value = when (uiState.pairingMethod) {
                            "manual" -> "Manuel"
                            "qr" -> "QR Kod"
                            "nfc" -> "NFC"
                            else -> "Bilinmiyor"
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun ConnectionStatusCard(
    isConnected: Boolean,
    pcName: String?,
    pcIpAddress: String?,
    lastConnected: Long?,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = if (isConnected) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceVariant
            }
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Icon(
                imageVector = if (isConnected) {
                    Icons.Default.Wifi
                } else {
                    Icons.Default.WifiOff
                },
                contentDescription = null,
                modifier = Modifier.size(48.dp),
                tint = if (isConnected) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                }
            )

            Text(
                text = if (isConnected) "PC Bağlandı" else "PC Bağlı Değil",
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Medium
            )

            if (isConnected && pcName != null) {
                Text(
                    text = pcName,
                    style = MaterialTheme.typography.bodyLarge
                )
            }

            if (isConnected && pcIpAddress != null) {
                Text(
                    text = pcIpAddress,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            if (lastConnected != null) {
                Text(
                    text = "Son bağlantı: ${formatTimestamp(lastConnected)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun DetailItem(
    label: String,
    value: String
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun PairedDeviceItem(
    deviceName: String,
    deviceModel: String,
    lastConnected: Long,
    onRemove: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
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
                    text = deviceName,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = deviceModel,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = "Son bağlantı: ${formatTimestamp(lastConnected)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            IconButton(onClick = onRemove) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Kaldır",
                    tint = MaterialTheme.colorScheme.error
                )
            }
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