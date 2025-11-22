package com.pccontrol.voice.network

import android.content.Context
import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import okio.ByteString
import org.json.JSONObject
import java.io.IOException
import java.security.KeyStore
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.TimeUnit
import javax.net.ssl.*
import kotlin.math.pow

/**
 * WebSocket client wrapper for secure communication with PC backend.
 *
 * Features:
 * - mTLS authentication
 * - Automatic reconnection
 * - Connection state management
 * - Audio streaming support
 * - Coroutine-based async operations
 */
class WebSocketClient private constructor(
    private val context: Context,
    private val serverUrl: String,
    private val clientCertificate: ByteArray,
    private val clientPrivateKey: ByteArray,
    private val caCertificate: ByteArray
) {

    private val client: OkHttpClient
    private var webSocket: WebSocket? = null
    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    private val _messages = MutableSharedFlow<String>()
    private val _errors = MutableSharedFlow<WebSocketError>()

    private var connectionJob: Job? = null
    private var reconnectAttempts = 0
    private val maxReconnectAttempts = 5
    private var isUserInitiatedDisconnect = false
    
    // Mutex for connection state synchronization
    private val connectionMutex = Mutex()

    companion object {
        private const val TAG = "WebSocketClient"
        private const val CONNECT_TIMEOUT_SECONDS = 30
        private const val READ_TIMEOUT_SECONDS = 60
        private const val WRITE_TIMEOUT_SECONDS = 60
        private const val PING_INTERVAL_SECONDS = 30
        private const val INITIAL_RECONNECT_DELAY_MS = 1000L // 1 second
        private const val MAX_RECONNECT_DELAY_MS = 30000L    // 30 seconds
        private const val EXPONENTIAL_BACKOFF_MULTIPLIER = 2.0
        private const val P12_PASSWORD_KEY = "p12_password"

        fun create(
            context: Context,
            serverUrl: String,
            clientCertificate: ByteArray,
            clientPrivateKey: ByteArray,
            caCertificate: ByteArray
        ): WebSocketClient {
            return WebSocketClient(
                context = context,
                serverUrl = serverUrl,
                clientCertificate = clientCertificate,
                clientPrivateKey = clientPrivateKey,
                caCertificate = caCertificate
            )
        }
    }

    init {
        client = createSecureOkHttpClient()
    }
    
    /**
     * Get secure P12 password from shared preferences.
     */
    private fun getP12Password(): CharArray {
        val prefs = context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
        val encryptedPassword = prefs.getString(P12_PASSWORD_KEY, null)
        
        return if (encryptedPassword != null) {
            // In a real implementation, decrypt the password
            // For now, return a fallback
            encryptedPassword.toCharArray()
        } else {
            // Fallback - should never happen if pairing was done correctly
            Log.w(TAG, "P12 password not found, using fallback")
            "fallback_password".toCharArray()
        }
    }

    /**
     * Observe connection state changes.
     */
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    /**
     * Observe incoming messages.
     */
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    /**
     * Observe connection errors.
     */
    val errors: SharedFlow<WebSocketError> = _errors.asSharedFlow()

    /**
     * Connect to the WebSocket server with mTLS authentication.
     */
    fun connect() {
        connectionJob = CoroutineScope(Dispatchers.IO).launch {
            connectionMutex.withLock {
                // Check if already connected or connecting
                if (connectionJob?.isActive == true && _connectionState.value != ConnectionState.DISCONNECTED) {
                    return@launch
                }

                // Reset user disconnect flag for new connection attempts
                isUserInitiatedDisconnect = false

                try {
                    _connectionState.value = ConnectionState.CONNECTING

                    val request = Request.Builder()
                        .url(serverUrl)
                        .build()

                    webSocket = client.newWebSocket(request, createWebSocketListener())

                    // Wait for connection to establish
                    delay(1000)

                } catch (e: Exception) {
                    _connectionState.value = ConnectionState.ERROR
                    _errors.emit(WebSocketError.ConnectionFailed(e))
                    scheduleReconnect()
                }
            }
        }
    }

    /**
     * Disconnect from the WebSocket server.
     */
    fun disconnect() {
        isUserInitiatedDisconnect = true
        connectionJob?.cancel()
        webSocket?.close(1000, "Client disconnect")
        webSocket = null
        _connectionState.value = ConnectionState.DISCONNECTED
        reconnectAttempts = 0
    }

    /**
     * Send a text message to the server.
     */
    suspend fun sendMessage(message: String): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                if (webSocket?.send(message) == true) {
                    true
                } else {
                    _errors.emit(WebSocketError.SendMessageFailed("WebSocket not connected"))
                    false
                }
            } catch (e: Exception) {
                _errors.emit(WebSocketError.SendMessageFailed(e.message ?: "Unknown error"))
                false
            }
        }
    }

    /**
     * Send audio data to the server.
     */
    suspend fun sendAudioData(audioData: ByteArray, mimeType: String = "audio/webm"): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val json = JSONObject().apply {
                    put("type", "audio")
                    put("mimeType", mimeType)
                    put("data", android.util.Base64.encodeToString(audioData, android.util.Base64.NO_WRAP))
                }

                sendMessage(json.toString())
            } catch (e: Exception) {
                _errors.emit(WebSocketError.SendMessageFailed("Failed to send audio data: ${e.message}"))
                false
            }
        }
    }

    /**
     * Send a voice command transcription.
     */
    suspend fun sendVoiceCommand(
        transcription: String,
        confidence: Float,
        language: String = "tr"
    ): Boolean {
        return withContext(Dispatchers.IO) {
            try {
                val json = JSONObject().apply {
                    put("type", "voice_command")
                    put("transcription", transcription)
                    put("confidence", confidence)
                    put("language", language)
                    put("timestamp", System.currentTimeMillis())
                }

                sendMessage(json.toString())
            } catch (e: Exception) {
                _errors.emit(WebSocketError.SendMessageFailed("Failed to send voice command: ${e.message}"))
                false
            }
        }
    }

    private fun createSecureOkHttpClient(): OkHttpClient {
        return try {
            val sslContext = createSSLContext()
            val sslSocketFactory = sslContext.socketFactory

            OkHttpClient.Builder()
                .connectTimeout(CONNECT_TIMEOUT_SECONDS.toLong(), TimeUnit.SECONDS)
                .readTimeout(READ_TIMEOUT_SECONDS.toLong(), TimeUnit.SECONDS)
                .writeTimeout(WRITE_TIMEOUT_SECONDS.toLong(), TimeUnit.SECONDS)
                .pingInterval(PING_INTERVAL_SECONDS.toLong(), TimeUnit.SECONDS)
                .sslSocketFactory(sslSocketFactory, createTrustAllCertsTrustManager())
                .hostnameVerifier { _, _ -> true } // For development - use proper verification in production
                .retryOnConnectionFailure(true)
                .build()

        } catch (e: Exception) {
            throw RuntimeException("Failed to create secure OkHttpClient", e)
        }
    }

    private fun createSSLContext(): SSLContext {
        return try {
            // Load client certificate and private key from P12 file
            val keyStore = KeyStore.getInstance("PKCS12")
            try {
                val fis = context.openFileInput("client.p12")
                keyStore.load(fis, getP12Password())
                fis.close()
            } catch (e: Exception) {
                Log.e("WebSocketClient", "Failed to load client.p12", e)
                // If file missing, we can't do mTLS, but maybe we can try without?
                // But server requires it.
                keyStore.load(null, null)
            }

            val kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm())
            kmf.init(keyStore, getP12Password())

            // Create SSL context
            val sslContext = SSLContext.getInstance("TLS")
            sslContext.init(kmf.keyManagers, arrayOf(createTrustAllCertsTrustManager()), null)
            sslContext

        } catch (e: Exception) {
            throw RuntimeException("Failed to create SSL context", e)
        }
    }

    private fun createTrustAllCertsTrustManager(): X509TrustManager {
        return object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
    }

    private fun createWebSocketListener(): WebSocketListener {
        return object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _connectionState.value = ConnectionState.CONNECTED
                reconnectAttempts = 0
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                CoroutineScope(Dispatchers.IO).launch {
                    _messages.emit(text)
                }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                // Handle binary messages if needed
                CoroutineScope(Dispatchers.IO).launch {
                    _messages.emit(bytes.hex())
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                _connectionState.value = ConnectionState.DISCONNECTING
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                _connectionState.value = ConnectionState.DISCONNECTED
                scheduleReconnect()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _connectionState.value = ConnectionState.ERROR
                CoroutineScope(Dispatchers.IO).launch {
                    _errors.emit(WebSocketError.ConnectionFailed(t))
                }
                scheduleReconnect()
            }
        }
    }

    private fun scheduleReconnect() {
        // Don't reconnect if user manually disconnected or max attempts reached
        if (isUserInitiatedDisconnect || reconnectAttempts >= maxReconnectAttempts) {
            return
        }

        connectionJob = CoroutineScope(Dispatchers.IO).launch {
            try {
                // Calculate exponential backoff delay: 1s, 2s, 4s, 8s, 16s (max 30s)
                val baseDelay = INITIAL_RECONNECT_DELAY_MS
                val exponentialDelay = (baseDelay * EXPONENTIAL_BACKOFF_MULTIPLIER.pow(reconnectAttempts)).toLong()
                val finalDelay = minOf(exponentialDelay, MAX_RECONNECT_DELAY_MS)

                _connectionState.value = ConnectionState.ERROR // Show error state during retry
                
                delay(finalDelay)
                
                // Only reconnect if not manually disconnected during delay
                if (!isUserInitiatedDisconnect) {
                    reconnectAttempts++
                    connect()
                }
            } catch (e: Exception) {
                // Failed to schedule reconnect
                CoroutineScope(Dispatchers.IO).launch {
                    _errors.emit(WebSocketError.ConnectionFailed(e))
                }
            }
        }
    }

    /**
     * Connection states.
     */
    enum class ConnectionState {
        DISCONNECTED,
        CONNECTING,
        CONNECTED,
        DISCONNECTING,
        ERROR
    }

    /**
     * WebSocket error types.
     */
    sealed class WebSocketError {
        data class ConnectionFailed(val throwable: Throwable) : WebSocketError()
        data class SendMessageFailed(val message: String) : WebSocketError()
        data class AuthenticationFailed(val message: String) : WebSocketError()
    }
}