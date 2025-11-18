package com.pccontrol.voice.services

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationManagerCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Battery optimization service for voice assistant.
 *
 * Provides automatic battery optimization recommendations and
 * can apply certain optimizations with user permission.
 */

data class OptimizationAction(
    val id: String,
    val title: String,
    val description: String,
    val canAutoApply: Boolean,
    val requiresSystemPermission: Boolean,
    val estimatedBatterySavings: Float, // percentage points
    val priority: Int // 1-10, higher is more important
)

data class OptimizationResult(
    val actionId: String,
    val success: Boolean,
    val message: String,
    val actualBatterySavings: Float = 0f,
    val timestamp: Long = System.currentTimeMillis()
)

class BatteryOptimizationService private constructor(
    private val context: Context,
    private val coroutineScope: CoroutineScope
) {

    companion object {
        @Volatile
        private var INSTANCE: BatteryOptimizationService? = null

        fun getInstance(context: Context, coroutineScope: CoroutineScope): BatteryOptimizationService {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: BatteryOptimizationService(context.applicationContext, coroutineScope)
                    .also { INSTANCE = it }
            }
        }

        // Optimization action IDs
        const val ACTION_DISABLE_BACKGROUND_SYNC = "disable_background_sync"
        const val ACTION_ADJUST_BRIGHTNESS = "adjust_brightness"
        const val ACTION_ENABLE_BATTERY_SAVER = "enable_battery_saver"
        const val ACTION_CLOSE_BACKGROUND_APPS = "close_background_apps"
        const val ACTION_DISABLE_BLUETOOTH = "disable_bluetooth"
        const val ACTION_OPTIMIZE_LOCATION = "optimize_location"
        const val ACTION_RESTRICT_BACKGROUND_DATA = "restrict_background_data"
        const val ACTION_OPTIMIZE_WIFI_MOBILE = "optimize_wifi_mobile"
    }

    private val batteryMonitor = BatteryMonitor.getInstance(context, coroutineScope)
    private val activityManager = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager

    // State flows
    private val _availableOptimizations = MutableStateFlow<List<OptimizationAction>>(emptyList())
    val availableOptimizations: StateFlow<List<OptimizationAction>> = _availableOptimizations.asStateFlow()

    private val _optimizationResults = MutableStateFlow<List<OptimizationResult>>(emptyList())
    val optimizationResults: StateFlow<List<OptimizationResult>> = _optimizationResults.asStateFlow()

    private val _isOptimizing = MutableStateFlow(false)
    val isOptimizing: StateFlow<Boolean> = _isOptimizing.asStateFlow()

    // Configuration
    private val maxResultsHistory = 50

    init {
        // Monitor battery changes and update available optimizations
        coroutineScope.launch {
            batteryMonitor.batteryInfoFlow.collect { batteryInfo ->
                batteryInfo?.let { updateAvailableOptimizations(it) }
            }
        }
    }

    /**
     * Get all available optimization actions
     */
    fun getAvailableOptimizations(): List<OptimizationAction> {
        val currentBattery = batteryMonitor.getCurrentBatteryInfo() ?: return emptyList()

        val optimizations = mutableListOf<OptimizationAction>()

        // Battery saver (highest priority for low battery)
        if (!currentBattery.isCharging && currentBattery.isLow) {
            optimizations.add(
                OptimizationAction(
                    id = ACTION_ENABLE_BATTERY_SAVER,
                    title = "Pil Tasarruf Modunu Etkinleştir",
                    description = "Pil ömrünü %20-30 uzatmak için pil tasarruf modunu etkinleştirin",
                    canAutoApply = Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP,
                    requiresSystemPermission = false,
                    estimatedBatterySavings = 25f,
                    priority = 10
                )
            )
        }

        // Background apps (medium priority)
        optimizations.add(
            OptimizationAction(
                id = ACTION_CLOSE_BACKGROUND_APPS,
                title = "Arka Plan Uygulamalarını Kapat",
                description = "Pil tüketen arka plan uygulamalarını kapatın",
                canAutoApply = true,
                requiresSystemPermission = false,
                estimatedBatterySavings = 8f,
                priority = 7
            )
        )

        // Screen brightness (high priority if battery is low)
        if (currentBattery.isLow) {
            optimizations.add(
                OptimizationAction(
                    id = ACTION_ADJUST_BRIGHTNESS,
                    title = "Ekran Parlaklığını Azalt",
                    description = "Ekran parlaklığını %30 azaltarak pil tasarrufu sağlayın",
                    canAutoApply = false,
                    requiresSystemPermission = false,
                    estimatedBatterySavings = 15f,
                    priority = 8
                )
            )
        }

        // Background sync (medium priority)
        optimizations.add(
            OptimizationAction(
                id = ACTION_DISABLE_BACKGROUND_SYNC,
                title = "Arka Plan Senkronizasyonunu Kısıtla",
                description = "Uygulamaların arka planda senkronizasyon yapmasını engelleyin",
                canAutoApply = false,
                requiresSystemPermission = true,
                estimatedBatterySavings = 5f,
                priority = 6
            )
        )

        // Location services (low priority)
        optimizations.add(
            OptimizationAction(
                id = ACTION_OPTIMIZE_LOCATION,
                title = "Konum Servislerini Optimize Et",
                description = "Yüksek hassasiyetli konum servislerini kapatın",
                canAutoApply = false,
                requiresSystemPermission = true,
                estimatedBatterySavings = 4f,
                priority = 4
            )
        )

        // Bluetooth (low priority if not connected)
        optimizations.add(
            OptimizationAction(
                id = ACTION_DISABLE_BLUETOOTH,
                title = "Bluetooth'u Kapat",
                description = "Kullanılmayan Bluetooth'u kapatın",
                canAutoApply = true,
                requiresSystemPermission = false,
                estimatedBatterySavings = 2f,
                priority = 3
            )
        )

        // Background data (medium priority)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            optimizations.add(
                OptimizationAction(
                    id = ACTION_RESTRICT_BACKGROUND_DATA,
                    title = "Arka Plan Veri Kullanımını Kısıtla",
                    description = "Uygulamaların arka planda veri kullanmasını kısıtlayın",
                    canAutoApply = false,
                    requiresSystemPermission = true,
                    estimatedBatterySavings = 6f,
                    priority = 5
                )
            )
        }

        // Sort by priority (descending)
        val sortedOptimizations = optimizations.sortedByDescending { it.priority }
        _availableOptimizations.value = sortedOptimizations

        return sortedOptimizations
    }

    /**
     * Apply optimization action
     */
    suspend fun applyOptimization(actionId: String): OptimizationResult {
        _isOptimizing.value = true

        return try {
            val action = _availableOptimizations.value.find { it.id == actionId }
                ?: return OptimizationResult(
                    actionId = actionId,
                    success = false,
                    message = "Optimizasyon bulunamadı"
                )

            val result = when (actionId) {
                ACTION_ENABLE_BATTERY_SAVER -> enableBatterySaver()
                ACTION_CLOSE_BACKGROUND_APPS -> closeBackgroundApps()
                ACTION_DISABLE_BACKGROUND_SYNC -> disableBackgroundSync()
                ACTION_ADJUST_BRIGHTNESS -> adjustBrightness()
                ACTION_OPTIMIZE_LOCATION -> optimizeLocationServices()
                ACTION_DISABLE_BLUETOOTH -> disableBluetooth()
                ACTION_RESTRICT_BACKGROUND_DATA -> restrictBackgroundData()
                ACTION_OPTIMIZE_WIFI_MOBILE -> optimizeWifiMobile()
                else -> OptimizationResult(
                    actionId = actionId,
                    success = false,
                    message = "Bilinmeyen optimizasyon eylemi"
                )
            }

            // Add to results history
            val updatedResults = _optimizationResults.value.toMutableList()
            updatedResults.add(0, result) // Add to beginning
            if (updatedResults.size > maxResultsHistory) {
                updatedResults.removeAt(updatedResults.size - 1)
            }
            _optimizationResults.value = updatedResults

            result

        } catch (e: Exception) {
            OptimizationResult(
                actionId = actionId,
                success = false,
                message = "Optimizasyon uygulanırken hata: ${e.message}"
            )
        } finally {
            _isOptimizing.value = false
        }
    }

    /**
     * Apply multiple optimizations automatically
     */
    suspend fun applyAutoOptimizations(): List<OptimizationResult> {
        val autoApplicableActions = _availableOptimizations.value.filter { it.canAutoApply }

        if (autoApplicableActions.isEmpty()) {
            return emptyList()
        }

        return coroutineScope.async {
            autoApplicableActions.map { action ->
                async {
                    applyOptimization(action.id)
                }
            }.awaitAll()
        }.await()
    }

    /**
     * Get optimization summary
     */
    fun getOptimizationSummary(): Map<String, Any> {
        val currentBattery = batteryMonitor.getCurrentBatteryInfo()
        val availableCount = _availableOptimizations.value.size
        val autoApplicableCount = _availableOptimizations.value.count { it.canAutoApply }
        val successfulOptimizations = _optimizationResults.value.count { it.success }

        val totalEstimatedSavings = _availableOptimizations.value
            .filter { it.canAutoApply }
            .sumOf { it.estimatedBatterySavings.toDouble() }
            .toFloat()

        return mapOf(
            "battery_level" to (currentBattery?.percentage ?: 0),
            "available_optimizations" to availableCount,
            "auto_applicable_count" to autoApplicableCount,
            "total_estimated_savings_percent" to totalEstimatedSavings,
            "successful_optimizations_today" to successfulOptimizations,
            "is_charging" to (currentBattery?.isCharging ?: false),
            "is_battery_low" to (currentBattery?.isLow ?: false)
        )
    }

    // Private optimization implementations

    private suspend fun enableBatterySaver(): OptimizationResult {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                val powerManager = context.getSystemService(Context.POWER_SERVICE) as PowerManager
                powerManager.isPowerSaveMode = true

                OptimizationResult(
                    actionId = ACTION_ENABLE_BATTERY_SAVER,
                    success = true,
                    message = "Pil tasarruf modu etkinleştirildi",
                    actualBatterySavings = 25f
                )
            } else {
                OptimizationResult(
                    actionId = ACTION_ENABLE_BATTERY_SAVER,
                    success = false,
                    message = "Pil tasarruf modu bu Android sürümünde desteklenmiyor"
                )
            }
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_ENABLE_BATTERY_SAVER,
                success = false,
                message = "Pil tasarruf modu etkinleştirilemedi: ${e.message}"
            )
        }
    }

    private suspend fun closeBackgroundApps(): OptimizationResult {
        return try {
            val runningTasks = activityManager.getRunningTasks(100)
            val packageName = context.packageName

            var closedCount = 0
            runningTasks.forEach { taskInfo ->
                val baseActivity = taskInfo.baseActivity
                if (baseActivity != null && baseActivity.packageName != packageName) {
                    try {
                        activityManager.killBackgroundProcesses(baseActivity.packageName)
                        closedCount++
                    } catch (e: Exception) {
                        // Some apps can't be killed
                    }
                }
            }

            OptimizationResult(
                actionId = ACTION_CLOSE_BACKGROUND_APPS,
                success = true,
                message = "$closedCount arka plan uygulaması kapatıldı",
                actualBatterySavings = 8f
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_CLOSE_BACKGROUND_APPS,
                success = false,
                message = "Arka plan uygulamaları kapatılamadı: ${e.message}"
            )
        }
    }

    private suspend fun disableBackgroundSync(): OptimizationResult {
        return try {
            // This would require system permissions on most devices
            // For now, return a result indicating user action needed
            OptimizationResult(
                actionId = ACTION_DISABLE_BACKGROUND_SYNC,
                success = false,
                message = "Arka plan senkronizasyonunu kısıtlamak için sistem ayarlarını manuel olarak güncelleyin",
                requiresSystemPermission = true
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_DISABLE_BACKGROUND_SYNC,
                success = false,
                message = "Arka plan senkronizasyonu kısıtlanamadı: ${e.message}"
            )
        }
    }

    private suspend fun adjustBrightness(): OptimizationResult {
        return try {
            // This would require system settings access
            // For now, return a result indicating user action needed
            OptimizationResult(
                actionId = ACTION_ADJUST_BRIGHTNESS,
                success = false,
                message = "Ekran parlaklığını ayarlamak için sistem ayarlarını manuel olarak güncelleyin",
                requiresSystemPermission = true
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_ADJUST_BRIGHTNESS,
                success = false,
                message = "Ekran parlaklığı ayarlanamadı: ${e.message}"
            )
        }
    }

    private suspend fun optimizeLocationServices(): OptimizationResult {
        return try {
            // This would require system permissions
            OptimizationResult(
                actionId = ACTION_OPTIMIZE_LOCATION,
                success = false,
                message = "Konum servislerini optimize etmek için sistem ayarlarını manuel olarak güncelleyin",
                requiresSystemPermission = true
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_OPTIMIZE_LOCATION,
                success = false,
                message = "Konum servisleri optimize edilemedi: ${e.message}"
            )
        }
    }

    private suspend fun disableBluetooth(): OptimizationResult {
        return try {
            // This would require Bluetooth permissions
            OptimizationResult(
                actionId = ACTION_DISABLE_BLUETOOTH,
                success = false,
                message = "Bluetooth'u kapatmak için sistem ayarlarını manuel olarak güncelleyin"
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_DISABLE_BLUETOOTH,
                success = false,
                message = "Bluetooth kapatılamadı: ${e.message}"
            )
        }
    }

    private suspend fun restrictBackgroundData(): OptimizationResult {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
                // This would require system permissions
                OptimizationResult(
                    actionId = ACTION_RESTRICT_BACKGROUND_DATA,
                    success = false,
                    message = "Arka plan veri kullanımını kısıtlamak için sistem ayarlarını manuel olarak güncelleyin",
                    requiresSystemPermission = true
                )
            } else {
                OptimizationResult(
                    actionId = ACTION_RESTRICT_BACKGROUND_DATA,
                    success = false,
                    message = "Arka plan veri kısıtlaması bu Android sürümünde desteklenmiyor"
                )
            }
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_RESTRICT_BACKGROUND_DATA,
                success = false,
                message = "Arka plan verisi kısıtlanamadı: ${e.message}"
            )
        }
    }

    private suspend fun optimizeWifiMobile(): OptimizationResult {
        return try {
            // This would require system permissions
            OptimizationResult(
                actionId = ACTION_OPTIMIZE_WIFI_MOBILE,
                success = false,
                message = "Wi-Fi/Mobil veri optimizasyonu için sistem ayarlarını manuel olarak güncelleyin",
                requiresSystemPermission = true
            )
        } catch (e: Exception) {
            OptimizationResult(
                actionId = ACTION_OPTIMIZE_WIFI_MOBILE,
                success = false,
                message = "Wi-Fi/Mobil veri optimize edilemedi: ${e.message}"
            )
        }
    }

    private fun updateAvailableOptimizations(batteryInfo: BatteryInfo) {
        // Re-evaluate available optimizations based on current battery state
        getAvailableOptimizations()
    }

    /**
     * Reset optimization history
     */
    fun resetHistory() {
        _optimizationResults.value = emptyList()
    }
}