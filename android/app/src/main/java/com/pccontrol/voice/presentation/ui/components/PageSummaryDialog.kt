package com.pccontrol.voice.presentation.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.pccontrol.voice.domain.services.PageSummary
import java.text.SimpleDateFormat
import java.util.*

/**
 * Page Summary Dialog
 *
 * Displays page content extracted from browser commands in a modal dialog.
 * Shows title, URL, extracted content, and provides copy/share actions.
 *
 * Task: T066 [US2] Implement page summary display in Android UI in
 * android/app/src/main/java/com/pccontrol/voice/presentation/ui/components/PageSummaryDialog.kt
 */
@Composable
fun PageSummaryDialog(
    pageSummary: PageSummary,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    val scrollState = rememberScrollState()

    var showCopiedSnackbar by remember { mutableStateOf(false) }
    var showShareDialog by remember { mutableStateOf(false) }

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
                PageSummaryHeader(
                    title = pageSummary.title,
                    url = pageSummary.url,
                    timestamp = pageSummary.timestamp,
                    onClose = onDismiss,
                    onCopy = {
                        clipboardManager.setText(AnnotatedString(pageSummary.content))
                        showCopiedSnackbar = true
                    },
                    onShare = {
                        showShareDialog = true
                    }
                )

                Divider()

                // Content
                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .verticalScroll(scrollState)
                        .padding(16.dp)
                ) {
                    Text(
                        text = pageSummary.content,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }

    // Snackbar for copy confirmation
    if (showCopiedSnackbar) {
        LaunchedEffect(Unit) {
            kotlinx.coroutines.delay(2000)
            showCopiedSnackbar = false
        }

        Snackbar(
            modifier = Modifier.padding(16.dp),
            action = {
                TextButton(onClick = { showCopiedSnackbar = false }) {
                    Text("Tamam") // "OK"
                }
            }
        ) {
            Text("İçerik panoya kopyalandı") // "Content copied to clipboard"
        }
    }

    // Share dialog
    if (showShareDialog) {
        ShareContentDialog(
            content = pageSummary.content,
            title = pageSummary.title,
            onDismiss = { showShareDialog = false }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PageSummaryHeader(
    title: String,
    url: String?,
    timestamp: Long,
    onClose: () -> Unit,
    onCopy: () -> Unit,
    onShare: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(16.dp)
    ) {
        // Top row: Title and Close button
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(
                modifier = Modifier.weight(1f).padding(end = 8.dp)
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                if (url != null) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = url,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.7f),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = formatTimestamp(timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f)
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

        Spacer(modifier = Modifier.height(12.dp))

        // Action buttons row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedButton(
                onClick = onCopy,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            ) {
                Icon(
                    imageVector = Icons.Default.ContentCopy,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("Kopyala") // "Copy"
            }

            OutlinedButton(
                onClick = onShare,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            ) {
                Icon(
                    imageVector = Icons.Default.Share,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text("Paylaş") // "Share"
            }
        }
    }
}

@Composable
private fun ShareContentDialog(
    content: String,
    title: String,
    onDismiss: () -> Unit
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = {
            Icon(Icons.Default.Share, contentDescription = null)
        },
        title = {
            Text("İçeriği Paylaş") // "Share Content"
        },
        text = {
            Column {
                Text(
                    text = "Bu içeriği paylaşmak için bir uygulama seçin:",  // "Choose an app to share this content:"
                    style = MaterialTheme.typography.bodyMedium
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "\"$title\"",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    // TODO: Implement actual share intent
                    // val sendIntent = Intent().apply {
                    //     action = Intent.ACTION_SEND
                    //     putExtra(Intent.EXTRA_TEXT, content)
                    //     type = "text/plain"
                    // }
                    // context.startActivity(Intent.createChooser(sendIntent, title))
                    onDismiss()
                }
            ) {
                Text("Paylaş") // "Share"
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("İptal") // "Cancel"
            }
        }
    )
}

/**
 * Format timestamp to human-readable string
 */
private fun formatTimestamp(timestamp: Long): String {
    val dateFormat = SimpleDateFormat("dd MMM yyyy, HH:mm", Locale("tr", "TR"))
    return dateFormat.format(Date(timestamp))
}

/**
 * Loading state for page summary
 */
@Composable
fun PageSummaryLoadingDialog(onDismiss: () -> Unit) {
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
                    text = "Sayfa içeriği alınıyor...", // "Fetching page content..."
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

/**
 * Error state for page summary
 */
@Composable
fun PageSummaryErrorDialog(
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
            Text("İçerik Alınamadı") // "Could Not Fetch Content"
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
