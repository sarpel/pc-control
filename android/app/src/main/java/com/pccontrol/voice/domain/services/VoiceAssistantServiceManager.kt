package com.pccontrol.voice.domain.services

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import dagger.hilt.android.qualifiers.ApplicationContext
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
class VoiceAssistantServiceManager @Inject constructor(
    @ApplicationContext private val context: Context
) {

    private var voiceService: VoiceAssistantService? = null
    private var isBound = false

    private val connection = object : ServiceConnection {
        override fun onServiceConnected(className: ComponentName, service: IBinder) {
            val binder = service as VoiceAssistantService.LocalBinder
            voiceService = binder.getService()
            isBound = true
            // Sync initial state if needed
        }

        override fun onServiceDisconnected(arg0: ComponentName) {
            isBound = false
            voiceService = null
        }
    }

    init {
        bindService()
    }

    private fun bindService() {
        Intent(context, VoiceAssistantService::class.java).also { intent ->
            context.bindService(intent, connection, Context.BIND_AUTO_CREATE)
        }
    }

    // Mirroring VoiceAssistantService states
    private val _connectionState = MutableStateFlow(VoiceAssistantService.ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<VoiceAssistantService.ConnectionState> = _connectionState.asStateFlow()

    private val _serviceState = MutableStateFlow(VoiceAssistantService.ServiceState.STOPPED)
    val serviceState: StateFlow<VoiceAssistantService.ServiceState> = _serviceState.asStateFlow()

    private val _audioLevelFlow = MutableStateFlow(0f)
    val audioLevelFlow: StateFlow<Float> = _audioLevelFlow.asStateFlow()

    // Methods
    suspend fun startVoiceCapture(): Boolean {
        if (isBound && voiceService != null) {
            voiceService?.startCapture()
            return true
        }
        return false
    }

    fun stopVoiceCapture() {
        if (isBound && voiceService != null) {
            voiceService?.stopCapture()
        }
    }

    suspend fun connectToPCAgent(): Boolean {
        if (isBound && voiceService != null) {
            voiceService?.connect()
            return true
        }
        return false
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
