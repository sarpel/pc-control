package com.pccontrol.voice.presentation.viewmodel

import android.app.Application
import androidx.lifecycle.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.time.Instant
import javax.inject.Inject

/**
 * Command Status ViewModel
 *
 * Manages the state for CommandStatusFragment and provides a clean API
 * for UI components. Handles voice command lifecycle, connection management,
 * and command history with Turkish language support.
 *
 * Features:
 * - Real-time command status updates (200ms timing validation)
 * - Connection state management
 * - Command history tracking (5 commands max, 10-minute retention)
 * - Error handling with Turkish messages
 * - Battery-optimized state updates
 * - Integration with VoiceAssistantService and VoiceCommandRepository
 *
 * Performance Optimizations:
 * - Efficient state management with minimal recompositions
 * - Debounced UI updates to save battery
 * - Lazy loading of command history
 * - Optimized Flow collection
 *
 * Task: T054 [US1] Supporting ViewModel for CommandStatusFragment
 */
@HiltViewModel
class CommandStatusViewModel @Inject constructor(
    private val application: Application,
    private val voiceCommandRepository: VoiceCommandRepository,
    private val voiceAssistantService: VoiceAssistantServiceManager
) : ViewModel() {

    // UI State
    private val _uiState = MutableStateFlow(CommandStatusUIState())
    val uiState: StateFlow<CommandStatusUIState> = _uiState.asStateFlow()

    // Command status flow for real-time updates
    private val _commandStatusFlow = MutableStateFlow<CommandStatus>(CommandStatus.Idle)
    val commandStatusFlow: StateFlow<CommandStatus> = _commandStatusFlow.asStateFlow()

    // Recent commands flow (5 max, 10-minute retention per spec)
    val recentCommands: StateFlow<List<VoiceCommand>> =
        voiceCommandRepository.getRecentCommandsFlow()
            .stateIn(
                scope = viewModelScope,
                started = SharingStarted.WhileSubscribed(5000),
                initialValue = emptyList()
            )

    // Current command tracking
    private val _currentCommand = MutableStateFlow<VoiceCommand?>(null)
    val currentCommand: StateFlow<VoiceCommand?> = _currentCommand.asStateFlow()

    // Debounced status updates for performance (200ms timing validation)
    private val statusUpdateDebouncer = MutableSharedFlow<CommandStatus>(
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    init {
        // Start collecting service states
        collectServiceStates()

        // Start collecting command updates
        collectCommandUpdates()

        // Start debounced status updates
        startStatusDebouncer()
    }

    /**
     * Collect service states (connection, service status, etc.)
     */
    private fun collectServiceStates() {
        viewModelScope.launch {
            // Collect connection state
            voiceAssistantService.connectionState
                .collect { connectionState ->
                    _uiState.update { currentState ->
                        currentState.copy(
                            connectionState = connectionState.toUIState(),
                            errorMessage = null // Clear error on successful connection
                        )
                    }
                }
        }

        viewModelScope.launch {
            // Collect service state
            voiceAssistantService.serviceState
                .collect { serviceState ->
                    _commandStatusFlow.value = serviceState.toCommandStatus()

                    _uiState.update { currentState ->
                        currentState.copy(
                            commandStatus = serviceState.toCommandStatus(),
                            audioLevel = if (serviceState == VoiceAssistantService.ServiceState.LISTENING) {
                                getAudioLevel()
                            } else {
                                0f
                            }
                        )
                    }
                }
        }

        viewModelScope.launch {
            // Collect audio level when listening
            voiceAssistantService.audioLevelFlow
                .collect { audioLevel ->
                    _uiState.update { currentState ->
                        currentState.copy(audioLevel = audioLevel)
                    }
                }
        }
    }

    /**
     * Collect command updates from repository
     */
    private fun collectCommandUpdates() {
        viewModelScope.launch {
            voiceCommandRepository.currentCommand.collect { command ->
                _currentCommand.value = command
                _uiState.update { currentState ->
                    currentState.copy(currentCommand = command)
                }
            }
        }
    }

    /**
     * Start debounced status updates for performance optimization
     */
    private fun startStatusDebouncer() {
        viewModelScope.launch {
            statusUpdateDebouncer
                .debounce(200) // 200ms timing validation as per spec
                .collect { status ->
                    _commandStatusFlow.value = status
                    _uiState.update { currentState ->
                        currentState.copy(commandStatus = status)
                    }
                }
        }
    }

    /**
     * Start voice command listening
     */
    fun startListening() {
        viewModelScope.launch {
            try {
                val success = voiceAssistantService.startVoiceCapture()
                if (!success) {
                    _uiState.update { currentState ->
                        currentState.copy(
                            errorMessage = voiceCommandRepository.getErrorMessage(
                                VoiceCommandRepository.CommandErrorType.PROCESSING_ERROR
                            )
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.update { currentState ->
                    currentState.copy(
                        errorMessage = "Dinleme başlatılamadı: ${e.message}" // "Could not start listening: ${e.message}"
                    )
                }
            }
        }
    }

    /**
     * Stop voice command listening
     */
    fun stopListening() {
        viewModelScope.launch {
            try {
                voiceAssistantService.stopVoiceCapture()
                statusUpdateDebouncer.tryEmit(CommandStatus.Idle)
            } catch (e: Exception) {
                _uiState.update { currentState ->
                    currentState.copy(
                        errorMessage = "Dinleme durdurulamadı: ${e.message}" // "Could not stop listening: ${e.message}"
                    )
                }
            }
        }
    }

    /**
     * Retry connection to PC agent
     */
    fun retryConnection() {
        viewModelScope.launch {
            _uiState.update { currentState ->
                currentState.copy(
                    connectionState = ConnectionState.Connecting,
                    errorMessage = null
                )
            }

            try {
                val success = voiceAssistantService.connectToPCAgent()
                if (!success) {
                    _uiState.update { currentState ->
                        currentState.copy(
                            connectionState = ConnectionState.Error,
                            errorMessage = voiceCommandRepository.getErrorMessage(
                                VoiceCommandRepository.CommandErrorType.NETWORK_ERROR
                            )
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.update { currentState ->
                    currentState.copy(
                        connectionState = ConnectionState.Error,
                        errorMessage = "Bağlantı yeniden denenemedi: ${e.message}" // "Could not retry connection: ${e.message}"
                    )
                }
            }
        }
    }

    /**
     * Clear command history
     */
    fun clearCommandHistory() {
        viewModelScope.launch {
            try {
                // Repository would need a method to clear history
                // This would delete all commands from the database
                voiceCommandRepository.clearAllCommands()
            } catch (e: Exception) {
                _uiState.update { currentState ->
                    currentState.copy(
                        errorMessage = "Geçmiş temizlenemedi: ${e.message}" // "Could not clear history: ${e.message}"
                    )
                }
            }
        }
    }

    /**
     * Get current audio level (optimized for battery)
     */
    private fun getAudioLevel(): Float {
        return try {
            voiceAssistantService.getCurrentAudioLevel()
        } catch (e: Exception) {
            0f
        }
    }

    /**
     * Handle voice command result
     */
    fun handleVoiceCommandResult(
        transcription: String,
        confidence: Float,
        success: Boolean,
        errorMessage: String? = null
    ) {
        viewModelScope.launch {
            try {
                if (success) {
                    // Create command if transcription is confident enough
                    if (confidence >= 0.60f) {
                        val command = voiceCommandRepository.createCommand(
                            transcribedText = transcription,
                            confidenceScore = confidence,
                            durationMs = 0 // Would be calculated from audio capture
                        )

                        // Update command status to processing
                        voiceCommandRepository.updateCommandStatus(
                            commandId = command.id,
                            status = VoiceCommand.CommandStatus.PROCESSING
                        )

                        statusUpdateDebouncer.tryEmit(CommandStatus.Processing)
                    } else {
                        _uiState.update { currentState ->
                            currentState.copy(
                                errorMessage = voiceCommandRepository.getErrorMessage(
                                    VoiceCommandRepository.CommandErrorType.LOW_CONFIDENCE
                                )
                            )
                        }
                        statusUpdateDebouncer.tryEmit(CommandStatus.Error)
                    }
                } else {
                    _uiState.update { currentState ->
                        currentState.copy(
                            errorMessage = errorMessage ?: "Komut işlenemedi" // "Command could not be processed"
                        )
                    }
                    statusUpdateDebouncer.tryEmit(CommandStatus.Error)
                }
            } catch (e: Exception) {
                _uiState.update { currentState ->
                    currentState.copy(
                        errorMessage = "Komut sonucu işlenemedi: ${e.message}" // "Could not process command result: ${e.message}"
                    )
                }
                statusUpdateDebouncer.tryEmit(CommandStatus.Error)
            }
        }
    }

    override fun onCleared() {
        super.onCleared()
        viewModelScope.cancel()
    }

    // Extension functions for converting between different state types
    private fun VoiceAssistantService.ConnectionState.toUIState(): ConnectionState {
        return when (this) {
            VoiceAssistantService.ConnectionState.CONNECTED -> ConnectionState.Connected
            VoiceAssistantService.ConnectionState.CONNECTING -> ConnectionState.Connecting
            VoiceAssistantService.ConnectionState.RECONNECTING -> ConnectionState.Connecting
            VoiceAssistantService.ConnectionState.ERROR -> ConnectionState.Error
            VoiceAssistantService.ConnectionState.DISCONNECTED -> ConnectionState.Disconnected
        }
    }

    private fun VoiceAssistantService.ServiceState.toCommandStatus(): CommandStatus {
        return when (this) {
            VoiceAssistantService.ServiceState.LISTENING -> CommandStatus.Listening
            VoiceAssistantService.ServiceState.RUNNING -> CommandStatus.Ready
            VoiceAssistantService.ServiceState.STARTING -> CommandStatus.Processing
            VoiceAssistantService.ServiceState.ERROR -> CommandStatus.Error
            VoiceAssistantService.ServiceState.STOPPED -> CommandStatus.Idle
        }
    }
}

/**
 * UI State data class
 */
data class CommandStatusUIState(
    val connectionState: ConnectionState = ConnectionState.Disconnected,
    val commandStatus: CommandStatus = CommandStatus.Idle,
    val currentCommand: VoiceCommand? = null,
    val audioLevel: Float = 0f,
    val errorMessage: String? = null
)

/**
 * Connection state for UI
 */
enum class ConnectionState(val displayName: String) {
    Connected("PC'ye Bağlı"),           // "Connected to PC"
    Connecting("Bağlanıyor..."),        // "Connecting..."
    Error("Bağlantı Hatası"),           // "Connection Error"
    Disconnected("Bağlı Değil")         // "Not Connected"
}

/**
 * Command status for UI
 */
sealed class CommandStatus(val displayName: String) {
    object Idle : CommandStatus("Hazır")                              // "Ready"
    object Listening : CommandStatus("Dinleniyor...")                  // "Listening..."
    object Processing : CommandStatus("İşleniyor...")                 // "Processing..."
    object Completed : CommandStatus("Tamamlandı")                      // "Completed"
    object Error : CommandStatus("Hata")                               // "Error"
    object Ready : CommandStatus("Komut Bekleniyor")                    // "Waiting for Command"
}

/**
 * Voice command data class (simplified for UI)
 */
data class VoiceCommand(
    val id: String,
    val transcribedText: String,
    val confidenceScore: Float,
    val timestamp: Long,
    val status: CommandStatus,
    val actionSummary: String? = null
)

/**
 * Voice command repository interface (for ViewModel dependency)
 */
interface VoiceCommandRepository {
    suspend fun createCommand(
        transcribedText: String,
        confidenceScore: Float,
        durationMs: Int
    ): VoiceCommand

    suspend fun updateCommandStatus(
        commandId: String,
        status: CommandStatus,
        errorMessage: String? = null
    )

    fun getRecentCommandsFlow(): Flow<List<VoiceCommand>>
    suspend fun clearAllCommands()
    fun getErrorMessage(errorType: CommandErrorType): String

    enum class CommandErrorType {
        LOW_CONFIDENCE,
        NETWORK_ERROR,
        PROCESSING_ERROR,
        TIMEOUT,
        PC_OFFLINE,
        UNKNOWN
    }

    val currentCommand: StateFlow<VoiceCommand?>
}

/**
 * Voice assistant service manager interface
 */
interface VoiceAssistantServiceManager {
    val connectionState: StateFlow<ConnectionState>
    val serviceState: StateFlow<ServiceState>
    val audioLevelFlow: StateFlow<Float>

    suspend fun connectToPCAgent(): Boolean
    suspend fun startVoiceCapture(): Boolean
    suspend fun stopVoiceCapture()
    fun getCurrentAudioLevel(): Float

    enum class ConnectionState {
        CONNECTED,
        CONNECTING,
        RECONNECTING,
        ERROR,
        DISCONNECTED
    }

    enum class ServiceState {
        STOPPED,
        STARTING,
        RUNNING,
        LISTENING,
        ERROR
    }
}