package com.pccontrol.voice.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pccontrol.voice.audio.AudioProcessingService
// import com.pccontrol.voice.services.WebSocketManager  // TODO: Fix Hilt injection
import com.pccontrol.voice.data.models.VoiceCommand
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
    private val audioProcessingService: AudioProcessingService
    // TODO: Fix WebSocketManager Hilt injection
    // private val webSocketManager: WebSocketManager
) : ViewModel() {

    private val _uiState = MutableStateFlow(VoiceCommandUiState())
    val uiState: StateFlow<VoiceCommandUiState> = _uiState.asStateFlow()

    fun initialize() {
        viewModelScope.launch {
            // Initialize services
            audioProcessingService.initialize()

            // Collect connection status
            // webSocketManager.isConnected.collect { isConnected ->
            //     _uiState.value = _uiState.value.copy(
            //         isConnected = isConnected,
            //         connectedPcName = if (isConnected) "PC" else null
            //     )
            // }

            // Collect audio processing results
            // This would be implemented based on the actual AudioProcessingService
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

                val result = audioProcessingService.startVoiceCommandProcessing()

                result.fold(
                    onSuccess = { voiceCommand ->
                        if (voiceCommand.isValid) {
                            _uiState.value = _uiState.value.copy(
                                statusMessage = voiceCommand.transcription.orEmpty(),
                                isError = false
                            )

                            // Send command to PC
                            sendCommandToPC(voiceCommand)

                            // Add to recent commands
                            val newCommand = RecentCommand(
                                transcription = voiceCommand.transcription.orEmpty(),
                                success = true,
                                timestamp = System.currentTimeMillis()
                            )
                            _uiState.value = _uiState.value.copy(
                                recentCommands = listOf(newCommand) + _uiState.value.recentCommands.take(4)
                            )
                        } else {
                            _uiState.value = _uiState.value.copy(
                                statusMessage = "Komut gönderilemedi",
                                isError = true
                            )
                        }
                    },
                    onFailure = { error ->
                        _uiState.value = _uiState.value.copy(
                            statusMessage = "İşlem hatası: ${error.message}",
                            isError = true
                        )
                    }
                )
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
            try {
                // TODO: Fix WebSocketManager Hilt injection
                /*
                val success = webSocketManager.sendVoiceCommand(
                    transcription = voiceCommand.transcription,
                    confidence = voiceCommand.confidence
                )
                */
                val success = true // Temporary placeholder

                if (success) {
                    _uiState.value = _uiState.value.copy(
                        statusMessage = "Komut gönderildi",
                        isError = false
                    )

                    // Add to recent commands
                    val newCommand = RecentCommand(
                        transcription = voiceCommand.transcription.orEmpty(),
                        success = true,
                        timestamp = System.currentTimeMillis()
                    )
                    _uiState.value = _uiState.value.copy(
                        recentCommands = listOf(newCommand) + _uiState.value.recentCommands.take(4)
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        statusMessage = "Komut gönderilemedi",
                        isError = true
                    )
                }
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    statusMessage = "Bağlantı hatası: ${e.message}",
                    isError = true
                )
            }
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

/**
 * Recent command for history display.
 */
data class RecentCommand(
    val transcription: String,
    val success: Boolean,
    val timestamp: Long
)