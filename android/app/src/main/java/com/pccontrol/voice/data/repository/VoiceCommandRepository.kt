package com.pccontrol.voice.data.repository

import android.content.Context
import androidx.room.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.Instant
import java.util.*

/**
 * Voice Command Repository
 *
 * Manages voice command data and provides a clean API for voice command operations.
 * Handles local storage of command history and provides in-memory management
 * as specified in the data model (transient audio data, 5-command history limit).
 *
 * Features:
 * - Command history management (5 commands max, 10-minute retention)
 * - Command status tracking (listening, processing, executing, completed, error)
 * - Real-time command updates via Flow
 * - Turkish error messages and status descriptions
 * - Automatic cleanup of expired commands
 * - Performance optimization for battery efficiency
 *
 * Memory Management (per specification FR-016 & FR-017):
 * - Audio data: In-memory only, never persisted
 * - Command history: Maximum 5 entries with 10-minute retention
 * - Automatic garbage collection of expired entries
 *
 * Task: T052 [P] [US1] Create voice command repository in android/app/src/main/java/com/pccontrol/voice/data/repository/VoiceCommandRepository.kt
 */

/**
 * Voice Command Entity for Room database
 */
@Entity(tableName = "voice_commands")
data class VoiceCommandEntity(
    @PrimaryKey val id: String = UUID.randomUUID().toString(),
    val transcribedText: String,
    val confidenceScore: Float,
    val timestamp: Long = System.currentTimeMillis(),
    val language: String = "tr-TR",
    val durationMs: Int,
    val status: String, // "listening", "processing", "executing", "completed", "error"
    val errorMessage: String? = null,
    val actionType: String? = null, // "system", "browser", "query"
    val actionSummary: String? = null, // Brief description in Turkish
    val result: String? = null // Execution result or error details
)

/**
 * Data Access Object for VoiceCommandEntity
 */
@Dao
interface VoiceCommandDao {
    @Query("SELECT * FROM voice_commands ORDER BY timestamp DESC LIMIT 5")
    fun getRecentCommands(): Flow<List<VoiceCommandEntity>>

    @Query("SELECT * FROM voice_commands WHERE id = :id")
    suspend fun getCommandById(id: String): VoiceCommandEntity?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCommand(command: VoiceCommandEntity)

    @Update
    suspend fun updateCommand(command: VoiceCommandEntity)

    @Query("DELETE FROM voice_commands WHERE timestamp < :cutoffTime")
    suspend fun deleteExpiredCommands(cutoffTime: Long)

    @Query("SELECT COUNT(*) FROM voice_commands")
    suspend fun getCommandCount(): Int

    @Query("DELETE FROM voice_commands WHERE id IN (SELECT id FROM voice_commands ORDER BY timestamp DESC LIMIT 5 OFFSET 5)")
    suspend fun deleteOldestCommandsBeyondLimit()
}

/**
 * Room Database for voice commands
 */
@Database(
    entities = [VoiceCommandEntity::class],
    version = 1,
    exportSchema = false
)
abstract class VoiceCommandDatabase : RoomDatabase() {
    abstract fun voiceCommandDao(): VoiceCommandDao

    companion object {
        @Volatile
        private var INSTANCE: VoiceCommandDatabase? = null

        fun getDatabase(context: Context): VoiceCommandDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    VoiceCommandDatabase::class.java,
                    "voice_command_database"
                )
                .fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}

/**
 * Voice Command Domain Model
 */
data class VoiceCommand(
    val id: String = UUID.randomUUID().toString(),
    val transcribedText: String,
    val confidenceScore: Float,
    val timestamp: Instant = Instant.now(),
    val language: String = "tr-TR",
    val durationMs: Int,
    val status: CommandStatus = CommandStatus.LISTENING,
    val errorMessage: String? = null,
    val actionType: ActionType? = null,
    val actionSummary: String? = null,
    val result: String? = null
)

/**
 * Command Status enum
 */
enum class CommandStatus(val displayName: String) {
    LISTENING("Dinleniyor..."),      // "Listening..."
    PROCESSING("İşleniyor..."),     // "Processing..."
    EXECUTING("Çalıştırılıyor..."), // "Executing..."
    COMPLETED("Tamamlandı"),        // "Completed"
    ERROR("Hata")                   // "Error"
}

/**
 * Action Type enum
 */
enum class ActionType(val displayName: String) {
    SYSTEM("Sistem İşlemi"),    // "System Operation"
    BROWSER("Tarayıcı"),        // "Browser"
    QUERY("Sorgu")              // "Query"
}

/**
 * Voice Command Repository
 */
class VoiceCommandRepository private constructor(
    private val context: Context
) {
    private val database = VoiceCommandDatabase.getDatabase(context)
    private val dao = database.voiceCommandDao()
    private val repositoryScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // In-memory cache for real-time updates (performance optimization)
    private val _recentCommands = MutableStateFlow<List<VoiceCommand>>(emptyList())
    val recentCommands: StateFlow<List<VoiceCommand>> = _recentCommands

    // Current active command tracking
    private val _currentCommand = MutableStateFlow<VoiceCommand?>(null)
    val currentCommand: StateFlow<VoiceCommand?> = _currentCommand

    init {
        // Start listening for database changes and cleanup expired commands
        repositoryScope.launch {
            dao.getRecentCommands().collect { entities ->
                _recentCommands.value = entities.map { it.toDomainModel() }
            }
        }

        // Start periodic cleanup of expired commands
        startPeriodicCleanup()
    }

    /**
     * Create a new voice command
     */
    suspend fun createCommand(
        transcribedText: String,
        confidenceScore: Float,
        language: String = "tr-TR",
        durationMs: Int
    ): VoiceCommand {
        val command = VoiceCommand(
            transcribedText = transcribedText,
            confidenceScore = confidenceScore,
            language = language,
            durationMs = durationMs,
            status = if (confidenceScore >= 0.60f) CommandStatus.PROCESSING else CommandStatus.ERROR
        )

        // Save to database
        dao.insertCommand(command.toEntity())

        // Enforce 5-command limit
        enforceCommandLimit()

        // Update current command
        _currentCommand.value = command

        return command
    }

    /**
     * Update command status
     */
    suspend fun updateCommandStatus(
        commandId: String,
        status: CommandStatus,
        errorMessage: String? = null,
        actionType: ActionType? = null,
        actionSummary: String? = null,
        result: String? = null
    ) {
        val entity = dao.getCommandById(commandId) ?: return

        val updatedEntity = entity.copy(
            status = status.name.lowercase(),
            errorMessage = errorMessage,
            actionType = actionType?.name?.lowercase(),
            actionSummary = actionSummary,
            result = result
        )

        dao.updateCommand(updatedEntity)

        // Update current command if it matches
        _currentCommand.value?.let { current ->
            if (current.id == commandId) {
                _currentCommand.value = updatedEntity.toDomainModel()
            }
        }
    }

    /**
     * Get command by ID
     */
    suspend fun getCommand(commandId: String): VoiceCommand? {
        return dao.getCommandById(commandId)?.toDomainModel()
    }

    /**
     * Get all recent commands (max 5)
     */
    fun getRecentCommandsFlow(): Flow<List<VoiceCommand>> {
        return dao.getRecentCommands().map { entities ->
            entities.map { it.toDomainModel() }
        }
    }

    /**
     * Get Turkish error message for command processing errors
     */
    fun getErrorMessage(errorType: CommandErrorType): String {
        return when (errorType) {
            CommandErrorType.LOW_CONFIDENCE -> "Ses anlaşılamadı. Lütfen tekrar konuşun."
            CommandErrorType.NETWORK_ERROR -> "PC ile bağlantı hatası. İnternet bağlantınızı kontrol edin."
            CommandErrorType.PROCESSING_ERROR -> "Komut işlenirken hata oluştu. Lütfen tekrar deneyin."
            CommandErrorType.TIMEOUT -> "İşlem zaman aşımına uğradı. Lütfen tekrar deneyin."
            CommandErrorType.PC_OFFLINE -> "PC çevrimdışı. PC'nin uyandığından emin olun."
            CommandErrorType.UNKNOWN -> "Bilinmeyen hata. Lütfen daha sonra tekrar deneyin."
        }
    }

    /**
     * Generate action summary in Turkish based on command interpretation
     */
    fun generateActionSummary(command: String, actionType: ActionType): String {
        return when (actionType) {
            ActionType.SYSTEM -> {
                when {
                    command.contains("aç") || command.contains("çalıştır") -> "Uygulama açılıyor"
                    command.contains("kapat") || command.contains("kapat") -> "Uygulama kapatılıyor"
                    command.contains("ses") || command.contains("volume") -> "Ses ayarlanıyor"
                    command.contains("bilgi") || command.contains("sistem") -> "Sistem bilgileri gösteriliyor"
                    else -> "Sistem komutu çalıştırılıyor"
                }
            }
            ActionType.BROWSER -> {
                when {
                    command.contains("ara") -> "İnternette arama yapılıyor"
                    command.contains("site") || command.contains("aç") -> "Web sitesi açılıyor"
                    command.contains("hava") || command.contains("hava durumu") -> "Hava durumu gösteriliyor"
                    else -> "Tarayıcı komutu çalıştırılıyor"
                }
            }
            ActionType.QUERY -> {
                when {
                    command.contains("bul") || command.contains("ara") -> "Dosya aranıyor"
                    command.contains("göster") || command.contains("liste") -> "İçerik gösteriliyor"
                    else -> "Sorgu yapılıyor"
                }
            }
        }
    }

    /**
     * Enforce 5-command limit by removing oldest commands
     */
    private suspend fun enforceCommandLimit() {
        dao.deleteOldestCommandsBeyondLimit()
    }

    /**
     * Start periodic cleanup of expired commands (older than 10 minutes)
     */
    private fun startPeriodicCleanup() {
        repositoryScope.launch {
            while (isActive) {
                delay(60000) // Check every minute
                cleanupExpiredCommands()
            }
        }
    }

    /**
     * Remove commands older than 10 minutes
     */
    private suspend fun cleanupExpiredCommands() {
        val cutoffTime = System.currentTimeMillis() - (10 * 60 * 1000) // 10 minutes ago
        dao.deleteExpiredCommands(cutoffTime)
    }

    /**
     * Cleanup resources
     */
    fun cleanup() {
        repositoryScope.cancel()
    }

    /**
     * Extension functions for converting between domain models and entities
     */
    private fun VoiceCommand.toEntity(): VoiceCommandEntity {
        return VoiceCommandEntity(
            id = id,
            transcribedText = transcribedText,
            confidenceScore = confidenceScore,
            timestamp = timestamp.toEpochMilli(),
            language = language,
            durationMs = durationMs,
            status = status.name.lowercase(),
            errorMessage = errorMessage,
            actionType = actionType?.name?.lowercase(),
            actionSummary = actionSummary,
            result = result
        )
    }

    private fun VoiceCommandEntity.toDomainModel(): VoiceCommand {
        return VoiceCommand(
            id = id,
            transcribedText = transcribedText,
            confidenceScore = confidenceScore,
            timestamp = Instant.ofEpochMilli(timestamp),
            language = language,
            durationMs = durationMs,
            status = CommandStatus.valueOf(status.uppercase()),
            errorMessage = errorMessage,
            actionType = actionType?.let { ActionType.valueOf(it.uppercase()) },
            actionSummary = actionSummary,
            result = result
        )
    }

    /**
     * Command error types for Turkish error messages
     */
    enum class CommandErrorType {
        LOW_CONFIDENCE,
        NETWORK_ERROR,
        PROCESSING_ERROR,
        TIMEOUT,
        PC_OFFLINE,
        UNKNOWN
    }

    /**
     * Factory for creating VoiceCommandRepository instances
     */
    class Factory(private val context: Context) {
        fun create(): VoiceCommandRepository = VoiceCommandRepository(context)
    }
}