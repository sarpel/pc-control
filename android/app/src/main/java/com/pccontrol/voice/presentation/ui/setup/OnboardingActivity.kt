package com.pccontrol.voice.presentation.ui.setup

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.*
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

/**
 * Onboarding Activity
 *
 * Provides an interactive tutorial for first-time users explaining features,
 * setup process, and usage patterns. Includes multiple screens with animations
 * and progress indicators.
 *
 * Task: T091 [P] Create user onboarding tutorial in android/app/src/main/java/com/pccontrol/voice/presentation/ui/setup/OnboardingActivity.kt
 */
class OnboardingActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme {
                OnboardingScreen(
                    onComplete = {
                        // Mark onboarding as completed
                        markOnboardingComplete()
                        finish()
                    },
                    onSkip = {
                        markOnboardingComplete()
                        finish()
                    }
                )
            }
        }
    }

    private fun markOnboardingComplete() {
        getSharedPreferences("app_prefs", MODE_PRIVATE)
            .edit()
            .putBoolean("onboarding_completed", true)
            .apply()
    }
}

/**
 * Onboarding screen data
 */
data class OnboardingPage(
    val title: String,
    val description: String,
    val icon: ImageVector,
    val tips: List<String> = emptyList()
)

/**
 * Main onboarding screen with pager
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    onComplete: () -> Unit,
    onSkip: () -> Unit
) {
    val pages = remember {
        listOf(
            OnboardingPage(
                title = "Hoş Geldiniz!", // "Welcome!"
                description = "PC'nizi sesli komutlarla kontrol edin. Türkçe komutlarla bilgisayarınızı kolayca yönetin.",
                // "Control your PC with voice commands. Easily manage your computer with Turkish commands."
                icon = Icons.Default.Waving,
                tips = listOf(
                    "Telefon ve PC aynı WiFi ağında olmalı",
                    "Güvenli bağlantı için tek seferlik eşleştirme gerekir",
                    "Komutlarınız tamamen yerel olarak işlenir"
                )
            ),
            OnboardingPage(
                title = "PC'yi Uyandırın", // "Wake Up PC"
                description = "Uyuyan PC'nizi sesli komutla uyandırın ve işlemlerinizi başlatın.",
                // "Wake up your sleeping PC with voice command and start your tasks."
                icon = Icons.Default.Computer,
                tips = listOf(
                    "Hızlı Ayarlar kutucuğuna dokunun",
                    "\"Chrome'u aç\" gibi komutlar verin",
                    "PC 10 saniye içinde uyanır"
                )
            ),
            OnboardingPage(
                title = "Tarayıcı Kontrolü", // "Browser Control"
                description = "Tarayıcınızı sesle kontrol edin, arama yapın ve sayfalarda gezinin.",
                // "Control your browser with voice, search and navigate pages."
                icon = Icons.Default.Language,
                tips = listOf(
                    "\"Hava durumu ara\" - arama yapar",
                    "\"Google'a git\" - siteye gider",
                    "Sayfa içeriğini otomatik özetler"
                )
            ),
            OnboardingPage(
                title = "Sistem İşlemleri", // "System Operations"
                description = "Uygulama açın, dosya arayın, ses seviyesini ayarlayın.",
                // "Open apps, search files, adjust volume."
                icon = Icons.Default.Settings,
                tips = listOf(
                    "\"Notepad'i aç\" - uygulama başlatır",
                    "\"Sesi yükselt\" - ses kontrolü",
                    "\"Sistem bilgilerini göster\" - detaylı bilgi"
                )
            ),
            OnboardingPage(
                title = "Güvenlik", // "Security"
                description = "Verileriniz güvende. mTLS şifrelemesi ve yerel ses işleme.",
                // "Your data is secure. mTLS encryption and local audio processing."
                icon = Icons.Default.Security,
                tips = listOf(
                    "Ses verisi hiçbir zaman kaydedilmez",
                    "Tüm iletişim şifreli",
                    "Sadece eşlenmiş cihazlar bağlanabilir"
                )
            ),
            OnboardingPage(
                title = "Başlayalım!", // "Let's Start!"
                description = "Hemen eşleştirme işlemini başlatarak PC'nizi kontrol etmeye başlayın.",
                // "Start pairing now to begin controlling your PC."
                icon = Icons.Default.RocketLaunch,
                tips = listOf(
                    "PC'de servis uygulamasını çalıştırın",
                    "Android uygulamada eşleştirme kodunu girin",
                    "İlk komutunuzu deneyin!"
                )
            )
        )
    }

    val pagerState = rememberPagerState(pageCount = { pages.size })
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            OnboardingTopBar(
                currentPage = pagerState.currentPage,
                totalPages = pages.size,
                onSkip = onSkip
            )
        },
        bottomBar = {
            OnboardingBottomBar(
                currentPage = pagerState.currentPage,
                totalPages = pages.size,
                onNext = {
                    scope.launch {
                        if (pagerState.currentPage < pages.size - 1) {
                            pagerState.animateScrollToPage(pagerState.currentPage + 1)
                        } else {
                            onComplete()
                        }
                    }
                },
                onPrevious = {
                    scope.launch {
                        if (pagerState.currentPage > 0) {
                            pagerState.animateScrollToPage(pagerState.currentPage - 1)
                        }
                    }
                },
                onComplete = onComplete
            )
        }
    ) { paddingValues ->
        HorizontalPager(
            state = pagerState,
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) { page ->
            OnboardingPageContent(
                page = pages[page],
                isVisible = pagerState.currentPage == page
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun OnboardingTopBar(
    currentPage: Int,
    totalPages: Int,
    onSkip: () -> Unit
) {
    TopAppBar(
        title = { },
        actions = {
            if (currentPage < totalPages - 1) {
                TextButton(onClick = onSkip) {
                    Text("Atla") // "Skip"
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = Color.Transparent
        )
    )
}

@Composable
private fun OnboardingBottomBar(
    currentPage: Int,
    totalPages: Int,
    onNext: () -> Unit,
    onPrevious: () -> Unit,
    onComplete: () -> Unit
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        tonalElevation = 3.dp
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            // Page indicators
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically
            ) {
                repeat(totalPages) { index ->
                    PageIndicator(
                        isSelected = index == currentPage,
                        modifier = Modifier.padding(horizontal = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Navigation buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                // Previous button
                if (currentPage > 0) {
                    TextButton(onClick = onPrevious) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Geri") // "Back"
                    }
                } else {
                    Spacer(modifier = Modifier.width(100.dp))
                }

                // Next/Complete button
                Button(
                    onClick = if (currentPage == totalPages - 1) onComplete else onNext,
                    modifier = Modifier.heightIn(min = 48.dp)
                ) {
                    Text(
                        text = if (currentPage == totalPages - 1) "Başla" else "İleri",
                        // "Start" / "Next"
                        fontWeight = FontWeight.Bold
                    )
                    if (currentPage < totalPages - 1) {
                        Spacer(modifier = Modifier.width(4.dp))
                        Icon(
                            imageVector = Icons.Default.ArrowForward,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun PageIndicator(
    isSelected: Boolean,
    modifier: Modifier = Modifier
) {
    val width by animateDpAsState(
        targetValue = if (isSelected) 32.dp else 8.dp,
        animationSpec = tween(300)
    )

    val color by animateColorAsState(
        targetValue = if (isSelected)
            MaterialTheme.colorScheme.primary
        else
            MaterialTheme.colorScheme.onSurface.copy(alpha = 0.3f),
        animationSpec = tween(300)
    )

    Box(
        modifier = modifier
            .width(width)
            .height(8.dp)
            .clip(RoundedCornerShape(4.dp))
            .background(color)
    )
}

@Composable
private fun OnboardingPageContent(
    page: OnboardingPage,
    isVisible: Boolean
) {
    // Animate content entrance
    val animatedVisibility by animateFloatAsState(
        targetValue = if (isVisible) 1f else 0f,
        animationSpec = tween(500)
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp)
            .graphicsLayer(alpha = animatedVisibility),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        // Icon with animation
        Box(
            modifier = Modifier
                .size(120.dp)
                .clip(CircleShape)
                .background(MaterialTheme.colorScheme.primaryContainer),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = page.icon,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = MaterialTheme.colorScheme.onPrimaryContainer
            )
        }

        Spacer(modifier = Modifier.height(32.dp))

        // Title
        Text(
            text = page.title,
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurface
        )

        Spacer(modifier = Modifier.height(16.dp))

        // Description
        Text(
            text = page.description,
            style = MaterialTheme.typography.bodyLarge,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.8f),
            modifier = Modifier.padding(horizontal = 16.dp)
        )

        Spacer(modifier = Modifier.height(32.dp))

        // Tips
        if (page.tips.isNotEmpty()) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)
                ),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    page.tips.forEach { tip ->
                        Row(
                            verticalAlignment = Alignment.Top,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.CheckCircle,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                                tint = MaterialTheme.colorScheme.primary
                            )
                            Text(
                                text = tip,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                }
            }
        }
    }
}

/**
 * Check if onboarding has been completed
 */
fun hasCompletedOnboarding(context: android.content.Context): Boolean {
    return context.getSharedPreferences("app_prefs", android.content.Context.MODE_PRIVATE)
        .getBoolean("onboarding_completed", false)
}
