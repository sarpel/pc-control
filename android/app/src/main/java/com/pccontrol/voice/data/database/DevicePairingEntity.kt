package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room entity for storing device pairing information.
 */
@Entity(tableName = "device_pairing")
data class DevicePairingEntity(
    @PrimaryKey val pairingId: String,
    val androidDeviceId: String,
    val androidFingerprint: String,
    val pcFingerprint: String,
    val pairingCode: String,
    val status: String,
    val createdAt: Long,
    val completedAt: Long? = null,
    val pcName: String? = null,
    val pcIpAddress: String? = null,
    val expiresAt: Long,
    val authenticationToken: String? = null,
    val deviceName: String? = null,
    val deviceModel: String? = null,
    val osVersion: String? = null,
    val pairingMethod: String,
    val createdBy: String = "android_app"
)