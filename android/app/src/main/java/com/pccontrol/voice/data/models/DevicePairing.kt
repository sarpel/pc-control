package com.pccontrol.voice.data.models

import java.util.*

/**
 * Data class representing device pairing information.
 * This model manages the secure pairing between Android device and PC.
 */
data class DevicePairing(
    val pairingId: UUID,
    val androidDeviceId: String,
    val androidFingerprint: String,
    val pcFingerprint: String,
    val pairingCode: String,
    val status: PairingStatus = PairingStatus.INITIATED,
    val createdAt: Long,
    val completedAt: Long? = null,
    val pcName: String? = null,
    val pcIpAddress: String? = null,
    val expiresAt: Long,
    val authenticationToken: String? = null,
    val deviceName: String? = null,
    val deviceModel: String? = null,
    val osVersion: String? = null,
    val pairingMethod: PairingMethod = PairingMethod.MANUAL,
    val createdBy: String = "android_app",
    val metadata: Map<String, String> = emptyMap()
) {
    companion object {
        fun fromEntity(entity: com.pccontrol.voice.data.database.DevicePairingEntity): DevicePairing {
            return DevicePairing(
                pairingId = UUID.fromString(entity.pairingId),
                androidDeviceId = entity.androidDeviceId,
                androidFingerprint = entity.androidFingerprint,
                pcFingerprint = entity.pcFingerprint,
                pairingCode = entity.pairingCode,
                status = PairingStatus.fromString(entity.status),
                createdAt = entity.createdAt,
                completedAt = entity.completedAt,
                pcName = entity.pcName,
                pcIpAddress = entity.pcIpAddress,
                expiresAt = entity.expiresAt,
                authenticationToken = entity.authenticationToken,
                deviceName = entity.deviceName,
                deviceModel = entity.deviceModel,
                osVersion = entity.osVersion,
                pairingMethod = PairingMethod.fromString(entity.pairingMethod),
                createdBy = entity.createdBy
            )
        }

        fun create(
            androidDeviceId: String,
            androidFingerprint: String,
            pcFingerprint: String,
            pairingCode: String,
            pcName: String? = null,
            pcIpAddress: String? = null,
            deviceName: String? = null,
            deviceModel: String? = null,
            osVersion: String? = null,
            pairingMethod: PairingMethod = PairingMethod.MANUAL,
            expiresMinutes: Int = 10
        ): DevicePairing {
            val now = System.currentTimeMillis()
            val expiresAt = now + (expiresMinutes * 60 * 1000)

            return DevicePairing(
                pairingId = UUID.randomUUID(),
                androidDeviceId = androidDeviceId,
                androidFingerprint = androidFingerprint,
                pcFingerprint = pcFingerprint,
                pairingCode = pairingCode,
                pcName = pcName,
                pcIpAddress = pcIpAddress,
                deviceName = deviceName,
                deviceModel = deviceModel,
                osVersion = osVersion,
                pairingMethod = pairingMethod,
                createdAt = now,
                expiresAt = expiresAt
            )
        }

        fun generatePairingCode(): String {
            return (100000..999999).random().toString()
        }
    }

    fun toEntity(): com.pccontrol.voice.data.database.DevicePairingEntity {
        return com.pccontrol.voice.data.database.DevicePairingEntity(
            pairingId = pairingId.toString(),
            androidDeviceId = androidDeviceId,
            androidFingerprint = androidFingerprint,
            pcFingerprint = pcFingerprint,
            pairingCode = pairingCode,
            status = status.value,
            createdAt = createdAt,
            completedAt = completedAt,
            pcName = pcName,
            pcIpAddress = pcIpAddress,
            expiresAt = expiresAt,
            authenticationToken = authenticationToken,
            deviceName = deviceName,
            deviceModel = deviceModel,
            osVersion = osVersion,
            pairingMethod = pairingMethod.value,
            createdBy = createdBy
        )
    }

    fun withStatus(newStatus: PairingStatus): DevicePairing {
        val now = System.currentTimeMillis()
        return copy(
            status = newStatus,
            completedAt = if (newStatus == PairingStatus.COMPLETED && completedAt == null) now else completedAt
        )
    }

    fun withPcDetails(pcName: String, pcIpAddress: String): DevicePairing {
        return copy(
            pcName = pcName,
            pcIpAddress = pcIpAddress
        )
    }

    fun withAuthToken(authenticationToken: String): DevicePairing {
        return copy(
            authenticationToken = authenticationToken,
            status = PairingStatus.COMPLETED,
            completedAt = completedAt ?: System.currentTimeMillis()
        )
    }

    fun isExpired(): Boolean {
        return System.currentTimeMillis() > expiresAt
    }

    fun isValid(): Boolean {
        return pairingCode.length == 6 &&
                androidDeviceId.isNotBlank() &&
                androidFingerprint.isNotBlank() &&
                pcFingerprint.isNotBlank() &&
                !isExpired()
    }

    fun canComplete(): Boolean {
        return status == PairingStatus.AWAITING_CONFIRMATION &&
                !isExpired() &&
                authenticationToken != null
    }

    fun timeUntilExpiration(): Long {
        return maxOf(0, expiresAt - System.currentTimeMillis())
    }

    fun getExpirationMinutes(): Int {
        return (timeUntilExpiration() / (60 * 1000)).toInt()
    }
}

/**
 * Enum representing pairing status.
 */
enum class PairingStatus(val value: String) {
    INITIATED("initiated"),
    AWAITING_CONFIRMATION("awaiting_confirmation"),
    COMPLETED("completed"),
    FAILED("failed"),
    EXPIRED("expired"),
    CANCELLED("cancelled");

    companion object {
        fun fromString(value: String): PairingStatus {
            return values().find { it.value == value } ?: INITIATED
        }
    }

    override fun toString(): String = value

    fun isActive(): Boolean {
        return this in listOf(INITIATED, AWAITING_CONFIRMATION)
    }

    fun isFinal(): Boolean {
        return this in listOf(COMPLETED, FAILED, EXPIRED, CANCELLED)
    }

    fun canTransitionTo(newStatus: PairingStatus): Boolean {
        return when (this) {
            INITIATED -> newStatus in listOf(AWAITING_CONFIRMATION, FAILED, EXPIRED, CANCELLED)
            AWAITING_CONFIRMATION -> newStatus in listOf(COMPLETED, FAILED, EXPIRED, CANCELLED)
            COMPLETED -> false // Final state
            FAILED -> false // Final state
            EXPIRED -> false // Final state
            CANCELLED -> false // Final state
        }
    }
}

/**
 * Enum representing pairing methods.
 */
enum class PairingMethod(val value: String, val displayName: String) {
    MANUAL("manual", "Manual Pairing"),
    QR_CODE("qr", "QR Code"),
    NFC("nfc", "NFC Tap"),
    BLUETOOTH("bluetooth", "Bluetooth"),
    NETWORK_DISCOVERY("network_discovery", "Network Discovery");

    companion object {
        fun fromString(value: String): PairingMethod {
            return values().find { it.value == value } ?: MANUAL
        }

        fun getAvailableMethods(): List<PairingMethod> {
            return listOf(MANUAL, QR_CODE, NETWORK_DISCOVERY)
        }
    }

    override fun toString(): String = displayName
}

/**
 * Data class representing pairing request/response.
 */
data class PairingRequest(
    val pairingId: UUID,
    val androidDeviceId: String,
    val androidFingerprint: String,
    val deviceName: String? = null,
    val deviceModel: String? = null,
    val osVersion: String? = null,
    val pairingMethod: PairingMethod = PairingMethod.MANUAL
)

data class PairingResponse(
    val pairingId: UUID,
    val pcFingerprint: String,
    val pcName: String,
    val pcIpAddress: String,
    val status: PairingStatus,
    val authenticationToken: String? = null,
    val errorMessage: String? = null
)

/**
 * Data class representing pairing confirmation.
 */
data class PairingConfirmation(
    val pairingId: UUID,
    val confirmationCode: String,
    val androidFingerprint: String
)

data class PairingResult(
    val success: Boolean,
    val pairing: DevicePairing? = null,
    val errorMessage: String? = null,
    val errorCode: String? = null
)