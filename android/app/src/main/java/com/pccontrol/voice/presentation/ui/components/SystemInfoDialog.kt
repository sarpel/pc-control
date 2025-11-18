package com.pccontrol.voice.presentation.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

/**
 * System Info Dialog
 *
 * Displays system information from the PC including CPU, memory, disk, and OS details.
 * Shows formatted system data in a readable card-based layout.
 *
 * Task: T076 [P] [US3] Create system command UI components in
 * android/app/src/main/java/com/pccontrol/voice/presentation/ui/components/SystemInfoDialog.kt
 */
@Composable
fun SystemInfoDialog(
    systemInfo: SystemInfo,
    onDismiss: () -> Unit
) {
    val scrollState = rememberScrollState()

    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            dismissOnBackPress = true,
            dismissOnClickOutside = true,
            usePlatformDefaultWidth = false
        )
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth(0.95f)
                .fillMaxHeight(0.85f),
            shape = RoundedCornerShape(16.dp),
            tonalElevation = 8.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.surface)
            ) {
                // Header
                SystemInfoHeader(
                    pcName = systemInfo.pcName,
                    onClose = onDismiss
                )

                Divider()

                // Content
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(scrollState)
                        .padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    // OS Information
                    SystemInfoCard(
                        title = "İşletim Sistemi", // "Operating System"
                        icon = Icons.Default.Computer,
                        items = listOf(
                            "İşletim Sistemi" to systemInfo.osName, // "Operating System"
                            "Sürüm" to systemInfo.osVersion, // "Version"
                            "Mimari" to systemInfo.osArchitecture, // "Architecture"
                            "Çalışma Süresi" to formatUptime(systemInfo.uptimeSeconds) // "Uptime"
                        )
                    )

                    // CPU Information
                    SystemInfoCard(
                        title = "İşlemci", // "Processor"
                        icon = Icons.Default.Computer,
                        items = listOf(
                            "Model" to systemInfo.cpuModel, // "Model"
                            "Çekirdek Sayısı" to systemInfo.cpuCores.toString(), // "Core Count"
                            "Kullanım" to "${systemInfo.cpuUsagePercent}%", // "Usage"
                            "Frekans" to "${systemInfo.cpuFrequencyMhz} MHz" // "Frequency"
                        )
                    )

                    // Memory Information
                    SystemInfoCard(
                        title = "Bellek", // "Memory"
                        icon = Icons.Default.Memory,
                        items = listOf(
                            "Toplam RAM" to formatBytes(systemInfo.totalMemoryBytes), // "Total RAM"
                            "Kullanılan" to formatBytes(systemInfo.usedMemoryBytes), // "Used"
                            "Boş" to formatBytes(systemInfo.freeMemoryBytes), // "Free"
                            "Kullanım Oranı" to "${systemInfo.memoryUsagePercent}%" // "Usage Percentage"
                        )
                    )

                    // Disk Information
                    SystemInfoCard(
                        title = "Disk", // "Disk"
                        icon = Icons.Default.Storage,
                        items = listOf(
                            "Toplam Alan" to formatBytes(systemInfo.totalDiskBytes), // "Total Space"
                            "Kullanılan" to formatBytes(systemInfo.usedDiskBytes), // "Used"
                            "Boş" to formatBytes(systemInfo.freeDiskBytes), // "Free"
                            "Kullanım Oranı" to "${systemInfo.diskUsagePercent}%" // "Usage Percentage"
                        )
                    )

                    // Network Information
                    if (systemInfo.networkInterfaces.isNotEmpty()) {
                        SystemInfoCard(
                            title = "Ağ Arabirimleri", // "Network Interfaces"
                            icon = Icons.Default.Computer,
                            items = systemInfo.networkInterfaces.map { iface ->
                                iface.name to iface.ipAddress
                            }
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SystemInfoHeader(
    pcName: String,
    onClose: () -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(16.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = "Sistem Bilgileri", // "System Information"
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                text = pcName,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f)
            )
        }

        IconButton(onClick = onClose) {
            Icon(
                imageVector = Icons.Default.Close,
                contentDescription = "Kapat", // "Close"
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun SystemInfoCard(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    items: List<Pair<String, String>>
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // Card title
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(20.dp)
                )
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Divider(modifier = Modifier.padding(vertical = 4.dp))

            // Card items
            items.forEach { (label, value) ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = label,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                        modifier = Modifier.weight(1f)
                    )
                    Text(
                        text = value,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

/**
 * System Info data class
 */
data class SystemInfo(
    val pcName: String,
    val osName: String,
    val osVersion: String,
    val osArchitecture: String,
    val uptimeSeconds: Long,
    val cpuModel: String,
    val cpuCores: Int,
    val cpuUsagePercent: Int,
    val cpuFrequencyMhz: Int,
    val totalMemoryBytes: Long,
    val usedMemoryBytes: Long,
    val freeMemoryBytes: Long,
    val memoryUsagePercent: Int,
    val totalDiskBytes: Long,
    val usedDiskBytes: Long,
    val freeDiskBytes: Long,
    val diskUsagePercent: Int,
    val networkInterfaces: List<NetworkInterface>
) {
    companion object {
        fun fromMap(data: Map<String, Any>): SystemInfo {
            @Suppress("UNCHECKED_CAST")
            return SystemInfo(
                pcName = data["pc_name"] as? String ?: "Bilinmiyor", // "Unknown"
                osName = data["os_name"] as? String ?: "Bilinmiyor",
                osVersion = data["os_version"] as? String ?: "Bilinmiyor",
                osArchitecture = data["os_architecture"] as? String ?: "Bilinmiyor",
                uptimeSeconds = (data["uptime_seconds"] as? Number)?.toLong() ?: 0L,
                cpuModel = data["cpu_model"] as? String ?: "Bilinmiyor",
                cpuCores = (data["cpu_cores"] as? Number)?.toInt() ?: 0,
                cpuUsagePercent = (data["cpu_usage_percent"] as? Number)?.toInt() ?: 0,
                cpuFrequencyMhz = (data["cpu_frequency_mhz"] as? Number)?.toInt() ?: 0,
                totalMemoryBytes = (data["total_memory_bytes"] as? Number)?.toLong() ?: 0L,
                usedMemoryBytes = (data["used_memory_bytes"] as? Number)?.toLong() ?: 0L,
                freeMemoryBytes = (data["free_memory_bytes"] as? Number)?.toLong() ?: 0L,
                memoryUsagePercent = (data["memory_usage_percent"] as? Number)?.toInt() ?: 0,
                totalDiskBytes = (data["total_disk_bytes"] as? Number)?.toLong() ?: 0L,
                usedDiskBytes = (data["used_disk_bytes"] as? Number)?.toLong() ?: 0L,
                freeDiskBytes = (data["free_disk_bytes"] as? Number)?.toLong() ?: 0L,
                diskUsagePercent = (data["disk_usage_percent"] as? Number)?.toInt() ?: 0,
                networkInterfaces = (data["network_interfaces"] as? List<Map<String, Any>>)
                    ?.mapNotNull { NetworkInterface.fromMap(it) } ?: emptyList()
            )
        }
    }
}

/**
 * Network Interface data class
 */
data class NetworkInterface(
    val name: String,
    val ipAddress: String
) {
    companion object {
        fun fromMap(data: Map<String, Any>): NetworkInterface? {
            val name = data["name"] as? String ?: return null
            val ipAddress = data["ip_address"] as? String ?: return null
            return NetworkInterface(name, ipAddress)
        }
    }
}

/**
 * Format bytes to human-readable string
 */
private fun formatBytes(bytes: Long): String {
    val units = arrayOf("B", "KB", "MB", "GB", "TB")
    var size = bytes.toDouble()
    var unitIndex = 0

    while (size >= 1024 && unitIndex < units.size - 1) {
        size /= 1024
        unitIndex++
    }

    return "%.2f %s".format(size, units[unitIndex])
}

/**
 * Format uptime seconds to human-readable string
 */
private fun formatUptime(seconds: Long): String {
    val days = seconds / 86400
    val hours = (seconds % 86400) / 3600
    val minutes = (seconds % 3600) / 60

    return buildString {
        if (days > 0) append("$days gün ") // "days"
        if (hours > 0) append("$hours saat ") // "hours"
        if (minutes > 0) append("$minutes dakika") // "minutes"
    }.trim().ifEmpty { "Az önce başlatıldı" } // "Just started"
}

/**
 * Loading state for system info
 */
@Composable
fun SystemInfoLoadingDialog(onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(
            dismissOnBackPress = true,
            dismissOnClickOutside = false
        )
    ) {
        Surface(
            shape = RoundedCornerShape(16.dp),
            tonalElevation = 8.dp
        ) {
            Column(
                modifier = Modifier
                    .padding(24.dp)
                    .widthIn(min = 280.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                CircularProgressIndicator()
                Text(
                    text = "Sistem bilgileri alınıyor...", // "Fetching system information..."
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

/**
 * Error state for system info
 */
@Composable
fun SystemInfoErrorDialog(
    errorMessage: String,
    onDismiss: () -> Unit,
    onRetry: (() -> Unit)? = null
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(
                imageVector = Icons.Default.Close,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error
            )
        },
        title = {
            Text("Bilgi Alınamadı") // "Could Not Fetch Information"
        },
        text = {
            Text(
                text = errorMessage,
                style = MaterialTheme.typography.bodyMedium
            )
        },
        confirmButton = {
            if (onRetry != null) {
                TextButton(onClick = onRetry) {
                    Text("Tekrar Dene") // "Retry"
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Tamam") // "OK"
            }
        }
    )
}
