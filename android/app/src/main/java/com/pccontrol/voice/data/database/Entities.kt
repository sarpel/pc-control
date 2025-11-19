package com.pccontrol.voice.data.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Entity representing a PC connection.
 */
@Entity(tableName = "pc_connections")
data class PCConnectionEntity(
    @PrimaryKey
    @ColumnInfo(name = "connection_id")
    val connectionId: String,

    @ColumnInfo(name = "device_pairing_id")
    val devicePairingId: String?,

    @ColumnInfo(name = "pc_ip_address")
    val pcIpAddress: String,

    @ColumnInfo(name = "pc_mac_address")
    val pcMacAddress: String,

    @ColumnInfo(name = "pc_name")
    val pcName: String,

    val status: String, // disconnected, connecting, connected, authenticated, error

    @ColumnInfo(name = "latency_ms")
    val latencyMs: Int?,

    @ColumnInfo(name = "last_heartbeat")
    val lastHeartbeat: Long?,

    @ColumnInfo(name = "authentication_token")
    val authenticationToken: String?,

    @ColumnInfo(name = "certificate_fingerprint")
    val certificateFingerprint: String?,

    @ColumnInfo(name = "connection_count")
    val connectionCount: Int = 0,

    @ColumnInfo(name = "total_connection_time_ms")
    val totalConnectionTimeMs: Long = 0,

    @ColumnInfo(name = "last_connected_at")
    val lastConnectedAt: Long?,

    @ColumnInfo(name = "device_name")
    val deviceName: String? = null,

    @ColumnInfo(name = "device_model")
    val deviceModel: String? = null,

    val createdAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
)

/**
 * Entity representing command history.
 */
@Entity(tableName = "command_history")
data class CommandHistoryEntity(
    @PrimaryKey
    @ColumnInfo(name = "history_id")
    val historyId: String,

    @ColumnInfo(name = "command_id")
    val commandId: String,

    @ColumnInfo(name = "device_name")
    val deviceName: String,

    val transcription: String,

    @ColumnInfo(name = "action_summary")
    val actionSummary: String,

    val success: Boolean,

    @ColumnInfo(name = "execution_time_ms")
    val executionTimeMs: Int,

    val timestamp: Long,

    @ColumnInfo(name = "expires_at")
    val expiresAt: Long
)

/**
 * Entity representing application settings.
 */
@Entity(tableName = "app_settings")
data class AppSettingsEntity(
    @PrimaryKey
    val key: String,

    val value: String,

    val category: String = "general",

    val description: String? = null,

    @ColumnInfo(name = "is_encrypted")
    val isEncrypted: Boolean = false,

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "updated_at")
    val updatedAt: Long = System.currentTimeMillis()
)

/**
 * Entity representing offline commands.
 */
@Entity(tableName = "offline_commands")
data class OfflineCommandEntity(
    @PrimaryKey
    @ColumnInfo(name = "command_id")
    val commandId: String,

    val transcription: String,

    @ColumnInfo(name = "command_type")
    val commandType: String,

    val parameters: String?, // JSON string

    val status: String, // pending, queued, executing, completed, failed

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis(),

    @ColumnInfo(name = "executed_at")
    val executedAt: Long?,

    @ColumnInfo(name = "error_message")
    val errorMessage: String?,

    @ColumnInfo(name = "device_name")
    val deviceName: String? = null
)

/**
 * Entity representing device pairing information.
 */
@Entity(tableName = "device_pairing")
data class DevicePairingEntity(
    @PrimaryKey
    @ColumnInfo(name = "pairing_id")
    val pairingId: String,

    @ColumnInfo(name = "android_device_id")
    val androidDeviceId: String,

    @ColumnInfo(name = "android_fingerprint")
    val androidFingerprint: String,

    @ColumnInfo(name = "pc_fingerprint")
    val pcFingerprint: String,

    @ColumnInfo(name = "pairing_code")
    val pairingCode: String,

    val status: String, // initiated, awaiting_confirmation, completed, failed, expired

    @ColumnInfo(name = "created_at")
    val createdAt: Long,

    @ColumnInfo(name = "completed_at")
    val completedAt: Long?,

    @ColumnInfo(name = "pc_name")
    val pcName: String?,

    @ColumnInfo(name = "pc_ip_address")
    val pcIpAddress: String?,

    @ColumnInfo(name = "expires_at")
    val expiresAt: Long,

    @ColumnInfo(name = "authentication_token")
    val authenticationToken: String?,

    @ColumnInfo(name = "device_name")
    val deviceName: String?,

    @ColumnInfo(name = "device_model")
    val deviceModel: String?,

    @ColumnInfo(name = "os_version")
    val osVersion: String?,

    @ColumnInfo(name = "pairing_method")
    val pairingMethod: String = "manual", // manual, qr, nfc

    @ColumnInfo(name = "created_by")
    val createdBy: String = "android_app"
)