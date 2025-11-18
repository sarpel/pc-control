package com.pccontrol.voice.data.models

import java.util.*

/**
 * Data class representing a PC connection.
 * This is the Kotlin version of the Python PCConnection model.
 */
data class PCConnection(
    val connectionId: UUID,
    val pcIpAddress: String,
    val pcMacAddress: String,
    val pcName: String,
    val status: ConnectionStatus,
    val latencyMs: Int? = null,
    val lastHeartbeat: Long? = null,
    val authenticationToken: String? = null,
    val certificateFingerprint: String? = null,
    val devicePairingId: String? = null,
    val connectionCount: Int = 0,
    val totalConnectionTimeMs: Long = 0L,
    val lastConnectedAt: Long? = null,
    val deviceName: String? = null,
    val deviceModel: String? = null
) {
    companion object {
        fun fromEntity(entity: com.pccontrol.voice.data.database.PCConnectionEntity): PCConnection {
            return PCConnection(
                connectionId = UUID.fromString(entity.connectionId),
                pcIpAddress = entity.pcIpAddress,
                pcMacAddress = entity.pcMacAddress,
                pcName = entity.pcName,
                status = ConnectionStatus.fromString(entity.status),
                latencyMs = entity.latencyMs,
                lastHeartbeat = entity.lastHeartbeat,
                authenticationToken = entity.authenticationToken,
                certificateFingerprint = entity.certificateFingerprint,
                devicePairingId = entity.devicePairingId,
                connectionCount = entity.connectionCount,
                totalConnectionTimeMs = entity.totalConnectionTimeMs,
                lastConnectedAt = entity.lastConnectedAt,
                deviceName = entity.deviceName,
                deviceModel = entity.deviceModel
            )
        }
    }

    fun toEntity(): com.pccontrol.voice.data.database.PCConnectionEntity {
        return com.pccontrol.voice.data.database.PCConnectionEntity(
            connectionId = connectionId.toString(),
            devicePairingId = devicePairingId,
            pcIpAddress = pcIpAddress,
            pcMacAddress = pcMacAddress,
            pcName = pcName,
            status = status.value,
            latencyMs = latencyMs,
            lastHeartbeat = lastHeartbeat,
            authenticationToken = authenticationToken,
            certificateFingerprint = certificateFingerprint,
            connectionCount = connectionCount,
            totalConnectionTimeMs = totalConnectionTimeMs,
            lastConnectedAt = lastConnectedAt,
            deviceName = deviceName,
            deviceModel = deviceModel
        )
    }
}

/**
 * Enum representing connection status.
 */
enum class ConnectionStatus(val value: String) {
    DISCONNECTED("disconnected"),
    CONNECTING("connecting"),
    CONNECTED("connected"),
    AUTHENTICATED("authenticated"),
    ERROR("error");

    companion object {
        fun fromString(value: String): ConnectionStatus {
            return values().find { it.value == value } ?: ERROR
        }
    }

    override fun toString(): String = value
}