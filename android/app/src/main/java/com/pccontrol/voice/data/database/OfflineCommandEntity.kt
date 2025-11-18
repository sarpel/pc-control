package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey

/**
 * Room entity for storing offline commands.
 */
@Entity(tableName = "offline_commands")
data class OfflineCommandEntity(
    @PrimaryKey val commandId: String,
    val transcription: String,
    val actionType: String,
    val parameters: String, // JSON string
    val status: String,
    val deviceName: String? = null,
    val createdAt: Long,
    val executedAt: Long? = null,
    val retryCount: Int = 0,
    val maxRetries: Int = 3
)