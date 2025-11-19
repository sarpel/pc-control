package com.pccontrol.voice.data.repository

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import java.time.Instant

// Extension property for DataStore
private val Context.tileStateDataStore: DataStore<Preferences> by preferencesDataStore(name = "tile_state_repository")

/**
 * Tile State Repository
 *
 * Manages persistent state storage for the Quick Settings tile.
 * Handles tile state persistence, connection history, and performance
 * metrics with battery-optimized storage strategies.
 *
 * Features:
 * - Tile state persistence (active/inactive/unavailable)
 * - Connection history tracking
 * - Performance metrics storage
 * - Battery optimization (minimal storage I/O)
 * - Turkish state descriptions
 * - Automatic cleanup of old data
 * - State recovery after service restart
 * - Performance analytics
 *
 * Storage Strategy:
 * - Critical state: Immediate persistence
 * - Performance metrics: Batched updates
 * - Historical data: 24-hour retention
 * - Error states: Extended retention for debugging
 *
 * Task: T121 [US1] Add Quick Settings tile state persistence in android/app/src/main/java/com/pccontrol/voice/data/repository/TileStateRepository.kt
 */
class TileStateRepository(
    private val context: Context
) {
    private val dataStore: DataStore<Preferences> = context.tileStateDataStore

    // State keys
    companion object {
        private val KEY_TILE_STATE = stringPreferencesKey("tile_state")
        private val KEY_LAST_STATE_UPDATE = longPreferencesKey("last_state_update")
        private val KEY_LAST_CONNECTION_TIME = longPreferencesKey("last_connection_time")
        private val KEY_CONNECTION_DURATION = longPreferencesKey("connection_duration")
        private val KEY_TOTAL_COMMANDS_PROCESSED = intPreferencesKey("total_commands_processed")
        private val KEY_SUCCESSFUL_COMMANDS = intPreferencesKey("successful_commands")
        private val KEY_FAILED_COMMANDS = intPreferencesKey("failed_commands")
        private val KEY_LAST_ERROR_MESSAGE = stringPreferencesKey("last_error_message")
        private val KEY_LAST_ERROR_TIME = longPreferencesKey("last_error_time")
        private val KEY_PC_IP_ADDRESS = stringPreferencesKey("pc_ip_address")
        private val KEY_IS_FIRST_LAUNCH = booleanPreferencesKey("is_first_launch")
        private val KEY_TILE_CLICK_COUNT = intPreferencesKey("tile_click_count")
        private val KEY_AVERAGE_LATENCY = intPreferencesKey("average_latency")
        private val KEY_MAX_LATENCY = intPreferencesKey("max_latency")
        private val KEY_MIN_LATENCY = intPreferencesKey("min_latency")
        private val KEY_BATTERY_DRAIN_PERCENTAGE = floatPreferencesKey("battery_drain_percentage")
        private val KEY_UPTIME_HOURS = floatPreferencesKey("uptime_hours")
    }

    // Tile state enum
    enum class TileState(val value: String, val displayName: String) {
        INACTIVE("inactive", "Aktif Değil"),         // "Inactive"
        ACTIVE("active", "Aktif"),                   // "Active"
        CONNECTING("connecting", "Bağlanıyor"),      // "Connecting"
        UNAVAILABLE("unavailable", "Kullanılamıyor"), // "Unavailable"
        ERROR("error", "Hata");                      // "Error"
        
        companion object {
            fun fromValue(value: String): TileState {
                return values().find { it.value == value } ?: INACTIVE
            }
        }
    }

    // State flows
    val tileState: Flow<TileState>
        get() = dataStore.data.map { preferences ->
            TileState.fromValue(preferences[KEY_TILE_STATE] ?: TileState.INACTIVE.value)
        }

    val lastKnownPcIpAddress: Flow<String?> = dataStore.data.map { it[KEY_PC_IP_ADDRESS] }

    val lastStateUpdate: Flow<Instant> = dataStore.data.map { preferences ->
        val timestamp = preferences[KEY_LAST_STATE_UPDATE] ?: System.currentTimeMillis()
        Instant.ofEpochMilli(timestamp)
    }

    val lastConnectionTime: Flow<Instant?> = dataStore.data.map { preferences ->
        preferences[KEY_LAST_CONNECTION_TIME]?.let { Instant.ofEpochMilli(it) }
    }

    val connectionDuration: Flow<Long> = dataStore.data.map { preferences ->
        preferences[KEY_CONNECTION_DURATION] ?: 0L
    }

    val totalCommandsProcessed: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0
    }

    val successfulCommands: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_SUCCESSFUL_COMMANDS] ?: 0
    }

    val failedCommands: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_FAILED_COMMANDS] ?: 0
    }

    val lastErrorMessage: Flow<String?> = dataStore.data.map { preferences ->
        preferences[KEY_LAST_ERROR_MESSAGE]
    }

    val lastErrorTime: Flow<Instant?> = dataStore.data.map { preferences ->
        preferences[KEY_LAST_ERROR_TIME]?.let { Instant.ofEpochMilli(it) }
    }

    val pcIpAddress: Flow<String> = dataStore.data.map { preferences ->
        preferences[KEY_PC_IP_ADDRESS] ?: ""
    }

    val isFirstLaunch: Flow<Boolean> = dataStore.data.map { preferences ->
        preferences[KEY_IS_FIRST_LAUNCH] ?: true
    }

    val tileClickCount: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_TILE_CLICK_COUNT] ?: 0
    }

    val averageLatency: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_AVERAGE_LATENCY] ?: 0
    }

    val maxLatency: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_MAX_LATENCY] ?: 0
    }

    val minLatency: Flow<Int> = dataStore.data.map { preferences ->
        preferences[KEY_MIN_LATENCY] ?: Int.MAX_VALUE
    }

    val batteryDrainPercentage: Flow<Float> = dataStore.data.map { preferences ->
        preferences[KEY_BATTERY_DRAIN_PERCENTAGE] ?: 0f
    }

    val uptimeHours: Flow<Float> = dataStore.data.map { preferences ->
        preferences[KEY_UPTIME_HOURS] ?: 0f
    }

    // State management methods
    suspend fun setTileState(state: TileState) {
        dataStore.edit { preferences ->
            preferences[KEY_TILE_STATE] = state.value
            preferences[KEY_LAST_STATE_UPDATE] = System.currentTimeMillis()
        }
    }

    suspend fun recordConnection(ipAddress: String) {
        dataStore.edit { preferences ->
            preferences[KEY_LAST_CONNECTION_TIME] = System.currentTimeMillis()
            preferences[KEY_PC_IP_ADDRESS] = ipAddress
            if (preferences[KEY_IS_FIRST_LAUNCH] != false) {
                preferences[KEY_IS_FIRST_LAUNCH] = false
            }
        }
    }

    suspend fun recordDisconnection(duration: Long) {
        dataStore.edit { preferences ->
            preferences[KEY_CONNECTION_DURATION] = duration
        }
    }

    suspend fun incrementTileClickCount() {
        dataStore.edit { preferences ->
            val currentCount = preferences[KEY_TILE_CLICK_COUNT] ?: 0
            preferences[KEY_TILE_CLICK_COUNT] = currentCount + 1
        }
    }

    // Command tracking methods
    suspend fun recordCommandProcessed(successful: Boolean, latency: Int? = null) {
        dataStore.edit { preferences ->
            val totalCommands = (preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0) + 1
            preferences[KEY_TOTAL_COMMANDS_PROCESSED] = totalCommands

            if (successful) {
                val successfulCommands = (preferences[KEY_SUCCESSFUL_COMMANDS] ?: 0) + 1
                preferences[KEY_SUCCESSFUL_COMMANDS] = successfulCommands
            } else {
                val failedCommands = (preferences[KEY_FAILED_COMMANDS] ?: 0) + 1
                preferences[KEY_FAILED_COMMANDS] = failedCommands
            }

            // Update latency statistics
            latency?.let { lat ->
                val currentMax = preferences[KEY_MAX_LATENCY] ?: 0
                val currentMin = preferences[KEY_MIN_LATENCY] ?: Int.MAX_VALUE
                val currentAverage = preferences[KEY_AVERAGE_LATENCY] ?: 0

                preferences[KEY_MAX_LATENCY] = maxOf(currentMax, lat)
                preferences[KEY_MIN_LATENCY] = minOf(currentMin, lat)

                // Calculate running average
                preferences[KEY_AVERAGE_LATENCY] = ((currentAverage * (totalCommands - 1) + lat) / totalCommands).toInt()
            }
        }
    }

    suspend fun recordError(errorMessage: String) {
        dataStore.edit { preferences ->
            preferences[KEY_LAST_ERROR_MESSAGE] = errorMessage
            preferences[KEY_LAST_ERROR_TIME] = System.currentTimeMillis()
        }
    }

    // Performance monitoring methods
    suspend fun updateBatteryDrain(percentageChange: Float) {
        dataStore.edit { preferences ->
            val currentDrain = preferences[KEY_BATTERY_DRAIN_PERCENTAGE] ?: 0f
            preferences[KEY_BATTERY_DRAIN_PERCENTAGE] = currentDrain + percentageChange
        }
    }

    suspend fun updateUptime(additionalHours: Float) {
        dataStore.edit { preferences ->
            val currentUptime = preferences[KEY_UPTIME_HOURS] ?: 0f
            preferences[KEY_UPTIME_HOURS] = currentUptime + additionalHours
        }
    }

    // Analytics methods
    suspend fun getSuccessRate(): Flow<Float> {
        return dataStore.data.map { preferences ->
            val total = preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0
            val successful = preferences[KEY_SUCCESSFUL_COMMANDS] ?: 0
            if (total > 0) (successful.toFloat() / total) else 0f
        }
    }

    suspend fun getPerformanceMetrics(): Flow<TilePerformanceMetrics> {
        return dataStore.data.map { preferences ->
            TilePerformanceMetrics(
                totalCommands = preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0,
                successRate = calculateSuccessRate(preferences),
                averageLatency = preferences[KEY_AVERAGE_LATENCY] ?: 0,
                maxLatency = preferences[KEY_MAX_LATENCY] ?: 0,
                minLatency = preferences[KEY_MIN_LATENCY] ?: 0,
                batteryDrain = preferences[KEY_BATTERY_DRAIN_PERCENTAGE] ?: 0f,
                uptimeHours = preferences[KEY_UPTIME_HOURS] ?: 0f,
                tileClickCount = preferences[KEY_TILE_CLICK_COUNT] ?: 0
            )
        }
    }

    private fun calculateSuccessRate(preferences: Preferences): Float {
        val total = preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0
        val successful = preferences[KEY_SUCCESSFUL_COMMANDS] ?: 0
        return if (total > 0) (successful.toFloat() / total) else 0f
    }

    // Cleanup methods
    suspend fun clearOldData(retentionHours: Int = 24) {
        dataStore.edit { preferences ->
            val cutoffTime = System.currentTimeMillis() - (retentionHours * 60 * 60 * 1000L)

            // Clear old error messages
            if ((preferences[KEY_LAST_ERROR_TIME] ?: 0) < cutoffTime) {
                preferences.remove(KEY_LAST_ERROR_MESSAGE)
                preferences.remove(KEY_LAST_ERROR_TIME)
            }
        }
    }

    suspend fun resetToDefaults() {
        dataStore.edit { preferences ->
            preferences.clear()
        }
    }

    // Export/Import methods for backup/restore
    suspend fun exportState(): TileStateExport {
        val preferences = dataStore.data.first()
        return TileStateExport(
            tileState = preferences[KEY_TILE_STATE] ?: TileState.INACTIVE.value,
            lastConnectionTime = preferences[KEY_LAST_CONNECTION_TIME] ?: 0,
            totalCommands = preferences[KEY_TOTAL_COMMANDS_PROCESSED] ?: 0,
            successfulCommands = preferences[KEY_SUCCESSFUL_COMMANDS] ?: 0,
            failedCommands = preferences[KEY_FAILED_COMMANDS] ?: 0,
            pcIpAddress = preferences[KEY_PC_IP_ADDRESS] ?: "",
            batteryDrain = preferences[KEY_BATTERY_DRAIN_PERCENTAGE] ?: 0f,
            uptimeHours = preferences[KEY_UPTIME_HOURS] ?: 0f
        )
    }

    suspend fun importState(export: TileStateExport) {
        dataStore.edit { preferences ->
            preferences[KEY_TILE_STATE] = export.tileState
            preferences[KEY_LAST_CONNECTION_TIME] = export.lastConnectionTime
            preferences[KEY_TOTAL_COMMANDS_PROCESSED] = export.totalCommands
            preferences[KEY_SUCCESSFUL_COMMANDS] = export.successfulCommands
            preferences[KEY_FAILED_COMMANDS] = export.failedCommands
            preferences[KEY_PC_IP_ADDRESS] = export.pcIpAddress
            preferences[KEY_BATTERY_DRAIN_PERCENTAGE] = export.batteryDrain
            preferences[KEY_UPTIME_HOURS] = export.uptimeHours
        }
    }

    /**
     * Data classes for analytics and backup
     */
    data class TilePerformanceMetrics(
        val totalCommands: Int,
        val successRate: Float,
        val averageLatency: Int,
        val maxLatency: Int,
        val minLatency: Int,
        val batteryDrain: Float,
        val uptimeHours: Float,
        val tileClickCount: Int
    )

    data class TileStateExport(
        val tileState: String,
        val lastConnectionTime: Long,
        val totalCommands: Int,
        val successfulCommands: Int,
        val failedCommands: Int,
        val pcIpAddress: String,
        val batteryDrain: Float,
        val uptimeHours: Float
    )

}

/**
 * Tile state manager for high-level operations
 */
class TileStateManager(private val repository: TileStateRepository) {

    suspend fun handleTileClick() {
        repository.incrementTileClickCount()
        // Additional tile click handling logic would go here
    }

    suspend fun handleConnectionEstablished(ipAddress: String) {
        repository.recordConnection(ipAddress)
        repository.setTileState(TileStateRepository.TileState.ACTIVE)
    }

    suspend fun handleConnectionLost(duration: Long) {
        repository.recordDisconnection(duration)
        repository.setTileState(TileStateRepository.TileState.INACTIVE)
    }

    suspend fun handleServiceError(errorMessage: String) {
        repository.recordError(errorMessage)
        repository.setTileState(TileStateRepository.TileState.ERROR)
    }

    suspend fun handleServiceUnavailable() {
        repository.setTileState(TileStateRepository.TileState.UNAVAILABLE)
    }

    val turkishStatusMessage: Flow<String> = repository.tileState.map { state ->
        when (state) {
            TileStateRepository.TileState.ACTIVE -> "PC'ye bağlı - Ses komutu bekleniyor"
            TileStateRepository.TileState.INACTIVE -> "Bağlı değil - Dokun bağlanmak için"
            TileStateRepository.TileState.CONNECTING -> "Bağlanıyor..."
            TileStateRepository.TileState.UNAVAILABLE -> "Hizmet kullanılamıyor"
            TileStateRepository.TileState.ERROR -> "Bağlantı hatası"
        }
    }
}