package com.pccontrol.voice.services

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.max
import kotlin.math.min

/**
 * Battery usage monitoring service for voice assistant.
 *
 * Features:
 * - Real-time battery level and status monitoring
 * - Power consumption tracking
 * - Battery optimization recommendations
 * - Background vs foreground usage analysis
 * - Battery drain detection and alerts
 */

data class BatteryInfo(
    val level: Int,           // 0-100
    val scale: Int,           // Usually 100
    val status: Int,          // BatteryManager.BATTERY_STATUS_*
    val health: Int,          // BatteryManager.BATTERY_HEALTH_*
    val plugged: Int,         // BatteryManager.BATTERY_PLUGGED_*
    val temperature: Float,   // Celsius
    val voltage: Int,         // Millivolts
    val technology: String,   // Battery technology
    val timestamp: Long = System.currentTimeMillis()
) {
    val percentage: Float
        get() = if (scale > 0) (level.toFloat() / scale.toFloat()) * 100f else 0f

    val isCharging: Boolean
        get() = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                status == BatteryManager.BATTERY_STATUS_FULL

    val isLow: Boolean
        get() = percentage < 15f

    val isCritical: Boolean
        get() = percentage < 5f

    val isOverheating: Boolean
        get() = temperature > 45f  // 45°C threshold
}

data class PowerConsumptionMetrics(
    val averageDrainRate: Float,      // % per hour
    val currentDrainRate: Float,      // % per hour (last 5 minutes)
    val screenOnDrainRate: Float,     // % per hour when screen on
    val screenOffDrainRate: Float,    // % per hour when screen off
    val voiceAssistantUsage: Float,   // % attributed to voice assistant
    val estimatedTimeRemaining: Long, // Minutes until empty
    val timestamp: Long = System.currentTimeMillis()
)

data class BatteryOptimizationRecommendation(
    val type: RecommendationType,
    val priority: Priority,            // LOW, MEDIUM, HIGH, CRITICAL
    val title: String,
    val description: String,
    val estimatedSavings: Float,      // % battery saved
    val actionRequired: Boolean = false
) {
    enum class RecommendationType {
        BRIGHTNESS,
        BACKGROUND_SYNC,
        LOCATION_SERVICES,
        BLUETOOTH,
        WIFI_MOBILE,
        APP_OPTIMIZATION,
        BATTERY_SAVER,
        CHARGING_BEHAVIOR
    }

    enum class Priority { LOW, MEDIUM, HIGH, CRITICAL }
}

class BatteryMonitor private constructor(
    private val context: Context,
    private val coroutineScope: CoroutineScope
) {

    companion object {
        @Volatile
        private var INSTANCE: BatteryMonitor? = null

        fun getInstance(context: Context, coroutineScope: CoroutineScope): BatteryMonitor {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: BatteryMonitor(context.applicationContext, coroutineScope)
                    .also { INSTANCE = it }
            }
        }
    }

    // Battery management
    private val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager

    // Data storage
    private val batteryHistory = ConcurrentHashMap<Long, BatteryInfo>()
    private val powerUsageHistory = mutableListOf<PowerConsumptionMetrics>()

    // Flows for real-time updates
    private val _batteryInfoFlow = MutableStateFlow<BatteryInfo?>(null)
    val batteryInfoFlow: StateFlow<BatteryInfo?> = _batteryInfoFlow.asStateFlow()

    private val _powerMetricsFlow = MutableStateFlow<PowerConsumptionMetrics?>(null)
    val powerMetricsFlow: StateFlow<PowerConsumptionMetrics?> = _powerMetricsFlow.asStateFlow()

    private val _recommendationsFlow = MutableStateFlow<List<BatteryOptimizationRecommendation>>(emptyList())
    val recommendationsFlow: StateFlow<List<BatteryOptimizationRecommendation>> = _recommendationsFlow.asStateFlow()

    // Monitoring state
    private var isMonitoring = false
    private var monitoringJob: Job? = null

    // Voice assistant tracking
    private var voiceAssistantStartTime: Long? = null
    private var totalVoiceAssistantUsage: Long = 0  // milliseconds
    private var lastBatteryLevel: Int = -1

    // Configuration
    private val maxHistorySize = 1000
    private val monitoringInterval = 30_000L  // 30 seconds
    private val analysisInterval = 300_000L   // 5 minutes

    /**
     * Start battery monitoring
     */
    fun startMonitoring() {
        if (isMonitoring) return

        isMonitoring = true

        // Initialize with current battery info
        getCurrentBatteryInfo()?.let { initialInfo ->
            _batteryInfoFlow.value = initialInfo
            batteryHistory[System.currentTimeMillis()] = initialInfo
            lastBatteryLevel = initialInfo.level
        }

        monitoringJob = coroutineScope.launch {
            while (isMonitoring) {
                try {
                    collectBatteryInfo()
                    delay(monitoringInterval)
                } catch (e: Exception) {
                    // Log error but continue monitoring
                    kotlinx.coroutines.delay(60_000) // Wait 1 minute on error
                }
            }
        }

        // Start periodic analysis
        startPeriodicAnalysis()

        // Listen for charging state changes
        registerChargingReceiver()
    }

    /**
     * Stop battery monitoring
     */
    fun stopMonitoring() {
        isMonitoring = false
        monitoringJob?.cancel()
        monitoringJob = null

        unregisterChargingReceiver()
    }

    /**
     * Track voice assistant usage
     */
    fun startVoiceAssistantSession() {
        voiceAssistantStartTime = System.currentTimeMillis()
    }

    fun endVoiceAssistantSession() {
        voiceAssistantStartTime?.let { startTime ->
            val sessionDuration = System.currentTimeMillis() - startTime
            totalVoiceAssistantUsage += sessionDuration
            voiceAssistantStartTime = null
        }
    }

    /**
     * Get current battery information
     */
    fun getCurrentBatteryInfo(): BatteryInfo? {
        return try {
            val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
                // For Android 5.0+, use BatteryManager API
                val level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                val status = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS)

                BatteryInfo(
                    level = level,
                    scale = 100,
                    status = status,
                    health = BatteryManager.BATTERY_HEALTH_UNKNOWN,
                    plugged = getPluggedType(status),
                    temperature = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_TEMPERATURE) / 10f,
                    voltage = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_VOLTAGE),
                    technology = "Unknown"
                )
            } else {
                // Fallback for older versions (would need to register BroadcastReceiver)
                null
            }
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Get comprehensive power usage analysis
     */
    fun getPowerUsageAnalysis(): PowerConsumptionMetrics? {
        if (batteryHistory.size < 2) return null

        val sortedHistory = batteryHistory.toSortedMap().values.toList()
        val recent = sortedHistory.takeLast(10)

        if (recent.size < 2) return null

        // Calculate drain rates
        val timeSpan = (recent.last().timestamp - recent.first().timestamp) / (1000 * 60 * 60) // hours
        val levelDrop = recent.first().percentage - recent.last().percentage

        val currentDrainRate = if (timeSpan > 0) levelDrop / timeSpan else 0f
        val averageDrainRate = calculateAverageDrainRate(sortedHistory)

        // Estimate time remaining
        val estimatedTimeRemaining = if (currentDrainRate > 0)
            recent.last().percentage / currentDrainRate * 60 else Long.MAX_VALUE

        // Calculate voice assistant usage impact
        val voiceAssistantUsageImpact = calculateVoiceAssistantImpact()

        return PowerConsumptionMetrics(
            averageDrainRate = averageDrainRate,
            currentDrainRate = currentDrainRate,
            screenOnDrainRate = currentDrainRate * 1.2f,  // Estimate
            screenOffDrainRate = currentDrainRate * 0.8f, // Estimate
            voiceAssistantUsage = voiceAssistantUsageImpact,
            estimatedTimeRemaining = estimatedTimeRemaining.toLong()
        )
    }

    /**
     * Get battery optimization recommendations
     */
    fun getOptimizationRecommendations(): List<BatteryOptimizationRecommendation> {
        val currentBattery = _batteryInfoFlow.value ?: return emptyList()
        val powerMetrics = _powerMetricsFlow.value ?: return emptyList()

        val recommendations = mutableListOf<BatteryOptimizationRecommendation>()

        // Low battery recommendations
        if (currentBattery.isLow) {
            recommendations.add(
                BatteryOptimizationRecommendation(
                    type = BatteryOptimizationRecommendation.RecommendationType.BATTERY_SAVER,
                    priority = if (currentBattery.isCritical)
                        BatteryOptimizationRecommendation.Priority.CRITICAL
                    else
                        BatteryOptimizationRecommendation.Priority.HIGH,
                    title = "Pil Tasarruf Modu",
                    description = if (currentBattery.isCritical)
                        "Kritik pil seviyesi! Hemen pil tasarruf modunu etkinleştirin."
                    else
                        "Düşük pil seviyesi. Pil tasarruf modunu考虑考虑.",
                    estimatedSavings = 20f,
                    actionRequired = true
                )
            )
        }

        // High drain rate recommendations
        if (powerMetrics.currentDrainRate > 15f) {  // >15% per hour
            recommendations.add(
                BatteryOptimizationRecommendation(
                    type = BatteryOptimizationRecommendation.RecommendationType.APP_OPTIMIZATION,
                    priority = BatteryOptimizationRecommendation.Priority.MEDIUM,
                    title = "Uygulama Optimizasyonu",
                    description = "Yüksek pil tüketimi tespit edildi. Arka plan uygulamalarını kontrol edin.",
                    estimatedSavings = 10f
                )
            )
        }

        // Voice assistant specific recommendations
        if (powerMetrics.voiceAssistantUsage > 5f) {
            recommendations.add(
                BatteryOptimizationRecommendation(
                    type = BatteryOptimizationRecommendation.RecommendationType.BACKGROUND_SYNC,
                    priority = BatteryOptimizationRecommendation.Priority.LOW,
                    title = "Ses Asistanı Optimizasyonu",
                    description = "Ses asistanı pil tüketimi optimize edilebilir. Daha az sıklıkla kullanın.",
                    estimatedSavings = 3f
                )
            )
        }

        // Overheating recommendations
        if (currentBattery.isOverheating) {
            recommendations.add(
                BatteryOptimizationRecommendation(
                    type = BatteryOptimizationRecommendation.RecommendationType.BRIGHTNESS,
                    priority = BatteryOptimizationRecommendation.Priority.HIGH,
                    title = "Isınma Uyarısı",
                    description = "Cihazınız çok sıcak. Parlaklığı azaltın ve uygulamaları kapatın.",
                    estimatedSavings = 15f
                )
            )
        }

        // Update recommendations flow
        _recommendationsFlow.value = recommendations

        return recommendations
    }

    /**
     * Get battery health status
     */
    fun getBatteryHealth(): String {
        val current = _batteryInfoFlow.value ?: return "Unknown"

        return when (current.health) {
            BatteryManager.BATTERY_HEALTH_GOOD -> "İyi"
            BatteryManager.BATTERY_HEALTH_OVERHEAT -> "Aşırı Isınmış"
            BatteryManager.BATTERY_HEALTH_DEAD -> "Bitmiş"
            BatteryManager.BATTERY_HEALTH_OVER_VOLTAGE -> "Aşırı Voltaj"
            BatteryManager.BATTERY_HEALTH_UNSPECIFIED_FAILURE -> "Belirtilmemiş Hata"
            BatteryManager.BATTERY_HEALTH_COLD -> "Soğuk"
            else -> "Bilinmiyor"
        }
    }

    // Private helper methods

    private fun collectBatteryInfo() {
        getCurrentBatteryInfo()?.let { batteryInfo ->
            _batteryInfoFlow.value = batteryInfo
            batteryHistory[System.currentTimeMillis()] = batteryInfo

            // Trim history if too large
            if (batteryHistory.size > maxHistorySize) {
                val sortedKeys = batteryHistory.keys.sorted()
                val keysToRemove = sortedKeys.take(sortedKeys.size - maxHistorySize)
                keysToRemove.forEach { batteryHistory.remove(it) }
            }
        }
    }

    private fun startPeriodicAnalysis() {
        coroutineScope.launch {
            while (isMonitoring) {
                delay(analysisInterval)

                val analysis = getPowerUsageAnalysis()
                if (analysis != null) {
                    _powerMetricsFlow.value = analysis
                }

                getOptimizationRecommendations()
            }
        }
    }

    private fun calculateAverageDrainRate(history: List<BatteryInfo>): Float {
        if (history.size < 2) return 0f

        var totalDrainRate = 0f
        var count = 0

        for (i in 1 until history.size) {
            val timeDiff = (history[i].timestamp - history[i-1].timestamp) / (1000f * 60f * 60f) // hours
            if (timeDiff > 0) {
                val levelDiff = history[i-1].percentage - history[i].percentage
                totalDrainRate += levelDiff / timeDiff
                count++
            }
        }

        return if (count > 0) totalDrainRate / count else 0f
    }

    private fun calculateVoiceAssistantImpact(): Float {
        // Estimate voice assistant battery impact based on usage patterns
        val totalUptime = if (batteryHistory.isNotEmpty()) {
            (System.currentTimeMillis() - batteryHistory.keys.first()) / (1000f * 60f * 60f) // hours
        } else 0f

        if (totalUptime == 0f) return 0f

        val usagePercentage = (totalVoiceAssistantUsage / (totalUptime * 60 * 60 * 1000)) * 100

        // Estimate impact based on usage percentage and typical consumption
        return usagePercentage * 0.3f // Assume 30% of usage time contributes to battery drain
    }

    private fun getPluggedType(status: Int): Int {
        return when (status) {
            BatteryManager.BATTERY_STATUS_CHARGING -> BatteryManager.BATTERY_PLUGGED_USB
            BatteryManager.BATTERY_STATUS_FULL -> BatteryManager.BATTERY_PLUGGED_AC
            else -> 0
        }
    }

    private fun registerChargingReceiver() {
        // Implementation would register BroadcastReceiver for ACTION_POWER_CONNECTED
        // and ACTION_POWER_DISCONNECTED intents
    }

    private fun unregisterChargingReceiver() {
        // Implementation would unregister the BroadcastReceiver
    }

    /**
     * Get monitoring status and statistics
     */
    fun getMonitoringStatus(): Map<String, Any> {
        return mapOf(
            "is_monitoring" to isMonitoring,
            "history_size" to batteryHistory.size,
            "total_voice_assistant_usage_ms" to totalVoiceAssistantUsage,
            "monitoring_interval_ms" to monitoringInterval,
            "last_update" to (_batteryInfoFlow.value?.timestamp ?: 0L)
        )
    }

    /**
     * Clear all monitoring data
     */
    fun clearData() {
        batteryHistory.clear()
        powerUsageHistory.clear()
        totalVoiceAssistantUsage = 0
        voiceAssistantStartTime = null

        _batteryInfoFlow.value = null
        _powerMetricsFlow.value = null
        _recommendationsFlow.value = emptyList()
    }
}