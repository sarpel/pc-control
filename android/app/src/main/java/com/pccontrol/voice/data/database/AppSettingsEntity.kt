package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room entity for storing application settings.
 */
@Entity(tableName = "app_settings")
data class AppSettingsEntity(
    @PrimaryKey val key: String,
    val value: String,
    val category: String,
    val description: String? = null,
    val isEncrypted: Boolean = false,
    val createdAt: Long,
    val updatedAt: Long
)