package com.pccontrol.voice.domain.services

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manager for interacting with VoiceAssistantService.
 * Acts as a bridge between UI/ViewModels and the Android Service.
 */
@Singleton
class VoiceAssistantServiceManager @Inject constructor() {

    // Mirroring VoiceAssistantService states
    private val _connectionState = MutableStateFlow(VoiceAssistantService.ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<VoiceAssistantService.ConnectionState> = _connectionState.asStateFlow()

    private val _serviceState = MutableStateFlow(VoiceAssistantService.ServiceState.STOPPED)
    val serviceState: StateFlow<VoiceAssistantService.ServiceState> = _serviceState.asStateFlow()

    private val _audioLevelFlow = MutableStateFlow(0f)
    val audioLevelFlow: StateFlow<Float> = _audioLevelFlow.asStateFlow()

    // Stub methods
    suspend fun startVoiceCapture(): Boolean {
        // TODO: Bind to service and call method
        _serviceState.value = VoiceAssistantService.ServiceState.LISTENING
        return true
    }

    fun stopVoiceCapture() {
        // TODO: Bind to service and call method
        _serviceState.value = VoiceAssistantService.ServiceState.RUNNING
    }

    suspend fun connectToPCAgent(): Boolean {
        // TODO: Bind to service and call method
        _connectionState.value = VoiceAssistantService.ConnectionState.CONNECTING
        // Simulate connection
        _connectionState.value = VoiceAssistantService.ConnectionState.CONNECTED
        return true
    }

    fun getCurrentAudioLevel(): Float {
        return _audioLevelFlow.value
    }
    
    // Method for Service to update state (if we go that route)
    fun updateConnectionState(state: VoiceAssistantService.ConnectionState) {
        _connectionState.value = state
    }
    
    fun updateServiceState(state: VoiceAssistantService.ServiceState) {
        _serviceState.value = state
    }
    
    fun updateAudioLevel(level: Float) {
        _audioLevelFlow.value = level
    }
}
