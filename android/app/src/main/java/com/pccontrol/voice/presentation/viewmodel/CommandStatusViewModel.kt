package com.pccontrol.voice.presentation.viewmodel

import android.app.Application
import androidx.lifecycle.*
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import javax.inject.Inject
import com.pccontrol.voice.data.repository.VoiceCommandRepository
import com.pccontrol.voice.data.repository.CommandStatus
import com.pccontrol.voice.data.repository.VoiceCommand
import com.pccontrol.voice.domain.services.VoiceAssistantService
import com.pccontrol.voice.domain.services.VoiceAssistantServiceManager

/**
 * Command Status ViewModel
 *
 * Manages the state for CommandStatusFragment and provides a clean API
 * for UI components. Handles voice command lifecycle, connection management,
 * and command history with Turkish language support.
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
    private val _commandStatusFlow = MutableStateFlow<CommandStatus?>(null)
    val commandStatusFlow: StateFlow<CommandStatus?> = _commandStatusFlow.asStateFlow()

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
    private val statusUpdateDebouncer = MutableSharedFlow<CommandStatus?>(
        extraBufferCapacity = 1,
        onBufferOverflow = kotlinx.coroutines.channels.BufferOverflow.DROP_OLDEST
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
                    val status = serviceState.toCommandStatus()
                    _commandStatusFlow.value = status

                    _uiState.update { currentState ->
                        currentState.copy(
                            commandStatus = status,
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
                statusUpdateDebouncer.tryEmit(null) // Idle
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

    private fun VoiceAssistantService.ServiceState.toCommandStatus(): CommandStatus? {
        return when (this) {
            VoiceAssistantService.ServiceState.LISTENING -> CommandStatus.LISTENING
            VoiceAssistantService.ServiceState.RUNNING -> CommandStatus.PROCESSING
            VoiceAssistantService.ServiceState.STARTING -> CommandStatus.PROCESSING
            VoiceAssistantService.ServiceState.ERROR -> CommandStatus.ERROR
            VoiceAssistantService.ServiceState.STOPPED -> null // Idle
        }
    }
}

/**
 * UI State data class
 */
data class CommandStatusUIState(
    val connectionState: ConnectionState = ConnectionState.Disconnected,
    val commandStatus: CommandStatus? = null, // null means Idle
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
