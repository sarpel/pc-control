package com.pccontrol.voice.data.models

import java.util.*

/**
 * Data class representing an action to be executed for a voice command.
 * Actions are the individual steps that make up a voice command execution.
 */
data class Action(
    val actionId: UUID,
    val commandId: UUID,
    val actionType: ActionType,
    val parameters: Map<String, Any>,
    val status: ActionStatus = ActionStatus.PENDING,
    val result: Map<String, Any>? = null,
    val errorMessage: String? = null,
    val executionTimeMs: Int? = null,
    val startedAt: Long? = null,
    val completedAt: Long? = null,
    val priority: Int = 0,
    val requiresConfirmation: Boolean = false,
    val timeoutMs: Int = 30000,
    val retryCount: Int = 0,
    val maxRetries: Int = 3,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
) {
    companion object {
        fun fromEntity(entity: com.pccontrol.voice.data.database.ActionEntity): Action {
            return Action(
                actionId = UUID.fromString(entity.actionId),
                commandId = UUID.fromString(entity.commandId),
                actionType = ActionType.fromString(entity.actionType),
                parameters = parseParametersJson(entity.parameters),
                status = ActionStatus.fromString(entity.status),
                result = parseResultJson(entity.result),
                errorMessage = entity.errorMessage,
                executionTimeMs = entity.executionTimeMs,
                startedAt = entity.startedAt,
                completedAt = entity.completedAt,
                priority = entity.priority,
                requiresConfirmation = entity.requiresConfirmation,
                timeoutMs = entity.timeoutMs,
                retryCount = entity.retryCount,
                maxRetries = entity.maxRetries,
                createdAt = entity.createdAt,
                updatedAt = entity.updatedAt
            )
        }

        /**
         * Parses JSON string to parameters Map.
         * Returns empty map if JSON is null, blank, or invalid.
         */
        private fun parseParametersJson(json: String?): Map<String, Any> {
            return try {
                if (json.isNullOrBlank()) emptyMap()
                else org.json.JSONObject(json).toMap()
            } catch (e: Exception) {
                emptyMap()
            }
        }

        /**
         * Parses JSON string to result Map.
         * Returns null if JSON is null, blank, or invalid.
         */
        private fun parseResultJson(json: String?): Map<String, Any>? {
            return try {
                if (json.isNullOrBlank()) null
                else org.json.JSONObject(json).toMap()
            } catch (e: Exception) {
                null
            }
        }

        fun create(
            commandId: UUID,
            actionType: ActionType,
            parameters: Map<String, Any>,
            priority: Int = 0,
            requiresConfirmation: Boolean = false,
            timeoutMs: Int = 30000
        ): Action {
            return Action(
                actionId = UUID.randomUUID(),
                commandId = commandId,
                actionType = actionType,
                parameters = parameters,
                priority = priority,
                requiresConfirmation = requiresConfirmation,
                timeoutMs = timeoutMs
            )
        }

        fun createSystemLaunchAction(commandId: UUID, executablePath: String, arguments: List<String> = emptyList()): Action {
            return create(
                commandId = commandId,
                actionType = ActionType.SYSTEM_LAUNCH,
                parameters = mapOf(
                    "executable_path" to executablePath,
                    "arguments" to arguments
                )
            )
        }

        fun createVolumeAction(commandId: UUID, volumeLevel: Int, adjustType: String = "set"): Action {
            return create(
                commandId = commandId,
                actionType = ActionType.SYSTEM_VOLUME,
                parameters = mapOf(
                    "volume_level" to volumeLevel,
                    "adjust_type" to adjustType // "set", "increase", "decrease"
                )
            )
        }

        fun createFileSearchAction(commandId: UUID, searchQuery: String, searchPath: String? = null): Action {
            return create(
                commandId = commandId,
                actionType = ActionType.SYSTEM_FILE_FIND,
                parameters = mapOf(
                    "search_query" to searchQuery,
                    "search_path" to (searchPath ?: "")
                )
            )
        }

        fun createBrowserNavigateAction(commandId: UUID, url: String): Action {
            return create(
                commandId = commandId,
                actionType = ActionType.BROWSER_NAVIGATE,
                parameters = mapOf("url" to url)
            )
        }

        fun createBrowserSearchAction(commandId: UUID, searchQuery: String, searchEngine: String = "google"): Action {
            return create(
                commandId = commandId,
                actionType = ActionType.BROWSER_SEARCH,
                parameters = mapOf(
                    "search_query" to searchQuery,
                    "search_engine" to searchEngine
                )
            )
        }
    }

    fun toEntity(): com.pccontrol.voice.data.database.ActionEntity {
        return com.pccontrol.voice.data.database.ActionEntity(
            actionId = actionId.toString(),
            commandId = commandId.toString(),
            actionType = actionType.value,
            parameters = org.json.JSONObject(parameters).toString(),
            status = status.value,
            result = result?.let { org.json.JSONObject(it).toString() },
            errorMessage = errorMessage,
            executionTimeMs = executionTimeMs,
            startedAt = startedAt,
            completedAt = completedAt,
            priority = priority,
            requiresConfirmation = requiresConfirmation,
            timeoutMs = timeoutMs,
            retryCount = retryCount,
            maxRetries = maxRetries,
            createdAt = createdAt,
            updatedAt = updatedAt
        )
    }

    fun withStatus(newStatus: ActionStatus): Action {
        val now = System.currentTimeMillis()
        return copy(
            status = newStatus,
            startedAt = if (newStatus == ActionStatus.EXECUTING && startedAt == null) now else startedAt,
            completedAt = if (newStatus in listOf(ActionStatus.COMPLETED, ActionStatus.FAILED) && completedAt == null) now else completedAt,
            updatedAt = now
        )
    }

    fun withResult(success: Boolean, resultData: Map<String, Any>? = null, error: String? = null): Action {
        val now = System.currentTimeMillis()
        val finalStatus = if (success) ActionStatus.COMPLETED else ActionStatus.FAILED

        return copy(
            status = finalStatus,
            result = resultData,
            errorMessage = error,
            completedAt = if (completedAt == null) now else completedAt,
            updatedAt = now
        )
    }

    fun canRetry(): Boolean {
        return retryCount < maxRetries && status == ActionStatus.FAILED
    }

    fun incrementRetryCount(): Action {
        return copy(
            retryCount = retryCount + 1,
            status = ActionStatus.PENDING,
            errorMessage = null,
            updatedAt = System.currentTimeMillis()
        )
    }

    fun isTimedOut(): Boolean {
        val elapsed = startedAt?.let { System.currentTimeMillis() - it } ?: return false
        return elapsed > timeoutMs
    }

    fun isValid(): Boolean {
        return parameters.isNotEmpty() && actionType != ActionType.UNKNOWN
    }
}

/**
 * Enum representing action types.
 */
enum class ActionType(val value: String) {
    SYSTEM_LAUNCH("system_launch"),
    SYSTEM_VOLUME("system_volume"),
    SYSTEM_FILE_FIND("system_file_find"),
    SYSTEM_INFO("system_info"),
    SYSTEM_FILE_DELETE("system_file_delete"),
    BROWSER_NAVIGATE("browser_navigate"),
    BROWSER_SEARCH("browser_search"),
    BROWSER_EXTRACT("browser_extract"),
    BROWSER_INTERACT("browser_interact"),
    UNKNOWN("unknown");

    companion object {
        fun fromString(value: String): ActionType {
            return values().find { it.value == value } ?: UNKNOWN
        }

        fun getSystemActions(): List<ActionType> {
            return listOf(
                SYSTEM_LAUNCH,
                SYSTEM_VOLUME,
                SYSTEM_FILE_FIND,
                SYSTEM_INFO,
                SYSTEM_FILE_DELETE
            )
        }

        fun getBrowserActions(): List<ActionType> {
            return listOf(
                BROWSER_NAVIGATE,
                BROWSER_SEARCH,
                BROWSER_EXTRACT,
                BROWSER_INTERACT
            )
        }
    }

    override fun toString(): String = value

    fun isSystemAction(): Boolean = getSystemActions().contains(this)
    fun isBrowserAction(): Boolean = getBrowserActions().contains(this)
}

/**
 * Enum representing action status.
 */
enum class ActionStatus(val value: String) {
    PENDING("pending"),
    EXECUTING("executing"),
    COMPLETED("completed"),
    FAILED("failed"),
    REQUIRES_CONFIRMATION("requires_confirmation"),
    CANCELLED("cancelled"),
    TIMED_OUT("timed_out");

    companion object {
        fun fromString(value: String): ActionStatus {
            return values().find { it.value == value } ?: PENDING
        }
    }

    override fun toString(): String = value

    fun isFinalStatus(): Boolean {
        return this in listOf(COMPLETED, FAILED, CANCELLED, TIMED_OUT)
    }

    fun isActive(): Boolean {
        return this in listOf(PENDING, EXECUTING, REQUIRES_CONFIRMATION)
    }
}

// Extension function to convert JSONObject to Map
/**
 * Converts a JSONObject to a Map<String, Any>.
 * Recursively converts nested JSONObjects to Maps.
 */
private fun org.json.JSONObject.toMap(): Map<String, Any> {
    val map = mutableMapOf<String, Any>()
    val keys = this.keys()
    while (keys.hasNext()) {
        val key = keys.next()
        val value = this.get(key)
        map[key] = value
    }
    return map
}