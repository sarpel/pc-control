package com.pccontrol.voice.data.models

import java.util.*

/**
 * Data class representing a voice command.
 * This model represents transcribed voice commands that will be processed and executed.
 */
data class VoiceCommand(
    val commandId: UUID,
    val transcription: String,
    val confidence: Float,
    val timestamp: Long,
    val durationMs: Int,
    val language: String = "tr",
    val status: CommandStatus = CommandStatus.PENDING,
    val deviceId: String,
    val sessionId: String? = null,
    val audioFilePath: String? = null,
    val actions: List<Action> = emptyList(),
    val result: CommandResult? = null,
    val errorMessage: String? = null,
    val executionTimeMs: Int? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
) {
    companion object {
        fun fromEntity(entity: com.pccontrol.voice.data.database.VoiceCommandEntity): VoiceCommand {
            return VoiceCommand(
                commandId = UUID.fromString(entity.commandId),
                transcription = entity.transcription,
                confidence = entity.confidence,
                timestamp = entity.timestamp,
                durationMs = entity.durationMs,
                language = entity.language,
                status = CommandStatus.fromString(entity.status),
                deviceId = entity.deviceId,
                sessionId = entity.sessionId,
                audioFilePath = entity.audioFilePath,
                actions = emptyList(), // Would need to load actions separately
                result = null, // Would need to parse from result JSON
                errorMessage = entity.errorMessage,
                executionTimeMs = entity.executionTimeMs,
                createdAt = entity.createdAt,
                updatedAt = entity.updatedAt
            )
        }

        fun create(
            transcription: String,
            confidence: Float,
            deviceId: String,
            durationMs: Int,
            language: String = "tr"
        ): VoiceCommand {
            return VoiceCommand(
                commandId = UUID.randomUUID(),
                transcription = transcription,
                confidence = confidence,
                timestamp = System.currentTimeMillis(),
                durationMs = durationMs,
                language = language,
                deviceId = deviceId
            )
        }
    }

    fun toEntity(): com.pccontrol.voice.data.database.VoiceCommandEntity {
        return com.pccontrol.voice.data.database.VoiceCommandEntity(
            commandId = commandId.toString(),
            transcription = transcription,
            confidence = confidence,
            timestamp = timestamp,
            durationMs = durationMs,
            language = language,
            status = status.value,
            deviceId = deviceId,
            sessionId = sessionId,
            audioFilePath = audioFilePath,
            errorMessage = errorMessage,
            executionTimeMs = executionTimeMs,
            createdAt = createdAt,
            updatedAt = updatedAt
        )
    }

    fun withStatus(newStatus: CommandStatus): VoiceCommand {
        return copy(
            status = newStatus,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun withActions(newActions: List<Action>): VoiceCommand {
        return copy(
            actions = newActions,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun withResult(result: CommandResult): VoiceCommand {
        return copy(
            result = result,
            status = if (result.success) CommandStatus.COMPLETED else CommandStatus.FAILED,
            executionTimeMs = result.executionTimeMs,
            errorMessage = if (!result.success) result.errorMessage else null,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun isValid(): Boolean {
        return transcription.isNotBlank() &&
                confidence in 0.0f..1.0f &&
                durationMs > 0 &&
                deviceId.isNotBlank()
    }
}

/**
 * Enum representing voice command status.
 */
enum class CommandStatus(val value: String) {
    PENDING("pending"),
    PROCESSING("processing"),
    EXECUTING("executing"),
    COMPLETED("completed"),
    FAILED("failed");

    companion object {
        fun fromString(value: String): CommandStatus {
            return values().find { it.value == value } ?: PENDING
        }
    }

    override fun toString(): String = value
}

/**
 * Data class representing command execution result.
 */
data class CommandResult(
    val success: Boolean,
    val executionTimeMs: Int,
    val actionResults: List<ActionResult> = emptyList(),
    val errorMessage: String? = null,
    val metadata: Map<String, Any> = emptyMap()
)

/**
 * Data class representing individual action execution result.
 */
data class ActionResult(
    val actionId: String,
    val actionType: String,
    val success: Boolean,
    val executionTimeMs: Int,
    val result: Map<String, Any>? = null,
    val errorMessage: String? = null
)