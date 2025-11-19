package com.pccontrol.voice.data.repository

import android.content.Context
import android.util.Log
import com.pccontrol.voice.data.models.DevicePairing
import com.pccontrol.voice.data.models.PCConnection
import com.pccontrol.voice.network.WebSocketClient
import com.pccontrol.voice.security.KeyStoreManager
import com.pccontrol.voice.network.WebSocketClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString
import kotlinx.serialization.decodeFromString
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/**
 * Repository for device pairing operations.

 * Handles:
 * - Pairing initiation with PC
 * - 6-digit code verification
 * - Certificate storage in KeyStore
 * - Auth token management
 * - Connection establishment
 */
typealias PairingResult<T> = Result<T>

class PairingRepository(
    private val context: Context,
    private val webSocketClient: WebSocketClient,
    private val keyStoreManager: KeyStoreManager
) {
    companion object {
        private const val TAG = "PairingRepository"
        private const val PAIRING_ENDPOINT = "https://{pcIpAddress}:8443/api/pairing"
        private const val SECURE_PREFS_NAME = "secure_storage"
        private const val AUTH_TOKEN_KEY_PREFIX = "auth_token_"
    }

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun initiatePairing(
        deviceName: String,
        deviceId: String,
        pcIpAddress: String
    ): PairingResult<PairingInitiateResponse> = withContext(Dispatchers.IO) {
        try {
            val url = URL(PAIRING_ENDPOINT.replace("{pcIpAddress}", pcIpAddress) + "/initiate")
            val request = PairingInitiateRequest(deviceName, deviceId)
            val response = sendJsonRequest<PairingInitiateRequest, PairingInitiateResponse>(url, "POST", request)
            Log.i(TAG, "Pairing initiated: ${response.pairingId}")
            Result.success(response)
        } catch (e: Exception) {
            Log.e(TAG, "Pairing initiation failed", e)
            Result.failure(e)
        }
    }

    /**
     * Verify pairing code and complete device pairing.
     */
    suspend fun verifyPairing(
        pairingId: String,
        pairingCode: String,
        deviceId: String,
        pcIpAddress: String
    ): PairingResult<PairingVerifyResponse> = withContext(Dispatchers.IO) {
        try {
            val url = URL(PAIRING_ENDPOINT.replace("{pcIpAddress}", pcIpAddress) + "/verify")
            val request = PairingVerifyRequest(pairingId, pairingCode, deviceId)
            val response = sendJsonRequest<PairingVerifyRequest, PairingVerifyResponse>(url, "POST", request)

            storeCertificatesSecurely(
                caCertificate = response.caCertificate,
                clientCertificate = response.clientCertificate,
                clientPrivateKey = response.clientPrivateKey
            )

            storeAuthToken(deviceId, response.authToken)

            Log.i(TAG, "Pairing completed successfully for device: $deviceId")
            Result.success(response)
        } catch (e: Exception) {
            Log.e(TAG, "Pairing verification failed", e)
            Result.failure(e)
        }
    }

    suspend fun getPairingStatus(
        deviceId: String,
        pcIpAddress: String
    ): PairingResult<PairingStatusResponse> = withContext(Dispatchers.IO) {
        try {
            val url = URL(PAIRING_ENDPOINT.replace("{pcIpAddress}", pcIpAddress) + "/status?device_id=$deviceId")
            val response = sendJsonRequest<Unit, PairingStatusResponse>(url, "GET")
            Result.success(response)
        } catch (e: Exception) {
            Log.e(TAG, "Error getting pairing status", e)
            Result.failure(Exception("Durum bilgisi alınamadı", e))
        }
    }

    suspend fun revokePairing(
        deviceId: String,
        pcIpAddress: String
    ): PairingResult<Unit> = withContext(Dispatchers.IO) {
        try {
            val url = URL(PAIRING_ENDPOINT.replace("{pcIpAddress}", pcIpAddress) + "/$deviceId")
            sendJsonRequest<Unit, Unit>(url, "DELETE")
            removeStoredData(deviceId)
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "Error revoking pairing", e)
            Result.failure(Exception("Eşleştirme iptal edilemedi", e))
        }
    }

    suspend fun establishSecureConnection(
        deviceId: String,
        pcIpAddress: String,
        port: Int = 8443
    ): PairingResult<PCConnection> {
        val authToken = getAuthToken(deviceId)
            ?: return Result.failure(Exception("Authentication token not found."))

        return try {
            webSocketClient.connectSecure(pcIpAddress, port, authToken)

            val connectionResult = withTimeoutOrNull(10000) { // 10-second timeout
                webSocketClient.connectionState.first { it == WebSocketClient.ConnectionState.CONNECTED }
            }

            if (connectionResult == null) {
                return Result.failure(Exception("Connection timed out."))
            }

            val connection = PCConnection(
                connectionId = java.util.UUID.randomUUID().toString(),
                pcIpAddress = pcIpAddress,
                pcName = "Connected PC",
                status = "CONNECTED",
                authenticationState = "AUTHENTICATED",
                establishedAt = System.currentTimeMillis()
            )
            Result.success(connection)
        } catch (e: Exception) {
            Log.e(TAG, "Error establishing secure connection", e)
            Result.failure(e)
        }
    }

    /**
     * Get stored device pairing information.
     */
    suspend fun getAuthToken(deviceId: String): String? = withContext(Dispatchers.IO) {
        try {
            val prefs = context.getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
            val encryptedToken = prefs.getString("$AUTH_TOKEN_KEY_PREFIX$deviceId", null)
            encryptedToken?.let { keyStoreManager.decryptSensitiveData(it) }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get auth token", e)
            null
        }
    }

    private suspend fun storeAuthToken(deviceId: String, token: String) = withContext(Dispatchers.IO) {
        try {
            val encryptedToken = keyStoreManager.encryptSensitiveData(token)
            if (encryptedToken != null) {
                val prefs = context.getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
                prefs.edit().putString("$AUTH_TOKEN_KEY_PREFIX$deviceId", encryptedToken).apply()
            } else {
                throw Exception("Failed to encrypt auth token")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store auth token", e)
            throw e
        }
    }

    private fun storeCertificatesSecurely(
        caCertificate: String,
        clientCertificate: String,
        clientPrivateKey: String
    ) {
        try {
            keyStoreManager.storeCertificate("CA", caCertificate)
            keyStoreManager.storeCertificate("CLIENT", clientCertificate)
            keyStoreManager.storeKey("CLIENT", clientPrivateKey)
        } catch (e: Exception) {
            Log.e(TAG, "Error storing certificates", e)
            throw Exception("Failed to store certificates securely.", e)
        }
    }

    /**
     * Store connection information for later use.
     */
    private fun removeStoredData(deviceId: String) {
        try {
            keyStoreManager.deleteCertificate("CA")
            keyStoreManager.deleteCertificate("CLIENT")
            keyStoreManager.deleteKey("CLIENT")

            val prefs = context.getSharedPreferences(SECURE_PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().remove("$AUTH_TOKEN_KEY_PREFIX$deviceId").apply()
        } catch (e: Exception) {
            Log.e(TAG, "Error removing stored data", e)
        }
    }

    @Throws(IOException::class, Exception::class)
    private inline fun <reified T, reified R> sendJsonRequest(
        url: URL,
        method: String,
        requestData: T? = null
    ): R {
        val connection = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = method
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("Accept", "application/json")
            if (requestData != null) {
                doOutput = true
                outputStream.use { os ->
                    os.write(json.encodeToString(requestData).toByteArray())
                }
            }
        }

        val responseCode = connection.responseCode
        val responseBody = if (responseCode in 200..299) {
            connection.inputStream.bufferedReader().readText()
        } else {
            connection.errorStream?.bufferedReader()?.readText()
        }

        if (responseCode in 200..299) {
            if (R::class == Unit::class) {
                @Suppress("UNCHECKED_CAST")
                return Unit as R
            }
            return json.decodeFromString(responseBody ?: "")
        } else {
            val errorMessage = parseErrorMessage(responseCode, responseBody)
            throw IOException(errorMessage)
        }
    }

    /**
     * Parse error message from API response.
     */
    private fun parseErrorMessage(responseCode: Int, errorBody: String?): String {
        return errorBody ?: when (responseCode) {
            HttpURLConnection.HTTP_BAD_REQUEST -> "Invalid request"
            HttpURLConnection.HTTP_UNAUTHORIZED -> "Invalid pairing code"
            HttpURLConnection.HTTP_FORBIDDEN -> "Maximum device limit reached"
            HttpURLConnection.HTTP_NOT_FOUND -> "Device not found"
            HttpURLConnection.HTTP_CONFLICT -> "Device already paired"
            HttpURLConnection.HTTP_GONE -> "Pairing expired"
            HttpURLConnection.HTTP_INTERNAL_ERROR -> "Server error"
            else -> "Unknown error ($responseCode)"
        }
    }
}

@kotlinx.serialization.Serializable
data class PairingInitiateRequest(
    val deviceName: String,
    val deviceId: String
)

@kotlinx.serialization.Serializable
data class PairingInitiateResponse(
    val pairingId: String,
    val pairingCode: String,
    val expiresInSeconds: Int
)

@kotlinx.serialization.Serializable
data class PairingVerifyRequest(
    val pairingId: String,
    val pairingCode: String,
    val deviceId: String
)

@kotlinx.serialization.Serializable
data class PairingVerifyResponse(
    val caCertificate: String,
    val clientCertificate: String,
    val clientPrivateKey: String,
    val authToken: String,
    val tokenExpiresAt: String
)

@kotlinx.serialization.Serializable
data class PairingStatusResponse(
    val status: String,
    val deviceName: String,
    val deviceId: String,
    val pairedAt: String?,
    val tokenExpiresAt: String?
)