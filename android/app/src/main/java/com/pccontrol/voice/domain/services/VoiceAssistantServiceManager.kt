package com.pccontrol.voice.domain.services

import com.pccontrol.voice.common.ConnectionState
import com.pccontrol.voice.common.ServiceState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manager for interacting with VoiceAssistantService.
 * Acts as a bridge between UI/ViewModels and the Android Service.
 */
interface VoiceAssistantServiceManagerInterface {
    val connectionState: StateFlow<ConnectionState>
    val serviceState: StateFlow<ServiceState>
    val audioLevelFlow: StateFlow<Float>
    fun onServiceConnected(service: VoiceAssistantService)
    fun onServiceDisconnected()
    suspend fun startVoiceCapture(): Boolean
    fun stopVoiceCapture()
    suspend fun connectToPCAgent(): Boolean
    fun getCurrentAudioLevel(): Float
}

@Singleton
class VoiceAssistantServiceManager @Inject constructor() : VoiceAssistantServiceManagerInterface {

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    override val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _serviceState = MutableStateFlow(ServiceState.STOPPED)
    override val serviceState: StateFlow<ServiceState> = _serviceState.asStateFlow()

    private val _audioLevelFlow = MutableStateFlow(0f)
    override val audioLevelFlow: StateFlow<Float> = _audioLevelFlow.asStateFlow()

    private val _isServiceBound = MutableStateFlow(false)
    val isServiceBound: StateFlow<Boolean> = _isServiceBound.asStateFlow()

    private var voiceAssistantService: VoiceAssistantService? = null

    override fun onServiceConnected(service: VoiceAssistantService) {
        voiceAssistantService = service
        _isServiceBound.value = true
        // TODO: Collect states from the service
    }

    override fun onServiceDisconnected() {
        voiceAssistantService = null
        _isServiceBound.value = false
    }

    override suspend fun startVoiceCapture(): Boolean {
        return voiceAssistantService?.startVoiceCommandCapture() ?: false
    }

    override fun stopVoiceCapture() {
        voiceAssistantService?.stopVoiceCommandCapture()
    }

    override suspend fun connectToPCAgent(): Boolean {
        return voiceAssistantService?.connectToPCAgent() ?: false
    }

    override fun getCurrentAudioLevel(): Float {
        return voiceAssistantService?.getCurrentAudioLevel() ?: 0f
    }
}
