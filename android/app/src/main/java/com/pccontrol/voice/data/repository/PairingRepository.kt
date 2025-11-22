package com.pccontrol.voice.data.repository

import android.content.Context
import android.util.Base64
import android.util.Log
import com.pccontrol.voice.data.database.AppDatabase
import com.pccontrol.voice.data.models.DevicePairing
import com.pccontrol.voice.data.models.PCConnection
import com.pccontrol.voice.security.KeyStoreManager
import com.pccontrol.voice.security.SecureConnectionHelper
import com.pccontrol.voice.services.WebSocketManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.KeyFactory
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.security.spec.PKCS8EncodedKeySpec
import java.util.UUID
import javax.net.ssl.HttpsURLConnection

/**
 * Repository for device pairing operations.
 *
 * Handles:
 * - Pairing initiation with PC
 * - 6-digit code verification
 * - Certificate storage in KeyStore
 * - Auth token management
 * - Connection establishment
 */
class PairingRepository(
    private val context: Context,
    private val webSocketManager: WebSocketManager,
    private val keyStoreManager: KeyStoreManager,
    private val appDatabase: AppDatabase
) {
    companion object {
        private const val TAG = "PairingRepository"
        private const val PAIRING_ENDPOINT = "https://pc-ip:8765/api/pairing"
        private const val P12_PASSWORD_KEY = "p12_password"
    }

    private val json = Json { ignoreUnknownKeys = true }
    private val secureConnectionHelper = SecureConnectionHelper(context)

    // Generate and store secure P12 password
    private fun getOrCreateP12Password(): CharArray {
        val prefs = context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
        val encryptedPassword = prefs.getString(P12_PASSWORD_KEY, null)

        return if (encryptedPassword != null) {
            // Decrypt existing password
            val decrypted = keyStoreManager.decryptSensitiveData(encryptedPassword)
            decrypted?.toCharArray() ?: generateAndStoreP12Password()
        } else {
            generateAndStoreP12Password()
        }
    }

    private fun generateAndStoreP12Password(): CharArray {
        // Generate strong random password
        val password = UUID.randomUUID().toString() + UUID.randomUUID().toString()

        // Encrypt and store
        val encrypted = keyStoreManager.encryptSensitiveData(password)
        if (encrypted != null) {
            val prefs = context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
            prefs.edit().putString(P12_PASSWORD_KEY, encrypted).apply()
        }

        return password.toCharArray()
    }

    /**
     * Create a secure HTTPS connection with proper validation.
     */
    private fun createSecureHttpsConnection(
        urlString: String,
        method: String = "GET",
        trustAll: Boolean = false
    ): HttpsURLConnection {
        // Validate URL
        if (!secureConnectionHelper.isValidUrl(urlString)) {
            throw IllegalArgumentException("Geçersiz URL")
        }

        val connection = if (trustAll) {
            secureConnectionHelper.createUnsafeConnection(urlString)
        } else {
            secureConnectionHelper.createSecureConnection(urlString)
        }

        connection.requestMethod = method
        connection.setRequestProperty("Content-Type", "application/json")
        connection.setRequestProperty("Accept", "application/json")
        connection.connectTimeout = 10000
        connection.readTimeout = 10000

        return connection
    }

    /**
     * Initiate pairing process with PC.
     */
    suspend fun initiatePairing(
        deviceName: String,
        deviceId: String,
        pcIpAddress: String
    ): Result<PairingInitiateResponse> {
        return withContext(Dispatchers.IO) {
            // Validate IP address
            if (!secureConnectionHelper.isValidIpAddress(pcIpAddress)) {
                return@withContext Result.failure(Exception("Geçersiz IP adresi"))
            }

            var connection: HttpsURLConnection? = null
            try {
                val urlString = "${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/initiate"
                // Use unsafe connection for initial pairing (we don't have CA yet)
                connection = createSecureHttpsConnection(urlString, "POST", trustAll = true)

                val request = PairingInitiateRequest(deviceName, deviceId)
                val requestBody = json.encodeToString(request)

                connection.doOutput = true
                connection.outputStream.use { it.write(requestBody.toByteArray()) }

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseBody = connection.inputStream.use {
                        it.bufferedReader().readText()
                    }
                    val response = json.decodeFromString<PairingInitiateResponse>(responseBody)
                    Log.i(TAG, "Pairing initiated: ${response.pairing_id}")
                    Result.success(response)
                } else {
                    val errorBody = connection.errorStream?.use { it.bufferedReader().readText() }
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Log.e(TAG, "Pairing initiation failed: $errorMessage")
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: IOException) {
                Log.e(TAG, "Network error during pairing initiation", e)
                Result.failure(Exception("PC'ye bağlanılamadı. Ağ bağlantısını kontrol edin."))
            } catch (e: IllegalArgumentException) {
                Log.e(TAG, "Invalid argument during pairing initiation", e)
                Result.failure(Exception(e.message ?: "Geçersiz parametre"))
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error during pairing initiation", e)
                Result.failure(Exception("Beklenmedik hata"))
            } finally {
                connection?.disconnect()
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
            // Validate IP address
            if (!secureConnectionHelper.isValidIpAddress(pcIpAddress)) {
                return@withContext Result.failure(Exception("Geçersiz IP adresi"))
            }

            var connection: HttpsURLConnection? = null
            try {
                val urlString = "${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/verify"
                // Use unsafe connection for verification (we receive CA here)
                connection = createSecureHttpsConnection(urlString, "POST", trustAll = true)

                val request = PairingVerifyRequest(pairingId, pairingCode, deviceId)
                val requestBody = json.encodeToString(request)

                connection.doOutput = true
                connection.outputStream.use { it.write(requestBody.toByteArray()) }

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseBody = connection.inputStream.use {
                        it.bufferedReader().readText()
                    }
                    val response = json.decodeFromString<PairingVerifyResponse>(responseBody)

                    // Initialize secure connection helper with CA cert for future connections
                    secureConnectionHelper.initializeWithCACertificate(response.ca_certificate)

                    // Store certificates securely
                    val stored = storeCertificatesSecurely(
                        deviceId = deviceId,
                        caCertificate = response.ca_certificate,
                        clientCertificate = response.client_certificate,
                        clientPrivateKey = response.client_private_key
                    )

                    if (stored) {
                        // Store auth token (encrypt + persist)
                        val encryptedToken =
                            keyStoreManager.encryptSensitiveData(response.auth_token)
                        val tokenStored = encryptedToken?.let { token ->
                            val prefs =
                                context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
                            prefs.edit().putString("auth_token_$deviceId", token).commit()
                        } ?: false

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
                    val errorBody = connection.errorStream?.use { it.bufferedReader().readText() }
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Log.e(TAG, "Pairing verification failed: $errorMessage")
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: IOException) {
                Log.e(TAG, "Network error during pairing verification", e)
                Result.failure(Exception("PC'ye bağlanılamadı. Ağ bağlantısını kontrol edin."))
            } catch (e: IllegalArgumentException) {
                Log.e(TAG, "Invalid argument during pairing verification", e)
                Result.failure(Exception(e.message ?: "Geçersiz parametre"))
            } catch (e: Exception) {
                Log.e(TAG, "Unexpected error during pairing verification", e)
                Result.failure(Exception("Beklenmedik hata"))
            } finally {
                connection?.disconnect()
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
            // Validate IP address
            if (!secureConnectionHelper.isValidIpAddress(pcIpAddress)) {
                return@withContext Result.failure(Exception("Geçersiz IP adresi"))
            }

            var connection: HttpsURLConnection? = null
            try {
                val urlString = "${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/status?device_id=$deviceId"
                // This checks existing pairing, should be secure if we have certs, but might be used to check if we CAN pair?
                // Assuming this is used for post-pairing check, so keep it secure.
                connection = createSecureHttpsConnection(urlString, "GET")

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseBody = connection.inputStream.use {
                        it.bufferedReader().readText()
                    }
                    val response = json.decodeFromString<PairingStatusResponse>(responseBody)
                    Result.success(response)
                } else {
                    val errorBody = connection.errorStream?.use { it.bufferedReader().readText() }
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: Exception) {
                Log.e(TAG, "Error getting pairing status", e)
                Result.failure(Exception("Durum bilgisi alınamadı"))
            } finally {
                connection?.disconnect()
            }
        }
    }

    /**
     * Check status of an ongoing pairing session.
     */
    suspend fun checkPairingStatus(
        pairingId: String,
        pcIpAddress: String
    ): Result<PairingStatusResponse> {
        return withContext(Dispatchers.IO) {
            // Validate IP address
            if (!secureConnectionHelper.isValidIpAddress(pcIpAddress)) {
                return@withContext Result.failure(Exception("Geçersiz IP adresi"))
            }

            var connection: HttpsURLConnection? = null
            try {
                val urlString = "${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/status/$pairingId"
                // Polling during pairing process -> must be unsafe as we have no CA yet
                connection = createSecureHttpsConnection(urlString, "GET", trustAll = true)

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    val responseBody = connection.inputStream.use {
                        it.bufferedReader().readText()
                    }
                    val response = json.decodeFromString<PairingStatusResponse>(responseBody)
                    Result.success(response)
                } else {
                    val errorBody = connection.errorStream?.use { it.bufferedReader().readText() }
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Result.failure(Exception(errorMessage))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error checking pairing status", e)
                Result.failure(e)
            } finally {
                connection?.disconnect()
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
            // Validate IP address
            if (!secureConnectionHelper.isValidIpAddress(pcIpAddress)) {
                return@withContext Result.failure(Exception("Geçersiz IP adresi"))
            }

            var connection: HttpsURLConnection? = null
            try {
                val urlString = "${PAIRING_ENDPOINT.replace("pc-ip", pcIpAddress)}/$deviceId"
                connection = createSecureHttpsConnection(urlString, "DELETE")

                val responseCode = connection.responseCode

                if (responseCode == HttpURLConnection.HTTP_OK) {
                    // Remove stored certificates and tokens
                    removeStoredData(deviceId)
                    Result.success(true)
                } else {
                    val errorBody = connection.errorStream?.use { it.bufferedReader().readText() }
                    val errorMessage = parseErrorMessage(responseCode, errorBody)
                    Result.failure(Exception(errorMessage))
                }

            } catch (e: Exception) {
                Log.e(TAG, "Error revoking pairing", e)
                Result.failure(Exception("Eşleştirme iptal edilemedi"))
            } finally {
                connection?.disconnect()
            }
        }
    }

    /**
     * Establish secure WebSocket connection after successful pairing.
     */
    suspend fun establishSecureConnection(
        deviceId: String,
        pcIpAddress: String,
        port: Int = 8765
    ): Result<Boolean> {
        return try {
            // Get stored auth token
            val prefs = context.getSharedPreferences("secure_storage", Context.MODE_PRIVATE)
            val encryptedToken = prefs.getString("auth_token_$deviceId", null)
            val authToken = encryptedToken?.let { keyStoreManager.decryptSensitiveData(it) }

            if (authToken == null) {
                return Result.failure(Exception("Kimlik doğrulama anahtarı bulunamadı"))
            }

            // Create connection info
            val connectionId = java.util.UUID.randomUUID()
            val connection = PCConnection(
                connectionId = connectionId,
                pcIpAddress = pcIpAddress,
                pcMacAddress = "unknown", // Would be fetched from status
                pcName = "PC", // Would be fetched from status
                status = com.pccontrol.voice.data.models.ConnectionStatus.CONNECTED,
                authenticationToken = authToken,
                lastConnectedAt = System.currentTimeMillis()
            )

            // Store connection info first so WebSocketManager can find it
            storeConnectionInfo(connection)

            // Connect with WebSocketManager
            val connectResult = webSocketManager.connectToPc(connectionId.toString())

            if (connectResult.isSuccess) {
                Result.success(true)
            } else {
                Result.failure(
                    connectResult.exceptionOrNull() ?: Exception("WebSocket bağlantısı kurulamadı")
                )
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

            // Save to P12 file for WebSocketClient
            saveP12Keystore(caCertificate, clientCertificate, clientPrivateKey)

            encryptedKey != null
        } catch (e: Exception) {
            Log.e(TAG, "Error storing certificates", e)
            false
        }
    }

    /**
     * Store connection information for later use.
     */
    private suspend fun storeConnectionInfo(connection: PCConnection) {
        try {
            // Store in database
            val entity = connection.toEntity()
            appDatabase.pcConnectionDao().insertConnection(entity)

            // Also store in SharedPreferences for legacy/backup (optional)
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
    suspend fun removePairing(deviceId: String) {
        try {
            // Remove from database
            // Note: deviceId here is likely the connectionId or related
            // Using deleteConnectionById since deviceId is a String (connectionId)
            appDatabase.pcConnectionDao().deleteConnectionById(deviceId)

            removeStoredData(deviceId)
        } catch (e: Exception) {
            Log.e(TAG, "Error removing pairing", e)
        }
    }

    /**
     * Remove stored pairing data (internal).
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

    private fun saveP12Keystore(caCertPem: String, clientCertPem: String, privateKeyPem: String) {
        try {
            // 1. Parse Private Key
            val privateKeyContent = privateKeyPem
                .replace("-----BEGIN PRIVATE KEY-----", "")
                .replace("-----END PRIVATE KEY-----", "")
                .replace("\n", "")
                .replace(" ", "")
            val privateKeyBytes = Base64.decode(privateKeyContent, Base64.DEFAULT)
            val keySpec = PKCS8EncodedKeySpec(privateKeyBytes)
            val keyFactory = KeyFactory.getInstance("RSA")
            val privateKey = keyFactory.generatePrivate(keySpec)

            // 2. Parse Certificates
            val certFactory = CertificateFactory.getInstance("X.509")

            val caCertContent = caCertPem
                .replace("-----BEGIN CERTIFICATE-----", "")
                .replace("-----END CERTIFICATE-----", "")
                .replace("\n", "")
            val caCertBytes = Base64.decode(caCertContent, Base64.DEFAULT)
            val caCert =
                certFactory.generateCertificate(caCertBytes.inputStream()) as X509Certificate

            val clientCertContent = clientCertPem
                .replace("-----BEGIN CERTIFICATE-----", "")
                .replace("-----END CERTIFICATE-----", "")
                .replace("\n", "")
            val clientCertBytes = Base64.decode(clientCertContent, Base64.DEFAULT)
            val clientCert =
                certFactory.generateCertificate(clientCertBytes.inputStream()) as X509Certificate

            // 3. Create PKCS12 KeyStore
            val keyStore = KeyStore.getInstance("PKCS12")
            keyStore.load(null, null)

            // 4. Get secure password
            val password = getOrCreateP12Password()

            // 5. Set Key Entry with Chain
            val chain = arrayOf(clientCert, caCert)
            keyStore.setKeyEntry("client", privateKey, password, chain)

            // 6. Save to File
            context.openFileOutput("client.p12", Context.MODE_PRIVATE).use { fos ->
                keyStore.store(fos, password)
            }

            Log.i(TAG, "P12 KeyStore saved successfully")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to save P12 KeyStore", e)
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
