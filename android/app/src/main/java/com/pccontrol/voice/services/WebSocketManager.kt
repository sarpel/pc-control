package com.pccontrol.voice.services

import android.content.Context
import com.pccontrol.voice.network.WebSocketClient
import com.pccontrol.voice.security.KeyStoreManager
import com.pccontrol.voice.data.database.AppDatabase
import com.pccontrol.voice.data.database.PCConnection
import com.pccontrol.voice.data.models.ConnectionStatus
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.json.JSONObject
import java.util.*

/**
 * WebSocket manager service for handling communication with PC backend.
 *
 * Integrates WebSocket client with:
 * - KeyStore for certificate management
 * - Room database for connection persistence
 * - Connection state management
 * - Message routing and handling
 */
class WebSocketManager private constructor(private val context: Context) {

    private val keyStoreManager = KeyStoreManager.getInstance(context)
    private val database = AppDatabase.getDatabase(context)
    private var webSocketClient: WebSocketClient? = null
    private val _isConnected = MutableStateFlow(false)
    private val _currentConnection = MutableStateFlow<PCConnection?>(null)

    // Coroutines
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private var connectionJob: Job? = null
    private var messageListenerJob: Job? = null

    companion object {
        @Volatile
        private var INSTANCE: WebSocketManager? = null

        fun getInstance(context: Context): WebSocketManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: WebSocketManager(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    /**
     * Observe connection state.
     */
    val isConnected: StateFlow<Boolean> = _isConnected.asStateFlow()

    /**
     * Observe current connection.
     */
    val currentConnection: StateFlow<PCConnection?> = _currentConnection.asStateFlow()

    /**
     * Connect to a PC using the stored connection information.
     */
    suspend fun connectToPc(connectionId: String): Result<Unit> {
        return withContext(Dispatchers.IO) {
            try {
                // Get connection from database
                val connectionEntity = database.pcConnectionDao().getConnectionById(connectionId)
                    ?: return@withContext Result.failure(Exception("Connection not found"))

                val connection = PCConnection.fromEntity(connectionEntity)

                // Validate connection has required certificates
                val clientCert = connection.certificateFingerprint
                    ?: return@withContext Result.failure(Exception("No client certificate available"))

                // Get client certificate from KeyStore
                val certData = keyStoreManager.getClientCertificate()
                    ?: return@withContext Result.failure(Exception("Client certificate not found in KeyStore"))

                val privateKey = keyStoreManager.getPrivateKey()
                    ?: return@withContext Result.failure(Exception("Private key not found in KeyStore"))

                // Get CA certificate
                val caCert = keyStoreManager.getCaCertificate()
                    ?: return@withContext Result.failure(Exception("CA certificate not found"))

                // Create WebSocket client
                val serverUrl = "wss://${connection.pcIpAddress}:8765/ws"
                webSocketClient = WebSocketClient.create(
                    context = context,
                    serverUrl = serverUrl,
                    clientCertificate = certData,
                    clientPrivateKey = privateKey.encoded,
                    caCertificate = caCert
                )

                // Start connection monitoring
                startConnectionMonitoring()

                // Connect
                webSocketClient?.connect()

                // Update current connection
                _currentConnection.value = connection

                Result.success(Unit)

            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    /**
     * Disconnect from current PC connection.
     */
    fun disconnect() {
        connectionJob?.cancel()
        messageListenerJob?.cancel()
        webSocketClient?.disconnect()
        webSocketClient = null
        _isConnected.value = false
        _currentConnection.value = null
    }

    /**
     * Send voice command transcription to connected PC.
     */
    suspend fun sendVoiceCommand(
        transcription: String,
        confidence: Float,
        language: String = "tr"
    ): Result<Unit> {
        return try {
            val success = webSocketClient?.sendVoiceCommand(transcription, confidence, language) ?: false
            if (success) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to send voice command"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Send audio data for transcription.
     */
    suspend fun sendAudioData(audioData: ByteArray, mimeType: String = "audio/webm"): Result<Unit> {
        return try {
            val success = webSocketClient?.sendAudioData(audioData, mimeType) ?: false
            if (success) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to send audio data"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Send a custom message to the connected PC.
     */
    suspend fun sendMessage(message: String): Result<Unit> {
        return try {
            val success = webSocketClient?.sendMessage(message) ?: false
            if (success) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to send message"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Get WebSocket client for advanced operations.
     */
    fun getWebSocketClient(): WebSocketClient? = webSocketClient

    private fun startConnectionMonitoring() {
        connectionJob?.cancel()
        connectionJob = scope.launch {
            webSocketClient?.connectionState?.collect { state ->
                when (state) {
                    WebSocketClient.ConnectionState.CONNECTED -> {
                        _isConnected.value = true
                        updateConnectionStatus(ConnectionStatus.CONNECTED)
                        startMessageListener()
                    }
                    WebSocketClient.ConnectionState.CONNECTING -> {
                        updateConnectionStatus(ConnectionStatus.CONNECTING)
                    }
                    WebSocketClient.ConnectionState.DISCONNECTED,
                    WebSocketClient.ConnectionState.DISCONNECTING -> {
                        _isConnected.value = false
                        updateConnectionStatus(ConnectionStatus.DISCONNECTED)
                        messageListenerJob?.cancel()
                    }
                    WebSocketClient.ConnectionState.ERROR -> {
                        _isConnected.value = false
                        updateConnectionStatus(ConnectionStatus.ERROR)
                        messageListenerJob?.cancel()
                    }
                }
            }
        }
    }

    private fun startMessageListener() {
        messageListenerJob?.cancel()
        messageListenerJob = scope.launch {
            webSocketClient?.messages?.collect { message ->
                handleMessage(message)
            }
        }
    }

    private suspend fun handleMessage(message: String) {
        try {
            val json = JSONObject(message)
            val messageType = json.optString("type")

            when (messageType) {
                "auth_response" -> handleAuthResponse(json)
                "command_result" -> handleCommandResult(json)
                "error" -> handleError(json)
                "ping" -> handlePing(json)
                else -> {
                    // Handle unknown message types
                    println("Unknown message type: $messageType")
                }
            }

        } catch (e: Exception) {
            println("Error handling message: ${e.message}")
        }
    }

    private suspend fun handleAuthResponse(json: JSONObject) {
        val success = json.optBoolean("success", false)
        if (success) {
            updateConnectionStatus(ConnectionStatus.AUTHENTICATED)
        } else {
            updateConnectionStatus(ConnectionStatus.ERROR)
        }
    }

    private suspend fun handleCommandResult(json: JSONObject) {
        val commandId = json.optString("command_id")
        val success = json.optBoolean("success", false)
        val result = json.optString("result")
        val errorMessage = json.optString("error_message")

        // Store command result in database
        // This would be implemented based on your command tracking needs
        println("Command result: $commandId, Success: $success, Result: $result, Error: $errorMessage")
    }

    private suspend fun handleError(json: JSONObject) {
        val errorCode = json.optString("error_code")
        val errorMessage = json.optString("error_message")
        println("WebSocket error: $errorCode - $errorMessage")

        updateConnectionStatus(ConnectionStatus.ERROR)
    }

    private suspend fun handlePing(json: JSONObject) {
        // Respond to ping with pong
        webSocketClient?.sendMessage("""{"type":"pong","timestamp":${System.currentTimeMillis()}}""")
    }

    private suspend fun updateConnectionStatus(status: ConnectionStatus) {
        _currentConnection.value?.let { connection ->
            val updatedConnection = connection.copy(
                status = status,
                lastHeartbeat = if (status == ConnectionStatus.CONNECTED) {
                    System.currentTimeMillis()
                } else {
                    connection.lastHeartbeat
                }
            )

            // Update database
            database.pcConnectionDao().updateConnectionStatus(
                connection.connectionId.toString(),
                status.value
            )

            _currentConnection.value = updatedConnection
        }
    }

    /**
     * Cleanup resources.
     */
    fun cleanup() {
        disconnect()
        scope.cancel()
    }
}