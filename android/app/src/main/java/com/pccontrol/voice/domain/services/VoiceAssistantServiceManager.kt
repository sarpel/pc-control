package com.pccontrol.voice.domain.services

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.core.content.ContextCompat
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val boundService = MutableStateFlow<VoiceAssistantService?>(null)
    private var observationJob: Job? = null
    private var isBound = false

    // Mirroring VoiceAssistantService states
    private val _connectionState = MutableStateFlow(VoiceAssistantService.ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<VoiceAssistantService.ConnectionState> = _connectionState.asStateFlow()

    private val _serviceState = MutableStateFlow(VoiceAssistantService.ServiceState.STOPPED)
    val serviceState: StateFlow<VoiceAssistantService.ServiceState> = _serviceState.asStateFlow()

    private val _audioLevelFlow = MutableStateFlow(0f)
    val audioLevelFlow: StateFlow<Float> = _audioLevelFlow.asStateFlow()

    private val serviceConnection = object : ServiceConnection {
        override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
            val binder = service as? VoiceAssistantService.LocalBinder ?: return
            val voiceService = binder.getService()
            boundService.value = voiceService
            startObservingService(voiceService)
        }

        override fun onServiceDisconnected(name: ComponentName?) {
            stopObservingService()
            boundService.value = null
            _connectionState.value = VoiceAssistantService.ConnectionState.DISCONNECTED
            _serviceState.value = VoiceAssistantService.ServiceState.STOPPED
            _audioLevelFlow.value = 0f
            isBound = false
        }
    }

    /**
     * Start listening for voice commands via the service.
     */
    suspend fun startVoiceCapture(): Boolean {
        val service = awaitService()
        return withContext(Dispatchers.Main) {
            service.startListeningFromManager()
        }
    }

    /**
     * Stop voice capture session.
     */
    fun stopVoiceCapture() {
        boundService.value?.stopListeningFromManager()
    }

    /**
     * Ensure a secure connection with the PC agent via the service.
     */
    suspend fun connectToPCAgent(): Boolean {
        val service = awaitService()
        return service.connectFromManager()
    }

    fun getCurrentAudioLevel(): Float = _audioLevelFlow.value

    private suspend fun awaitService(): VoiceAssistantService {
        ensureServiceConnection()
        return boundService.filterNotNull().first()
    }

    private fun ensureServiceConnection() {
        val intent = Intent(context, VoiceAssistantService::class.java)
        ContextCompat.startForegroundService(context, intent)
        if (!isBound) {
            isBound = context.bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE)
        }
    }

    private fun startObservingService(service: VoiceAssistantService) {
        stopObservingService()
        observationJob = scope.launch {
            launch { service.connectionState.collect { _connectionState.value = it } }
            launch { service.serviceState.collect { _serviceState.value = it } }
            launch { service.audioLevel.collect { _audioLevelFlow.value = it } }
        }
    }

    private fun stopObservingService() {
        observationJob?.cancel()
        observationJob = null
    }

    fun shutdown() {
        stopObservingService()
        if (isBound) {
            context.unbindService(serviceConnection)
            isBound = false
        }
        scope.cancel()
    }
}
