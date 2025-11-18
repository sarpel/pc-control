package com.pccontrol.voice.data.repository

import android.content.Context
import android.util.Log
import com.pccontrol.voice.data.models.DevicePairing
import com.pccontrol.voice.data.models.PCConnection
import com.pccontrol.voice.network.WebSocketClient
import com.pccontrol.voice.security.KeyStoreManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
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
class PairingRepository(
    private val context: Context,
    private val webSocketClient: WebSocketClient,
    private val keyStoreManager: KeyStoreManager
) {
    companion object {
        private const val TAG = "PairingRepository"
        private const val PAIRING_ENDPOINT = "https://pc-ip:8443/api/pairing"
    }

    private val json = Json { ignoreUnknownKeys = true }

    /**
     * Initiate pairing process with PC.
     */
    suspend fun initiatePairing(
        deviceName: String,
        deviceId: String,
        pcIpAddress: String
    ): Result<PairingInitiateResponse> {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/initiate")
                val request = PairingInitiateRequest(deviceName, deviceId)
                val requestBody = json.encodeToString(request)

                val connection = url.openConnection() as HttpURLConnection
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Accept", "application/json")
                    doOutput = true

                    // Write request body
                    outputStream.use { it.write(requestBody.toByteArray()) }
                }

                val responseCode = connection.responseCode
                val responseBody = connection.inputStream.bufferedReader().readText()

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val response = json.decodeFromString<PairingInitiateResponse>(responseBody)
                    Log.i(TAG, "Pairing initiated: ${response.pairing_id}")
                    Result.success(response)
                } else {
                    val errorBody = connection.errorStream?.bufferedReader()?.readText()
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Log.e(TAG, "Pairing initiation failed: $errorMessage")
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: IOException) {
                Log.e(TAG, "Network error during pairing initiation", e)
                Result.failure(Exception("PC'ye bağlanılamadı. Ağ bağlantısını kontrol edin.", e))
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error during pairing initiation", e)
                Result.failure(Exception("Beklenmedik hata: ${e.message}", e))
            }
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
    ): Result<PairingVerifyResponse> {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/verify")
                val request = PairingVerifyRequest(pairingId, pairingCode, deviceId)
                val requestBody = json.encodeToString(request)

                val connection = url.openConnection() as HttpURLConnection
                connection.apply {
                    requestMethod = "POST"
                    setRequestProperty("Content-Type", "application/json")
                    setRequestProperty("Accept", "application/json")
                    doOutput = true

                    outputStream.use { it.write(requestBody.toByteArray()) }
                }

                val responseCode = connection.responseCode
                val responseBody = connection.inputStream.bufferedReader().readText()

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val response = json.decodeFromString<PairingVerifyResponse>(responseBody)

                    // Store certificates securely
                    val stored = storeCertificatesSecurely(
                        deviceId = deviceId,
                        caCertificate = response.ca_certificate,
                        clientCertificate = response.client_certificate,
                        clientPrivateKey = response.client_private_key
                    )

                    if (stored) {
                        // Store auth token
                        val encryptedToken = keyStoreManager.encryptSensitiveData(response.auth_token)
                        val tokenStored = encryptedToken != null

                        if (tokenStored) {
                            Log.i(TAG, "Pairing completed successfully for device: $deviceId")
                            Result.success(response)
                        } else {
                            Result.failure(Exception("Kimlik doğrulama anahtarı saklanamadı"))
                        }
                    } else {
                        Result.failure(Exception("Sertifikalar güvenli şekilde saklanamadı"))
                    }
                } else {
                    val errorBody = connection.errorStream?.bufferedReader()?.readText()
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Log.e(TAG, "Pairing verification failed: $errorMessage")
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: IOException) {
                Log.e(TAG, "Network error during pairing verification", e)
                Result.failure(Exception("PC'ye bağlanılamadı. Ağ bağlantısını kontrol edin.", e))
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error during pairing verification", e)
                Result.failure(Exception("Beklenmedik hata: ${e.message}", e))
            }
        }
    }

    /**
     * Get pairing status from PC.
     */
    suspend fun getPairingStatus(
        deviceId: String,
        pcIpAddress: String
    ): Result<PairingStatusResponse> {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/status?device_id=$deviceId")
                val connection = url.openConnection() as HttpURLConnection
                connection.apply {
                    requestMethod = "GET"
                    setRequestProperty("Accept", "application/json")
                }

                val responseCode = connection.responseCode
                val responseBody = connection.inputStream.bufferedReader().readText()

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val response = json.decodeFromString<PairingStatusResponse>(responseBody)
                    Result.success(response)
                } else {
                    val errorBody = connection.errorStream?.bufferedReader()?.readText()
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: Exception) {
                Log.e(TAG, "Error getting pairing status", e)
                Result.failure(Exception("Durum bilgisi alınamadı", e))
            }
        }
    }

    /**
     * Revoke device pairing.
     */
    suspend fun revokePairing(
        deviceId: String,
        pcIpAddress: String
    ): Result<Boolean> {
        return withContext(Dispatchers.IO) {
            try {
                val url = URL("${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/$deviceId")
                val connection = url.openConnection() as HttpURLConnection
                connection.apply {
                    requestMethod = "DELETE"
                    setRequestProperty("Accept", "application/json")
                }

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    // Remove stored certificates and tokens
                    removeStoredData(deviceId)
                    Result.success(true)
                } else {
                    val errorBody = connection.errorStream?.bufferedReader()?.readText()
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: Exception) {
                Log.e(TAG, "Error revoking pairing", e)
                Result.failure(Exception("Eşleştirme iptal edilemedi", e))
            }
        }
    }

    /**
     * Establish secure WebSocket connection after successful pairing.
     */
    suspend fun establishSecureConnection(
        deviceId: String,
        pcIpAddress: String,
        port: Int = 8443
    ): Result<Boolean> {
        return try {
            // Get stored auth token
            val authToken = keyStoreManager.decryptSensitiveData("auth_token_$deviceId")
            if (authToken == null) {
                return Result.failure(Exception("Kimlik doğrulama anahtarı bulunamadı"))
            }

            // Connect with WebSocket
            webSocketClient.connect()

            // Wait for connection to establish
            kotlinx.coroutines.delay(2000)

            // Check if connected
            val connected = webSocketClient.connectionState.value == 
                com.pccontrol.voice.network.WebSocketClient.ConnectionState.CONNECTED

            if (connected) {
                // Store connection info
                val connection = PCConnection(
                    connectionId = java.util.UUID.randomUUID(),
                    pcIpAddress = pcIpAddress,
                    pcMacAddress = "unknown", // Would be fetched from status
                    pcName = "PC", // Would be fetched from status
                    status = com.pccontrol.voice.data.models.ConnectionStatus.CONNECTED,
                    authenticationToken = authToken,
                    lastConnectedAt = System.currentTimeMillis()
                )

                storeConnectionInfo(connection)
                Result.success(true)
            } else {
                Result.failure(Exception("WebSocket bağlantısı kurulamadı"))
            }

        } catch (e: Exception) {
            Log.e(TAG, "Error establishing secure connection", e)
            Result.failure(Exception("Güvenli bağlantı kurulamadı", e))
        }
    }

    /**
     * Get stored device pairing information.
     */
    fun getStoredPairing(deviceId: String): DevicePairing? {
        return try {
            val certificate = keyStoreManager.getCertificate()
            val fingerprint = keyStoreManager.getCertificateFingerprint()
            val authToken = keyStoreManager.decryptSensitiveData("auth_token_$deviceId")

            if (certificate != null && fingerprint != null && authToken != null) {
                DevicePairing(
                    pairingId = java.util.UUID.randomUUID(),
                    androidDeviceId = deviceId,
                    androidFingerprint = fingerprint,
                    pcFingerprint = "stored_in_keystore",
                    pairingCode = "",
                    status = com.pccontrol.voice.data.models.PairingStatus.COMPLETED,
                    createdAt = System.currentTimeMillis(),
                    expiresAt = System.currentTimeMillis() + (365L * 24 * 60 * 60 * 1000), // 1 year
                    authenticationToken = authToken
                )
            } else {
                null
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error getting stored pairing", e)
            null
        }
    }

    /**
     * Store certificates securely in Android KeyStore.
     */
    private suspend fun storeCertificatesSecurely(
        deviceId: String,
        caCertificate: String,
        clientCertificate: String,
        clientPrivateKey: String
    ): Boolean {
        return try {
            // Store CA certificate for validation
            val caCertBytes = android.util.Base64.decode(
                caCertificate.replace("-----BEGIN CERTIFICATE-----", "")
                    .replace("-----END CERTIFICATE-----", "")
                    .replace("\n", ""),
                android.util.Base64.DEFAULT
            )
            keyStoreManager.importCertificate(caCertBytes)

            // Store client certificate
            val clientCertBytes = android.util.Base64.decode(
                clientCertificate.replace("-----BEGIN CERTIFICATE-----", "")
                    .replace("-----END CERTIFICATE-----", "")
                    .replace("\n", ""),
                android.util.Base64.DEFAULT
            )
            keyStoreManager.importCertificate(clientCertBytes)

            // Store private key (encrypted)
            val encryptedKey = keyStoreManager.encryptSensitiveData(clientPrivateKey)

            encryptedKey != null
        } catch (e: Exception) {
            Log.e(TAG, "Error storing certificates", e)
            false
        }
    }

    /**
     * Store connection information for later use.
     */
    private fun storeConnectionInfo(connection: PCConnection) {
        // Store in SharedPreferences or database
        try {
            val connectionJson = json.encodeToString(connection)
            val prefs = context.getSharedPreferences("pc_connections", Context.MODE_PRIVATE)
            prefs.edit().putString(connection.connectionId.toString(), connectionJson).apply()
        } catch (e: Exception) {
            Log.e(TAG, "Error storing connection info", e)
        }
    }

    /**
     * Remove stored pairing data.
     */
    private fun removeStoredData(deviceId: String) {
        try {
            keyStoreManager.deleteRSAKey()
            // Remove encrypted auth token from SharedPreferences
            val prefs = context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
            prefs.edit().remove("auth_token_$deviceId").apply()
        } catch (e: Exception) {
            Log.e(TAG, "Error removing stored data", e)
        }
    }

    /**
     * Parse error message from API response.
     */
    private fun parseErrorMessage(responseCode: Int, errorBody: String?): String {
        return when (responseCode) {
            HttpURLConnection.HTTP_BAD_REQUEST -> "Geçersiz istek"
            HttpURLConnection.HTTP_UNAUTHORIZED -> "Geçersiz eşleştirme kodu"
            HttpURLConnection.HTTP_FORBIDDEN -> "Maksimum cihaz sayısına ulaşıldı"
            HttpURLConnection.HTTP_NOT_FOUND -> "Cihaz bulunamadı"
            HttpURLConnection.HTTP_CONFLICT -> "Cihaz zaten eşleştirilmiş"
            HttpURLConnection.HTTP_GONE -> "Eşleştirme süresi dolmuş"
            HttpURLConnection.HTTP_INTERNAL_ERROR -> "Sunucu hatası"
            else -> "Bilinmeyen hata ($responseCode)"
        }
    }
}

// Data classes for API requests/responses
@kotlinx.serialization.Serializable
data class PairingInitiateRequest(
    val device_name: String,
    val device_id: String
)

@kotlinx.serialization.Serializable
data class PairingInitiateResponse(
    val pairing_id: String,
    val pairing_code: String,
    val expires_in_seconds: Int
)

@kotlinx.serialization.Serializable
data class PairingVerifyRequest(
    val pairing_id: String,
    val pairing_code: String,
    val device_id: String
)

@kotlinx.serialization.Serializable
data class PairingVerifyResponse(
    val ca_certificate: String,
    val client_certificate: String,
    val client_private_key: String,
    val auth_token: String,
    val token_expires_at: String
)

@kotlinx.serialization.Serializable
data class PairingStatusResponse(
    val status: String,
    val device_name: String,
    val device_id: String,
    val paired_at: String?,
    val token_expires_at: String?
)