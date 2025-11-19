package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.audio.AudioProcessingService
import com.pccontrol.voice.data.models.VoiceCommand
import com.pccontrol.voice.services.WebSocketManager
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for the voice command screen.
 */
@HiltViewModel
class VoiceCommandViewModel @Inject constructor(
    private val audioProcessingService: AudioProcessingService,
    private val webSocketManager: WebSocketManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(VoiceCommandUiState())
    val uiState: StateFlow<VoiceCommandUiState> = _uiState.asStateFlow()

    init {
        initialize()
    }

    private fun initialize() {
        viewModelScope.launch {
            audioProcessingService.initialize()
            webSocketManager.connectionStatus.collect { status ->
                _uiState.value = _uiState.value.copy(
                    isConnected = status.isConnected,
                    connectedPcName = if (status.isConnected) status.pcName else null
                )
            }
        }
    }

    fun startListening() {
        viewModelScope.launch {
            try {
                _uiState.value = _uiState.value.copy(
                    isListening = true,
                    statusMessage = "Dinleniyor...",
                    isError = false
                )

                val result: Result<AudioProcessingService.VoiceCommandResult> = audioProcessingService.startVoiceCommandProcessing()

                result.onSuccess { voiceCommand ->
                    _uiState.value = _uiState.value.copy(statusMessage = voiceCommand.transcription)
                    sendCommandToPC(voiceCommand)
                }.onFailure { error ->
                    _uiState.value = _uiState.value.copy(statusMessage = "Error: ${error.message}", isError = true)
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Hata: ${e.message}",
                    isError = true,
                    isListening = false
                )
            }
        }
    }

    fun stopListening() {
        viewModelScope.launch {
            try {
                audioProcessingService.cancelProcessing()
                _uiState.value = _uiState.value.copy(
                    isListening = false,
                    statusMessage = "Durduruldu",
                    currentTranscription = ""
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Hata: ${e.message}",
                    isError = true
                )
            }
        }
    }

    private fun sendCommandToPC(voiceCommand: AudioProcessingService.VoiceCommandResult) {
        viewModelScope.launch {
            val command = VoiceCommand(
                transcription = voiceCommand.transcription,
                timestamp = System.currentTimeMillis()
            )
            val success = webSocketManager.sendCommand(command)

            val newCommand = RecentCommand(
                transcription = voiceCommand.transcription,
                success = success,
                timestamp = System.currentTimeMillis()
            )
            _uiState.value = _uiState.value.copy(
                statusMessage = if (success) "Command sent" else "Failed to send command",
                isError = !success,
                recentCommands = listOf(newCommand) + _uiState.value.recentCommands.take(4)
            )
        }
    }
}

/**
 * UI state for the voice command screen.
 */
data class VoiceCommandUiState(
    val isConnected: Boolean = false,
    val connectedPcName: String? = null,
    val isListening: Boolean = false,
    val voiceLevel: Float = 0f,
    val currentTranscription: String = "",
    val statusMessage: String = "",
    val isError: Boolean = false,
    val recentCommands: List<RecentCommand> = emptyList()
)