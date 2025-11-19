package com.pccontrol.voice.domain.services

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.pccontrol.voice.data.repository.VoiceCommandRepository
import com.pccontrol.voice.domain.VoiceCommandResult
import com.pccontrol.voice.R
import javax.inject.Inject

/**
 * Voice Assistant Foreground Service
 *
 * Background service that manages voice command processing and WebSocket communication
 * with the PC agent. Provides persistent voice assistant functionality with minimal
 * battery impact.
 *
 * Features:
 * - Foreground service with persistent notification
 * - WebSocket connection management with PC agent
 * - Audio capture and streaming integration
 * - Voice command lifecycle management
 * - Battery optimization (<5% battery/hour requirement)
 * - Turkish status messages and notifications
 * - Automatic reconnection and error handling
 * - Integration with AudioCaptureService and VoiceCommandRepository
 *
 * Battery Optimization Features:
 * - Sleep mode when idle
 * - Efficient audio buffering
 * - Automatic cleanup of resources
 * - Background task scheduling optimization
 *
 * Task: T053 [US1] Implement Android foreground service for background operation in android/app/src/main/java/com/pccontrol/voice/domain/services/VoiceAssistantService.kt
 */
class VoiceAssistantService @Inject constructor(
    private val voiceCommandRepository: VoiceCommandRepository,
    private val audioCaptureService: AudioCaptureService,
    private val webSocketManager: WebSocketManager,
    private val notificationManager: NotificationManagerCompat
) : Service() {

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // Service state tracking
    private var isRunning = false
    private var isConnected = false
    private var isListening = false
    private var lastActivityTime = System.currentTimeMillis()

    // State flows for UI updates
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState

    private val _serviceState = MutableStateFlow(ServiceState.STOPPED)
    val serviceState: StateFlow<ServiceState> = _serviceState

    // Idle detection
    private val idleCheckJob = serviceScope.launch {
        while (isActive) {
            delay(30000) // Check every 30 seconds
            checkIdleTimeout()
        }
    }

    enum class ConnectionState(val displayName: String) {
        DISCONNECTED("Bağlı Değil"),
        CONNECTING("Bağlanıyor..."),
        CONNECTED("PC'ye Bağlı"),
        RECONNECTING("Yeniden Bağlanıyor..."),
        ERROR("Bağlantı Hatası")
    }

    enum class ServiceState(val displayName: String) {
        STOPPED("Durduruldu"),
        STARTING("Başlatılıyor..."),
        RUNNING("Çalışıyor"),
        LISTENING("Dinleniyor..."),
        ERROR("Hata")
    }

    override fun onCreate() {
        super.onCreate()
        Log.d(TAG, "VoiceAssistantService created")
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)

        when (intent?.action) {
            ACTION_START -> startVoiceAssistant()
            ACTION_STOP -> stopVoiceAssistant()
            ACTION_VOICE_COMMAND -> startVoiceCommandCapture()
            else -> startVoiceAssistant() // Default action
        }

        return START_STICKY // Service will be restarted if killed
    }

    override fun onBind(intent: Intent?): IBinder? {
        // Return null for non-bound service
        return null
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "VoiceAssistantService destroyed")

        // Cleanup all resources
        cleanup()
    }

    /**
     * Start the voice assistant service
     */
    private fun startVoiceAssistant() {
        if (isRunning) {
            Log.d(TAG, "Service already running")
            return
        }
        Log.d(TAG, "Starting voice assistant service")
        _serviceState.value = ServiceState.STARTING
        startForeground(NOTIFICATION_ID, createNotification("Starting..."))
        serviceScope.launch {
            try {
                audioCaptureService.initialize().getOrThrow()
                connectToPCAgent()
                isRunning = true
                _serviceState.value = ServiceState.RUNNING
                lastActivityTime = System.currentTimeMillis()
                Log.d(TAG, "Voice assistant service started successfully")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to start voice assistant service", e)
                handleServiceError("Failed to start: ${e.message}")
            }
        }
    }

    private fun stopVoiceAssistant() {
        Log.d(TAG, "Stopping voice assistant service")
        try {
            audioCaptureService.stopRecording()
            webSocketManager.disconnect()
            stopForeground(true)
            stopSelf()
            isRunning = false
            isConnected = false
            _serviceState.value = ServiceState.STOPPED
            _connectionState.value = ConnectionState.DISCONNECTED
            Log.d(TAG, "Voice assistant service stopped")
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping voice assistant service", e)
        } finally {
            cleanup()
        }
    }

    /**
     * Start voice command capture
     */
    private fun startVoiceCommandCapture() {
        if (!isRunning || !isConnected || isListening) {
            Log.w(TAG, "Cannot start voice capture. Running: $isRunning, Connected: $isConnected, Listening: $isListening")
            return
        }
        Log.d(TAG, "Starting voice command capture")
        _serviceState.value = ServiceState.LISTENING
        isListening = true
        lastActivityTime = System.currentTimeMillis()
        updateNotification("Listening...")
        serviceScope.launch {
            audioCaptureService.startRecording()
            audioCaptureService.audioDataFlow.collect { audioData ->
                webSocketManager.sendAudioData(audioData)
            }
        }
    }

    private fun stopVoiceCommandCapture() {
        if (!isListening) return
        Log.d(TAG, "Stopping voice command capture")
        audioCaptureService.stopRecording()
        isListening = false
        _serviceState.value = ServiceState.RUNNING
        updateNotification("Connected to PC")
    }

    private suspend fun connectToPCAgent() {
        _connectionState.value = ConnectionState.CONNECTING
        try {
            webSocketManager.connect()
            isConnected = true
            _connectionState.value = ConnectionState.CONNECTED
            lastActivityTime = System.currentTimeMillis()
            startWebSocketMonitoring()
            Log.d(TAG, "Connected to PC agent successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect to PC agent", e)
            isConnected = false
            _connectionState.value = ConnectionState.ERROR
            scheduleReconnection()
        }
    }

    /**
     * Monitor WebSocket messages and handle command results
     */
    private fun startWebSocketMonitoring() {
        serviceScope.launch {
            webSocketManager.messageFlow.collect { message ->
                lastActivityTime = System.currentTimeMillis()
                handleMessage(message)
            }
        }
    }

    private suspend fun handleMessage(message: VoiceCommandResult) {
        when (message) {
            is VoiceCommandResult.Transcription -> {
                Log.d(TAG, "Received transcription: ${message.text}")
                voiceCommandRepository.updateCommandTranscription(message.text)
                updateNotification("Processing command...")
            }
            is VoiceCommandResult.Success -> {
                Log.d(TAG, "Command successful: ${message.message}")
                voiceCommandRepository.updateCommandStatus(CommandStatus.COMPLETED, message.message)
                stopVoiceCommandCapture()
            }
            is VoiceCommandResult.Error -> {
                Log.e(TAG, "Command error: ${message.error}")
                voiceCommandRepository.updateCommandStatus(CommandStatus.ERROR, error = message.error)
                showErrorNotification(message.error)
                stopVoiceCommandCapture()
            }
        }
    }

    private fun handleServiceError(message: String) {
        Log.e(TAG, "Service error: $message")
        _serviceState.value = ServiceState.ERROR
        showErrorNotification(message)
        stopSelf()
    }

    private fun scheduleReconnection() {
        serviceScope.launch {
            _connectionState.value = ConnectionState.RECONNECTING
            var retryDelay = 1000L
            val maxRetryDelay = 30000L

            while (isActive && !isConnected) {
                delay(retryDelay)
                try {
                    Log.d(TAG, "Attempting to reconnect...")
                    connectToPCAgent()
                    if (isConnected) break
                } catch (e: Exception) {
                    Log.w(TAG, "Reconnection attempt failed: ${e.message}")
                }
                retryDelay = (retryDelay * 2).coerceAtMost(maxRetryDelay)
            }
        }
    }

    private fun checkIdleTimeout() {
        if (!isRunning || isListening) return

        if (System.currentTimeMillis() - lastActivityTime > IDLE_TIMEOUT_MS) {
            Log.d(TAG, "Entering idle mode for battery optimization")
            serviceScope.launch {
                audioCaptureService.cleanup()
                webSocketManager.enterIdleMode()
            }
        }
    }

    /**
     * Create notification channel for foreground service
     */
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Sesli Asistan",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "PC Sesli Asistan bağlantı durumu ve komut işleme"
                setShowBadge(false)
                enableVibration(false)
                setSound(null, null)
            }

            notificationManager?.createNotificationChannel(channel)
        }
    }

    /**
     * Create notification for foreground service
     */
    private fun createNotification(statusText: String): Notification {
        val stopSelf = Intent(this, VoiceAssistantService::class.java).apply {
            action = ACTION_STOP
        }
        val pStopSelf = PendingIntent.getService(this, 0, stopSelf, PendingIntent.FLAG_IMMUTABLE)

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PC Voice Assistant")
            .setContentText(statusText)
            .setSmallIcon(R.drawable.ic_notification)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(R.drawable.ic_stop, "Stop", pStopSelf)
            .build()
    }

    /**
     * Update notification with new status
     */
    private fun updateNotification(statusText: String) {
        notificationManager.notify(NOTIFICATION_ID, createNotification(statusText))
    }

    private fun showErrorNotification(errorMessage: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Voice Assistant Error")
            .setContentText(errorMessage)
            .setSmallIcon(R.drawable.ic_error)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()
        notificationManager.notify(NOTIFICATION_ID + 1, notification)
    }

    /**
     * Cleanup all resources
     */
    private fun cleanup() {
        serviceScope.cancel()
        idleCheckJob.cancel()
    }
}