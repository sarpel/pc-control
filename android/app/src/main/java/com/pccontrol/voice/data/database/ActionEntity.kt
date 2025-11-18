package com.pccontrol.voice.data.database

import androidx.room.Entity
import androidx.room.PrimaryKey
import androidx.room.ForeignKey
import androidx.room.Index

/**
 * Room entity for storing actions.
 */
@Entity(
    tableName = "actions",
    foreignKeys = [
        ForeignKey(
            entity = VoiceCommandEntity::class,
            parentColumns = ["commandId"],
            childColumns = ["commandId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index(value = ["commandId"])]
)
data class ActionEntity(
    @PrimaryKey val actionId: String,
    val commandId: String,
    val actionType: String,
    val parameters: String, // JSON string
    val status: String,
    val result: String? = null, // JSON string
    val errorMessage: String? = null,
    val executionTimeMs: Int? = null,
    val startedAt: Long? = null,
    val completedAt: Long? = null,
    val priority: Int = 0,
    val requiresConfirmation: Boolean = false,
    val timeoutMs: Int = 30000,
    val retryCount: Int = 0,
    val maxRetries: Int = 3,
    val createdAt: Long,
    val updatedAt: Long
)