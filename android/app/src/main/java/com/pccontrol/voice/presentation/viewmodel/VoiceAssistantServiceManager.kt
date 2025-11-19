package com.pccontrol.voice.presentation.viewmodel

import kotlinx.coroutines.flow.StateFlow

/**
 * Voice Assistant Service Manager Interface
 *
 * Provides abstraction layer for VoiceAssistantService integration with ViewModels.
 * This allows for better testability and separation of concerns.
 */
interface VoiceAssistantServiceManager {
    val connectionState: StateFlow<VoiceAssistantService.ConnectionState>
    val serviceState: StateFlow<VoiceAssistantService.ServiceState>
    val audioLevelFlow: StateFlow<Float>

    suspend fun connectToPCAgent(): Boolean
    suspend fun startVoiceCapture(): Boolean
    suspend fun stopVoiceCapture()
    fun getCurrentAudioLevel(): Float
}

/**
 * VoiceAssistantService state enums
 * (These would normally be in VoiceAssistantService.kt but are here for reference)
 */
object VoiceAssistantService {
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
