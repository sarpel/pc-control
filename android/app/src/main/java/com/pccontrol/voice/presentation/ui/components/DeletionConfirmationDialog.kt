package com.pccontrol.voice.presentation.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import java.io.File

/**
 * Deletion Confirmation Dialog
 *
 * Displays a confirmation dialog for file/folder deletion operations.
 * Shows file details and requires explicit user confirmation before deletion.
 *
 * Task: T077 [US3] Implement file deletion confirmation dialog in Android in
 * android/app/src/main/java/com/pccontrol/voice/presentation/ui/components/DeletionConfirmationDialog.kt
 */
@Composable
fun DeletionConfirmationDialog(
    filePath: String,
    fileSize: Long? = null,
    isDirectory: Boolean = false,
    isSystemProtected: Boolean = false,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    var userConfirmed by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = onCancel,
        icon = {
            Icon(
                imageVector = if (isSystemProtected) Icons.Default.Warning else Icons.Default.Delete,
                contentDescription = null,
                tint = if (isSystemProtected)
                    MaterialTheme.colorScheme.error
                else
                    MaterialTheme.colorScheme.primary
            )
        },
        title = {
            Text(
                text = if (isSystemProtected)
                    "Korumalı Klasör" // "Protected Folder"
                else if (isDirectory)
                    "Klasörü Sil" // "Delete Folder"
                else
                    "Dosyayı Sil", // "Delete File"
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column(
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                if (isSystemProtected) {
                    // Warning for system-protected directories
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer
                        ),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "⚠️ DİKKAT",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                            Text(
                                text = "Bu dosya/klasör sistem tarafından korunmaktadır. Silme işlemi sistem kararsızlığına neden olabilir.",
                                // "This file/folder is protected by the system. Deletion may cause system instability."
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                        }
                    }
                }

                // File information
                Text(
                    text = if (isDirectory)
                        "Bu klasörü silmek istediğinizden emin misiniz?" // "Are you sure you want to delete this folder?"
                    else
                        "Bu dosyayı silmek istediğinizden emin misiniz?", // "Are you sure you want to delete this file?"
                    style = MaterialTheme.typography.bodyLarge
                )

                // File path
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp)
                    ) {
                        Text(
                            text = "Konum:", // "Location:"
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            text = filePath,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f),
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis
                        )

                        if (fileSize != null && !isDirectory) {
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "Boyut:", // "Size:"
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = formatFileSize(fileSize),
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.8f)
                            )
                        }
                    }
                }

                // Warning message
                Text(
                    text = if (isDirectory)
                        "⚠️ Bu klasör ve içindeki tüm dosyalar kalıcı olarak silinecektir."
                        // "⚠️ This folder and all its contents will be permanently deleted."
                    else
                        "⚠️ Bu işlem geri alınamaz.",
                        // "⚠️ This action cannot be undone."
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )

                if (isSystemProtected) {
                    // Extra confirmation checkbox for protected folders
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Checkbox(
                            checked = userConfirmed,
                            onCheckedChange = { userConfirmed = it }
                        )
                        Text(
                            text = "Riskleri anlıyorum ve silmek istiyorum",
                            // "I understand the risks and want to delete"
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                enabled = !isSystemProtected || userConfirmed,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error
                )
            ) {
                Text(
                    text = if (isDirectory) "Klasörü Sil" else "Dosyayı Sil", // "Delete Folder" / "Delete File"
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) {
                Text("İptal") // "Cancel"
            }
        }
    )
}

/**
 * Simple deletion confirmation dialog (non-system files)
 */
@Composable
fun SimpleDeletionConfirmationDialog(
    fileName: String,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onCancel,
        icon = {
            Icon(
                imageVector = Icons.Default.Delete,
                contentDescription = null
            )
        },
        title = {
            Text("Dosyayı Sil") // "Delete File"
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    text = "\"$fileName\" dosyasını silmek istediğinizden emin misiniz?",
                    // "Are you sure you want to delete \"$fileName\"?"
                    style = MaterialTheme.typography.bodyLarge
                )
                Text(
                    text = "Bu işlem geri alınamaz.", // "This action cannot be undone."
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = onConfirm,
                colors = ButtonDefaults.textButtonColors(
                    contentColor = MaterialTheme.colorScheme.error
                )
            ) {
                Text("Sil") // "Delete"
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) {
                Text("İptal") // "Cancel"
            }
        }
    )
}

/**
 * Batch deletion confirmation dialog (multiple files)
 */
@Composable
fun BatchDeletionConfirmationDialog(
    fileCount: Int,
    totalSize: Long? = null,
    onConfirm: () -> Unit,
    onCancel: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onCancel,
        icon = {
            Icon(
                imageVector = Icons.Default.Delete,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.error
            )
        },
        title = {
            Text(
                text = "$fileCount Öğeyi Sil", // "Delete $fileCount Items"
                fontWeight = FontWeight.Bold
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = "$fileCount dosya/klasörü silmek istediğinizden emin misiniz?",
                    // "Are you sure you want to delete $fileCount files/folders?"
                    style = MaterialTheme.typography.bodyLarge
                )

                if (totalSize != null) {
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant
                        ),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Row(
                            modifier = Modifier.padding(12.dp),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Toplam Boyut:", // "Total Size:"
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold
                            )
                            Text(
                                text = formatFileSize(totalSize),
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }

                Text(
                    text = "⚠️ Bu işlem geri alınamaz ve tüm seçili öğeler kalıcı olarak silinecektir.",
                    // "⚠️ This action cannot be undone and all selected items will be permanently deleted."
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error
                )
            ) {
                Text(
                    text = "Tümünü Sil", // "Delete All"
                    fontWeight = FontWeight.Bold
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) {
                Text("İptal") // "Cancel"
            }
        }
    )
}

/**
 * Format file size to human-readable string
 */
private fun formatFileSize(bytes: Long): String {
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
 * Check if path is a system-protected directory
 */
fun isSystemProtectedPath(path: String): Boolean {
    val protectedPaths = listOf(
        "C:\\Windows",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\ProgramData",
        "C:\\System Volume Information",
        "C:\\$Recycle.Bin"
    )

    val normalizedPath = File(path).absolutePath
    return protectedPaths.any { protectedPath ->
        normalizedPath.startsWith(protectedPath, ignoreCase = true)
    }
}
