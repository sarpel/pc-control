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
import com.pccontrol.voice.data.repository.CommandStatus
import com.pccontrol.voice.services.WebSocketManager
import com.pccontrol.voice.services.CommandResult
import com.pccontrol.voice.services.MessageType
import com.pccontrol.voice.services.WebSocketMessage

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
class VoiceAssistantService : Service() {

    companion object {
        private const val TAG = "VoiceAssistantService"
        private const val NOTIFICATION_ID = 1001
        private const val CHANNEL_ID = "voice_assistant_channel"
        private const val ACTION_START = "com.pccontrol.voice.START"
        private const val ACTION_STOP = "com.pccontrol.voice.STOP"
        private const val ACTION_VOICE_COMMAND = "com.pccontrol.voice.VOICE_COMMAND"

        // Battery optimization: idle timeout (5 minutes)
        private const val IDLE_TIMEOUT_MS = 5 * 60 * 1000L
    }

    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var audioCaptureService: AudioCaptureService? = null
    private var voiceCommandRepository: VoiceCommandRepository? = null
    private var webSocketManager: WebSocketManager? = null
    private var notificationManager: NotificationManagerCompat? = null

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

        // Initialize components
        initializeComponents()

        // Create notification channel
        createNotificationChannel()

        // Initialize repository
        voiceCommandRepository = VoiceCommandRepository.Factory(this).create()
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

    inner class LocalBinder : android.os.Binder() {
        fun getService(): VoiceAssistantService = this@VoiceAssistantService
    }

    private val binder = LocalBinder()

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }

    // Public methods for ServiceManager
    fun startCapture() {
        startVoiceCommandCapture()
    }

    fun stopCapture() {
        stopVoiceCommandCapture()
    }

    fun connect() {
        // Trigger connection logic if needed, or ensure service is started
        if (!isRunning) {
            startVoiceAssistant()
        }
        // Force reconnection attempt if needed
        serviceScope.launch {
            webSocketManager?.connect()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        Log.d(TAG, "VoiceAssistantService destroyed")

        // Cleanup all resources
        cleanup()
    }

    /**
     * Initialize all service components
     */
    private fun initializeComponents() {
        notificationManager = NotificationManagerCompat.from(this)

        // Initialize audio capture service
        audioCaptureService = AudioCaptureService.Factory(this).create()

        // Initialize WebSocket manager
        webSocketManager = WebSocketManager.getInstance(this)
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

        serviceScope.launch {
            try {
                // Start foreground service with notification
                startForeground(NOTIFICATION_ID, createNotification())

                // Initialize audio capture
                audioCaptureService?.let { audio ->
                    val initResult = audio.initialize()
                    if (initResult.isFailure) {
                        throw Exception("Failed to initialize audio capture: ${initResult.exceptionOrNull()}")
                    }
                }

                // Connect to PC agent
                connectToPCAgent()

                isRunning = true
                _serviceState.value = ServiceState.RUNNING
                lastActivityTime = System.currentTimeMillis()

                Log.d(TAG, "Voice assistant service started successfully")

            } catch (e: Exception) {
                Log.e(TAG, "Failed to start voice assistant service", e)
                _serviceState.value = ServiceState.ERROR
                stopSelf()
            }
        }
    }

    /**
     * Stop the voice assistant service
     */
    private fun stopVoiceAssistant() {
        Log.d(TAG, "Stopping voice assistant service")

        serviceScope.launch {
            try {
                // Stop audio capture
                audioCaptureService?.stopRecording()

                // Disconnect WebSocket
                webSocketManager?.disconnect()

                // Stop foreground service
                stopForeground(true)
                stopSelf()

                isRunning = false
                isConnected = false
                isListening = false
                _serviceState.value = ServiceState.STOPPED
                _connectionState.value = ConnectionState.DISCONNECTED

                Log.d(TAG, "Voice assistant service stopped")

            } catch (e: Exception) {
                Log.e(TAG, "Error stopping voice assistant service", e)
            }
        }
    }

    /**
     * Start voice command capture
     */
    private fun startVoiceCommandCapture() {
        if (!isRunning || !isConnected) {
            Log.w(TAG, "Cannot start voice capture - service not ready")
            return
        }

        if (isListening) {
            Log.d(TAG, "Already listening for voice commands")
            return
        }

        Log.d(TAG, "Starting voice command capture")
        _serviceState.value = ServiceState.LISTENING

        serviceScope.launch {
            try {
                audioCaptureService?.startRecording()

                // Listen for audio data and stream to PC
                audioCaptureService?.audioDataFlow?.collect { audioData ->
                    webSocketManager?.sendAudioData(audioData)
                }

                isListening = true
                lastActivityTime = System.currentTimeMillis()

                updateNotification("Dinleniyor...") // "Listening..." in Turkish

            } catch (e: Exception) {
                Log.e(TAG, "Failed to start voice capture", e)
                _serviceState.value = ServiceState.ERROR
                isListening = false
            }
        }
    }

    /**
     * Stop voice command capture
     */
    private fun stopVoiceCommandCapture() {
        if (!isListening) {
            return
        }

        Log.d(TAG, "Stopping voice command capture")
        audioCaptureService?.stopRecording()
        isListening = false
        _serviceState.value = ServiceState.RUNNING
        updateNotification("PC'ye Bağlı") // "Connected to PC" in Turkish
    }

    /**
     * Connect to PC agent via WebSocket
     */
    private suspend fun connectToPCAgent() {
        _connectionState.value = ConnectionState.CONNECTING

        try {
            webSocketManager?.let { ws ->
                val connected = ws.connect()

                if (connected) {
                    isConnected = true
                    _connectionState.value = ConnectionState.CONNECTED
                    lastActivityTime = System.currentTimeMillis()

                    // Start monitoring WebSocket messages
                    startWebSocketMonitoring()

                    Log.d(TAG, "Connected to PC agent successfully")
                } else {
                    _connectionState.value = ConnectionState.ERROR
                    throw Exception("Failed to connect to PC agent")
                }
            }

        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect to PC agent", e)
            _connectionState.value = ConnectionState.ERROR
            isConnected = false

            // Start reconnection attempt
            scheduleReconnection()
        }
    }

    /**
     * Monitor WebSocket messages and handle command results
     */
    private fun startWebSocketMonitoring() {
        serviceScope.launch {
            webSocketManager?.messageFlow?.collect { message ->
                handleMessage(message)
                lastActivityTime = System.currentTimeMillis()
            }
        }
    }

    /**
     * Handle incoming WebSocket messages from PC agent
     */
    private suspend fun handleMessage(message: WebSocketMessage) {
        when (message.type) {
            MessageType.TRANSCRIPTION_RESULT -> {
                handleTranscriptionResult(message.data as String, message.confidence)
            }
            MessageType.COMMAND_RESULT -> {
                handleCommandResult(message.data as CommandResult)
            }
            MessageType.ERROR -> {
                handleErrorMessage(message.data as String)
            }
            MessageType.PING -> {
                // Respond to ping to keep connection alive
                webSocketManager?.sendPong()
            }
        }
    }

    /**
     * Handle speech-to-text transcription result
     */
    private suspend fun handleTranscriptionResult(transcription: String, confidence: Float) {
        Log.d(TAG, "Received transcription: $transcription (confidence: $confidence)")

        voiceCommandRepository?.let { repo ->
            val command = repo.createCommand(
                transcribedText = transcription,
                confidenceScore = confidence,
                durationMs = 0 // Will be updated by audio capture service
            )

            // Update UI state
            updateNotification("Komut işleniyor...") // "Processing command..." in Turkish
        }
    }

    /**
     * Handle command execution result from PC
     */
    private suspend fun handleCommandResult(result: CommandResult) {
        Log.d(TAG, "Received command result: $result")

        voiceCommandRepository?.let { repo ->
            // Update the current command with result
            repo.currentCommand.value?.let { currentCommand ->
                repo.updateCommandStatus(
                    commandId = currentCommand.id,
                    status = if (result.success) CommandStatus.COMPLETED else CommandStatus.ERROR,
                    result = result.message,
                    errorMessage = if (!result.success) result.message else null
                )
            }
        }

        // Stop listening and return to ready state
        stopVoiceCommandCapture()
    }

    /**
     * Handle error message from PC
     */
    private fun handleErrorMessage(errorMessage: String) {
        Log.w(TAG, "Received error from PC: $errorMessage")

        // Show error notification
        showErrorNotification(errorMessage)

        // Stop listening on error
        stopVoiceCommandCapture()
    }

    /**
     * Schedule reconnection attempt with exponential backoff
     */
    private fun scheduleReconnection() {
        serviceScope.launch {
            _connectionState.value = ConnectionState.RECONNECTING

            var retryDelay = 1000L // Start with 1 second
            val maxRetryDelay = 30000L // Max 30 seconds

            while (!isConnected && isActive) {
                delay(retryDelay)

                try {
                    connectToPCAgent()
                    if (isConnected) break
                } catch (e: Exception) {
                    Log.w(TAG, "Reconnection attempt failed", e)
                }

                // Exponential backoff
                retryDelay = (retryDelay * 2).coerceAtMost(maxRetryDelay)
            }
        }
    }

    /**
     * Check for idle timeout and optimize battery usage
     */
    private fun checkIdleTimeout() {
        if (!isRunning) return

        val timeSinceActivity = System.currentTimeMillis() - lastActivityTime
        if (timeSinceActivity > IDLE_TIMEOUT_MS) {
            Log.d(TAG, "Entering idle mode for battery optimization")

            // Optimize for battery: reduce monitoring frequency
            serviceScope.launch {
                audioCaptureService?.cleanup()
                // Keep minimal monitoring
                while (isActive && !isListening) {
                    delay(60000) // Check every minute when idle
                }
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
    private fun createNotification(): Notification {
        val statusText = when (_connectionState.value) {
            ConnectionState.CONNECTED -> "PC'ye Bağlı"
            ConnectionState.CONNECTING -> "Bağlanıyor..."
            ConnectionState.RECONNECTING -> "Yeniden Bağlanıyor..."
            ConnectionState.ERROR -> "Bağlantı Hatası"
            else -> "Hazır"
        }

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PC Sesli Asistan")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                "Durdur",
                PendingIntent.getService(
                    this,
                    0,
                    Intent(this, VoiceAssistantService::class.java).setAction(ACTION_STOP),
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .build()
    }

    /**
     * Update notification with new status
     */
    private fun updateNotification(statusText: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("PC Sesli Asistan")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setOngoing(true)
            .setSilent(true)
            .build()

        notificationManager?.notify(NOTIFICATION_ID, notification)
    }

    /**
     * Show error notification
     */
    private fun showErrorNotification(errorMessage: String) {
        notificationManager?.notify(
            NOTIFICATION_ID + 1,
            NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("Sesli Asistan Hatası")
                .setContentText(errorMessage)
                .setSmallIcon(android.R.drawable.stat_notify_error)
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .build()
        )
    }

    /**
     * Cleanup all resources
     */
    private fun cleanup() {
        serviceScope.cancel()

        audioCaptureService?.cleanup()
        audioCaptureService = null

        webSocketManager?.disconnect()
        webSocketManager = null

        voiceCommandRepository?.cleanup()
        voiceCommandRepository = null

        idleCheckJob.cancel()
    }

    /**
     * Service status for external queries
     */
    fun isConnected(): Boolean = isConnected
    fun isRunning(): Boolean = isRunning
    fun isListening(): Boolean = isListening
}