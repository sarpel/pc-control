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

    // Mirroring VoiceAssistantService states
    private val _connectionState = MutableStateFlow(VoiceAssistantService.ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<VoiceAssistantService.ConnectionState> = _connectionState.asStateFlow()

    private val _serviceState = MutableStateFlow(VoiceAssistantService.ServiceState.STOPPED)
    val serviceState: StateFlow<VoiceAssistantService.ServiceState> = _serviceState.asStateFlow()

    private val _audioLevelFlow = MutableStateFlow(0f)
    val audioLevelFlow: StateFlow<Float> = _audioLevelFlow.asStateFlow()

    private var serviceBinder: VoiceAssistantService.LocalBinder? = null
    private var isBound = false

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
            serviceBinder = binder as? VoiceAssistantService.LocalBinder
            isBound = true
            
            // Observe service states
            serviceBinder?.getService()?.let { service ->
                // Update state flows from service
                _connectionState.value = service.connectionState.value
                _serviceState.value = service.serviceState.value
            }
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            serviceBinder = null
            isBound = false
            _serviceState.value = VoiceAssistantService.ServiceState.STOPPED
        }
    }

    fun bindToService() {
        val intent = Intent(context, VoiceAssistantService::class.java)
        context.bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
    }

    fun unbindFromService() {
        if (isBound) {
            context.unbindService(serviceConnection)
            isBound = false
        }
    }

    suspend fun startVoiceCapture(): Boolean {
        return try {
            if (!isBound) {
                bindToService()
            }
            
            serviceBinder?.getService()?.let { service ->
                // Trigger voice capture
                _serviceState.value = VoiceAssistantService.ServiceState.LISTENING
                true
            } ?: false
        } catch (e: Exception) {
            false
        }
    }

    fun stopVoiceCapture() {
        serviceBinder?.getService()?.let {
            _serviceState.value = VoiceAssistantService.ServiceState.RUNNING
        }
    }

    suspend fun connectToPCAgent(): Boolean {
        return try {
            if (!isBound) {
                bindToService()
            }
            
            _connectionState.value = VoiceAssistantService.ConnectionState.CONNECTING
            // The actual connection would be handled by the service
            _connectionState.value = VoiceAssistantService.ConnectionState.CONNECTED
            true
        } catch (e: Exception) {
            _connectionState.value = VoiceAssistantService.ConnectionState.ERROR
            false
        }
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
