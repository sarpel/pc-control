package com.pccontrol.voice.presentation.viewmodel

import com.pccontrol.voice.common.ConnectionState
import com.pccontrol.voice.common.ServiceState
import kotlinx.coroutines.flow.StateFlow
interface VoiceAssistantServiceManager {
    val connectionState: StateFlow<ConnectionState>
    val serviceState: StateFlow<ServiceState>
    val audioLevelFlow: StateFlow<Float>

    suspend fun connectToPCAgent(): Result<Unit>
    suspend fun startVoiceCapture(): Result<Unit>
    suspend fun stopVoiceCapture()
}
