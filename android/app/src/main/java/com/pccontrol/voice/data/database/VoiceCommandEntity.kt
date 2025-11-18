package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.util.*

/**
 * Room entity for storing voice commands.
 */
@Entity(tableName = "voice_commands")
data class VoiceCommandEntity(
    @PrimaryKey val commandId: String,
    val transcription: String,
    val confidence: Float,
    val timestamp: Long,
    val durationMs: Int,
    val language: String,
    val status: String,
    val deviceId: String,
    val sessionId: String? = null,
    val audioFilePath: String? = null,
    val errorMessage: String? = null,
    val executionTimeMs: Int? = null,
    val createdAt: Long,
    val updatedAt: Long
)