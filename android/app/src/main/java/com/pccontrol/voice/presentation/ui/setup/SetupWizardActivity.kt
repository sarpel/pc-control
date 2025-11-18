package com.pccontrol.voice.presentation.ui.setup

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pccontrol.voice.presentation.viewmodel.DiscoveredPC
import com.pccontrol.voice.presentation.viewmodel.SetupStep
import com.pccontrol.voice.presentation.viewmodel.SetupWizardUiState
import com.pccontrol.voice.presentation.viewmodel.SetupWizardViewModel

/**
 * Setup Wizard Activity for secure PC connection setup.

 * Guides user through:
 * 1. Welcome screen
 * 2. PC discovery (automatic + manual)
 * 3. Pairing process with 6-digit code
 * 4. Connection verification
 * 5. Success confirmation
 */
class SetupWizardActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PCVoiceTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    SetupWizardScreen()
                }
            }
        }
    }
}

@Composable
private fun SetupWizardScreen(
    viewModel: SetupWizardViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsState()

    // Handle navigation
    when (uiState.currentStep) {
        SetupStep.WELCOME -> WelcomeScreen(
            onNext = { viewModel.nextStep() }
        )
        SetupStep.PC_DISCOVERY -> PCDiscoveryScreen(
            uiState = uiState,
            onPCSelected = { pc -> viewModel.selectPC(pc) },
            onNext = { viewModel.nextStep() },
            onRetry = { viewModel.retryDiscovery() }
        )
        SetupStep.PAIRING -> PairingScreen(
            uiState = uiState,
            onCodeEntered = { code -> viewModel.enterPairingCode(code) },
            onNext = { viewModel.nextStep() },
            onRetry = { viewModel.retryPairing() }
        )
        SetupStep.VERIFICATION -> VerificationScreen(
            uiState = uiState,
            onNext = { viewModel.nextStep() },
            onRetry = { viewModel.retryVerification() }
        )
        SetupStep.SUCCESS -> SuccessScreen(
            onFinish = { viewModel.finishSetup() }
        )
    }
}

@Composable
private fun WelcomeScreen(
    onNext: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Logo/Icon
        Box(
            modifier = Modifier
                .size(120.dp)
                .background(
                    MaterialTheme.colorScheme.primaryContainer,
                    androidx.compose.foundation.shape.CircleShape
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "🎤",
                fontSize = 60.sp
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Title
        Text(
            text = "PC Sesli Asistan",
            fontSize = 32.sp,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center
        )

        Text(
            text = "Bilgisayarınızı sesle kontrol edin",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Features
        val features = listOf(
            "✓ Güvenli bağlantı",
            "✓ Hızlı komutlar",
            "✓ Türkçe dil desteği",
            "✓ Çevrimdışı çalışma"
        )

        features.forEach { feature ->
            Text(
                text = feature,
                fontSize = 16.sp,
                modifier = Modifier.padding(vertical = 4.dp)
            )
        }

        Spacer(modifier = Modifier.height(48.dp))

        // Continue button
        Button(
            onClick = onNext,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            Text(
                text = "Başla",
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

@Composable
private fun PCDiscoveryScreen(
    uiState: SetupWizardUiState,
    onPCSelected: (DiscoveredPC) -> Unit,
    onNext: () -> Unit,
    onRetry: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
    ) {
        // Header
        Text(
            text = "PC Bulma",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "Aynı WiFi ağındaki bilgisayarları buluyoruz...",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = 8.dp)
        )

        Spacer(modifier = Modifier.height(24.dp))

        // Loading state
        if (uiState.isDiscovering) {
            Box(
                modifier = Modifier.fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    CircularProgressIndicator()
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "PC'ler aranıyor...",
                        fontSize = 16.sp
                    )
                }
            }
        }

        // PC List
        if (uiState.discoveredPCs.isNotEmpty()) {
            Text(
                text = "Bulunan PC'ler:",
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium,
                modifier = Modifier.padding(bottom = 16.dp)
            )

            uiState.discoveredPCs.forEach { pc ->
                PCItemCard(
                    pc = pc,
                    isSelected = uiState.selectedPC?.id == pc.id,
                    onClick = { onPCSelected(pc) }
                )
                Spacer(modifier = Modifier.height(12.dp))
            }
        }

        // Manual entry option
        if (uiState.discoveredPCs.isEmpty() && !uiState.isDiscovering) {
            Text(
                text = "PC bulunamadı. Manuel giriş yapın:",
                fontSize = 16.sp,
                modifier = Modifier.padding(bottom = 16.dp)
            )

            OutlinedTextField(
                value = uiState.manualPCAddress,
                onValueChange = { /* Update in ViewModel */ },
                label = { Text("PC IP Adresi") },
                modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Action buttons
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = onRetry,
                modifier = Modifier.weight(1f)
            ) {
                Text("Tekrar Dene")
            }

            Button(
                onClick = onNext,
                enabled = uiState.selectedPC != null || uiState.manualPCAddress.isNotBlank(),
                modifier = Modifier.weight(1f)
            ) {
                Text("Devam")
            }
        }
    }
}

@Composable
private fun PCItemCard(
    pc: DiscoveredPC,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surface
            }
        ),
        elevation = CardDefaults.cardElevation(
            defaultElevation = if (isSelected) 4.dp else 1.dp
        ),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column {
                Text(
                    text = pc.name,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = pc.ipAddress,
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (pc.isAvailable) {
                    Text(
                        text = "Ulaşılabilir",
                        fontSize = 12.sp,
                        color = Color(0xFF4CAF50)
                    )
                }
            }

            if (isSelected) {
                Text(
                    text = "✓",
                    fontSize = 20.sp,
                    color = MaterialTheme.colorScheme.primary
                )
            }
        }
    }
}

@Composable
private fun PairingScreen(
    uiState: SetupWizardUiState,
    onCodeEntered: (String) -> Unit,
    onNext: () -> Unit,
    onRetry: () -> Unit
) {
    var codeInput by remember { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(32.dp))

        // Header
        Text(
            text = "PC Eşleştirme",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold
        )

        Text(
            text = "Bilgisayarda gösterilecek 6 haneli kodu girin",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 8.dp)
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Pairing code display (from PC)
        if (uiState.pairingCode != null) {
            PairingCodeDisplay(code = uiState.pairingCode)
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Code input
        Text(
            text = "Eşleştirme Kodu:",
            fontSize = 18.sp,
            fontWeight = FontWeight.Medium
        )

        Spacer(modifier = Modifier.height(16.dp))

        // 6-digit code input
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            repeat(6) { index ->
                CodeDigitInput(
                    value = codeInput.getOrNull(index)?.toString() ?: "",
                    onValueChange = { digit ->
                        val newCode = if (digit.isEmpty()) {
                            if (codeInput.length > index) {
                                codeInput.substring(0, index) + codeInput.substring(index + 1)
                            } else {
                                codeInput
                            }
                        } else {
                            val before = codeInput.substring(0, index)
                            val after = if (codeInput.length > index) codeInput.substring(index + 1) else ""
                            before + digit + after
                        }
                        codeInput = newCode.take(6) // Limit to 6 digits
                        onCodeEntered(codeInput)
                    }
                )
            }
        }

        // Error message
        if (uiState.errorMessage != null) {
            Spacer(modifier = Modifier.height(16.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Text(
                    text = uiState.errorMessage,
                    modifier = Modifier.padding(16.dp),
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
        }

        Spacer(modifier = Modifier.height(48.dp))

        // Action buttons
        Button(
            onClick = onNext,
            enabled = codeInput.length == 6 && !uiState.isPairing,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            if (uiState.isPairing) {
                CircularProgressIndicator(
                    modifier = Modifier.size(24.dp),
                    color = MaterialTheme.colorScheme.onPrimary
                )
            } else {
                Text(
                    text = "Eşleştir",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }

        if (uiState.errorMessage != null) {
            Spacer(modifier = Modifier.height(12.dp))
            TextButton(
                onClick = onRetry
            ) {
                Text("Tekrar Dene")
            }
        }
    }
}

@Composable
private fun PairingCodeDisplay(code: String) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
    ) {
        Column(
            modifier = Modifier.padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(
                text = "PC'de gösterilen kod:",
                fontSize = 16.sp,
                color = MaterialTheme.colorScheme.onPrimaryContainer
            )

            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = code.chunked(3).joinToString(" "),
                fontSize = 36.sp,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary,
                letterSpacing = 4.sp
            )
        }
    }
}

@Composable
private fun CodeDigitInput(
    value: String,
    onValueChange: (String) -> Unit
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.size(56.dp),
        singleLine = true,
        textStyle = LocalTextStyle.current.copy(
            fontSize = 24.sp,
            textAlign = TextAlign.Center
        ),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)
    )
}

@Composable
private fun VerificationScreen(
    uiState: SetupWizardUiState,
    onNext: () -> Unit,
    onRetry: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        if (uiState.isVerifying) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                CircularProgressIndicator()
                Spacer(modifier = Modifier.height(24.dp))
                Text(
                    text = "Bağlantı doğrulanıyor...",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = "Lütfen bekleyin",
                    fontSize = 14.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            // Success state
            Box(
                modifier = Modifier
                    .size(100.dp)
                    .background(
                        Color(0xFF4CAF50),
                        androidx.compose.foundation.shape.CircleShape
                    ),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "✓",
                    fontSize = 60.sp,
                    color = Color.White
                )
            }

            Spacer(modifier = Modifier.height(32.dp))

            Text(
                text = "Bağlantı Başarılı!",
                fontSize = 24.sp,
                fontWeight = FontWeight.Bold
            )

            Text(
                text = "${uiState.selectedPC?.name ?: "PC"} ile güvenli bağlantı kuruldu",
                fontSize = 16.sp,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(48.dp))

            Button(
                onClick = onNext,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp)
            ) {
                Text(
                    text = "Devam",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

@Composable
private fun SuccessScreen(
    onFinish: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Success icon
        Box(
            modifier = Modifier
                .size(120.dp)
                .background(
                    Color(0xFF4CAF50),
                    androidx.compose.foundation.shape.CircleShape
                ),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "✓",
                fontSize = 80.sp,
                color = Color.White
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "Kurulum Tamamlandı!",
            fontSize = 28.sp,
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "PC Sesli Asistan artık kullanıma hazır",
            fontSize = 16.sp,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(48.dp))

        // Usage instructions
        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceVariant
            )
        ) {
            Column(
                modifier = Modifier.padding(20.dp),
                horizontalAlignment = Alignment.Start
            ) {
                Text(
                    text = "Nasıl kullanılır:",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Medium
                )

                Spacer(modifier = Modifier.height(12.dp))

                listOf(
                    "1. Hızlı Ayarlar'dan PC Sesli Asistan'ı açın",
                    "2. Mikrofona \"Chrome'u aç\" deyin",
                    "3. Komutunuz bilgisayarda çalışacak"
                ).forEach { instruction ->
                    Text(
                        text = instruction,
                        fontSize = 14.sp,
                        modifier = Modifier.padding(vertical = 4.dp)
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(48.dp))

        Button(
            onClick = onFinish,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp)
        ) {
            Text(
                text = "Bitir",
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

// Theme wrapper
@Composable
private fun PCVoiceTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = lightColorScheme(),
        content = content
    )
}