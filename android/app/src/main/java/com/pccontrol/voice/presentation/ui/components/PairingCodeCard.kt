package com.pccontrol.voice.presentation.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Card component for displaying pairing code.
 */
@Composable
fun PairingCodeCard(
    pairingCode: String,
    onCopyCode: () -> Unit,
    modifier: Modifier = Modifier
) {
    var copySuccess by remember { mutableStateOf(false) }

    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "Bu Kodu PC'ye Girin",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium
            )

            // Pairing code display
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(Color.White)
                    .padding(16.dp)
            ) {
                Text(
                    text = pairingCode.chunked(3).joinToString(" "),
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.Bold,
                    fontSize = 32.sp,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                    color = MaterialTheme.colorScheme.primary
                )
            }

            // Copy button
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        onCopyCode()
                        copySuccess = true
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Icon(
                        imageVector = if (copySuccess) {
                            Icons.Default.Check
                        } else {
                            Icons.Default.ContentCopy
                        },
                        contentDescription = if (copySuccess) "Kopyalandı" else "Kopyala"
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(if (copySuccess) "Kopyalandı!" else "Kopyala")
                }
            }

            // Instructions
            Text(
                text = "PC uygulamasında eşleştirme ekranına bu kodu girin",
                style = MaterialTheme.typography.bodySmall,
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            LaunchedEffect(copySuccess) {
                if (copySuccess) {
                    kotlinx.coroutines.delay(2000)
                    copySuccess = false
                }
            }
        }
    }
}