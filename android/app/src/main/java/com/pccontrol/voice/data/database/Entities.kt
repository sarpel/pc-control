package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Entity representing a PC connection.
 */
@Entity(tableName = "pc_connections")
data class PCConnectionEntity(
    @PrimaryKey
    val connectionId: String,

    val devicePairingId: String?,

    val pcIpAddress: String,

    val pcMacAddress: String,

    val pcName: String,

    val status: String, // disconnected, connecting, connected, authenticated, error

    val latencyMs: Int?,

    val lastHeartbeat: Long?,

    val authenticationToken: String?,

    val certificateFingerprint: String?,

    val connectionCount: Int = 0,

    val totalConnectionTimeMs: Long = 0,

    val lastConnectedAt: Long?,

    val deviceName: String? = null,

    val deviceModel: String? = null,

    val createdAt: Long = System.currentTimeMillis(),

    val updatedAt: Long = System.currentTimeMillis()
)

/**
 * Entity representing command history.
 */
@Entity(tableName = "command_history")
data class CommandHistoryEntity(
    @PrimaryKey
    val historyId: String,

    val commandId: String,

    val deviceName: String,

    val transcription: String,

    val actionSummary: String,

    val success: Boolean,

    val executionTimeMs: Int,

    val timestamp: Long,

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

    val category: String = "general"
)

/**
 * Entity representing offline commands.
 */
@Entity(tableName = "offline_commands")
data class OfflineCommandEntity(
    @PrimaryKey
    val commandId: String,

    val transcription: String,

    val commandType: String,

    val parameters: String?, // JSON string

    val status: String, // pending, queued, executing, completed, failed

    val createdAt: Long = System.currentTimeMillis(),

    val executedAt: Long?,

    val errorMessage: String?,

    val deviceName: String? = null
)

/**
 * Entity representing device pairing information.
 */
@Entity(tableName = "device_pairing")
data class DevicePairingEntity(
    @PrimaryKey
    val pairingId: String,

    val androidDeviceId: String,

    val androidFingerprint: String,

    val pcFingerprint: String,

    val pairingCode: String,

    val status: String, // initiated, awaiting_confirmation, completed, failed, expired

    val createdAt: Long,

    val completedAt: Long?,

    val pcName: String?,

    val pcIpAddress: String?,

    val expiresAt: Long,

    val authenticationToken: String?,

    val deviceName: String?,

    val deviceModel: String?,

    val osVersion: String?,

    val pairingMethod: String = "manual" // manual, qr, nfc
)