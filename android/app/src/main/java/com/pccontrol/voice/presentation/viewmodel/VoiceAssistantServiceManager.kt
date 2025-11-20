package com.pccontrol.voice.presentation.viewmodel

import com.pccontrol.voice.domain.services.VoiceAssistantService
import kotlinx.coroutines.flow.StateFlow

/**
 * Voice Assistant Service Manager Interface
 *
 * Provides abstraction layer for VoiceAssistantService integration with ViewModels.
 * This allows for better testability and separation of concerns.
 *
 * Note: Uses enums from domain.services.VoiceAssistantService to avoid duplication.
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
