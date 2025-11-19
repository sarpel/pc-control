package com.pccontrol.voice.security

import android.content.Context
import android.security.KeyPairGeneratorSpec
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import android.util.Log
import java.io.IOException
import java.math.BigInteger
import java.security.*
import java.security.cert.Certificate
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.spec.RSAKeyGenParameterSpec
import java.util.*
import javax.crypto.*
import javax.crypto.spec.IvParameterSpec
import javax.crypto.spec.SecretKeySpec
import javax.security.auth.x500.X500Principal

/**
 * Android KeyStore wrapper for secure storage and cryptographic operations.
 *
 * This class provides:
 * - Secure key generation and storage
 * - Certificate management
 * - Encryption and decryption operations
 * - Digital signature operations
 */
class KeyStoreManager private constructor(private val context: Context) {

    companion object {
        private const val TAG = "KeyStoreManager"
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val KEYSTORE_ALIAS = "pc_voice_assistant_key"
        private const val CERTIFICATE_ALIAS = "pc_voice_assistant_cert"
        private const val KEY_ALGORITHM_RSA = "RSA"
        private const val KEY_ALGORITHM_AES = "AES"
        private const val RSA_KEY_SIZE = 2048
        private const val AES_KEY_SIZE = 256
        private const val BLOCK_MODE = KeyProperties.BLOCK_MODE_GCM
        private const val PADDING = KeyProperties.ENCRYPTION_PADDING_NONE
        private const val ENCRYPTION_TRANSFORMATION = "AES/GCM/NoPadding"

        @Volatile
        private var INSTANCE: KeyStoreManager? = null

        fun getInstance(context: Context): KeyStoreManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: KeyStoreManager(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    private val keyStore: KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE)

    init {
        try {
            keyStore.load(null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load KeyStore", e)
            throw SecurityException("KeyStore initialization failed", e)
        }
    }

    /**
     * Generate RSA key pair for client certificate signing.
     */
    fun generateRSAKeyPair(): KeyPair {
        return try {
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.M) {
                generateRSAKeyPairAPI23()
            } else {
                generateRSAKeyPairLegacy()
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to generate RSA key pair", e)
            throw SecurityException("RSA key generation failed", e)
        }
    }

    @Throws(NoSuchAlgorithmException::class, NoSuchProviderException::class, InvalidAlgorithmParameterException::class)
    private fun generateRSAKeyPairAPI23(): KeyPair {
        val keyPairGenerator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_RSA, ANDROID_KEYSTORE
        )

        val parameterSpec = KeyGenParameterSpec.Builder(
            KEYSTORE_ALIAS,
            KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
        )
            .setAlgorithmParameterSpec(RSAKeyGenParameterSpec(RSA_KEY_SIZE, BigInteger.valueOf(65537L)))
            .setDigests(KeyProperties.DIGEST_SHA256, KeyProperties.DIGEST_SHA512)
            .setSignaturePaddings(KeyProperties.SIGNATURE_PADDING_RSA_PKCS1)
            .setCertificateSubject(X500Principal("CN=PC Voice Assistant Client"))
            .setCertificateSerialNumber(BigInteger.ONE)
            .setKeyValidityForOriginationEnd(Date(System.currentTimeMillis() + 365L * 24 * 60 * 60 * 1000)) // 1 year
            .setKeyValidityForConsumptionEnd(Date(System.currentTimeMillis() + 365L * 24 * 60 * 60 * 1000)) // 1 year
            .build()

        keyPairGenerator.initialize(parameterSpec)
        return keyPairGenerator.generateKeyPair()
    }

    @Throws(NoSuchAlgorithmException::class, NoSuchProviderException::class, InvalidAlgorithmParameterException::class)
    private fun generateRSAKeyPairLegacy(): KeyPair {
        val startDate = Calendar.getInstance()
        val endDate = Calendar.getInstance()
        endDate.add(Calendar.YEAR, 1)

        val spec = KeyPairGeneratorSpec.Builder(context)
            .setAlias(KEYSTORE_ALIAS)
            .setSubject(X500Principal("CN=PC Voice Assistant Client"))
            .setSerialNumber(BigInteger.ONE)
            .setStartDate(startDate.time)
            .setEndDate(endDate.time)
            .build()

        val keyPairGenerator = KeyPairGenerator.getInstance(KEY_ALGORITHM_RSA, ANDROID_KEYSTORE)
        keyPairGenerator.initialize(spec)
        return keyPairGenerator.generateKeyPair()
    }

    /**
     * Generate AES key for symmetric encryption.
     */
    fun generateAESKey(): SecretKey {
        return try {
            val keyGenerator = KeyGenerator.getInstance(KEY_ALGORITHM_AES)
            keyGenerator.init(AES_KEY_SIZE)
            keyGenerator.generateKey()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to generate AES key", e)
            throw SecurityException("AES key generation failed", e)
        }
    }

    /**
     * Get RSA private key from KeyStore.
     */
    fun getRSAPrivateKey(): PrivateKey? {
        return try {
            val privateKeyEntry = keyStore.getEntry(KEYSTORE_ALIAS, null) as KeyStore.PrivateKeyEntry?
            privateKeyEntry?.privateKey
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get RSA private key", e)
            null
        }
    }
    
    /**
     * Get private key from KeyStore (alias for getRSAPrivateKey).
     */
    fun getPrivateKey(): PrivateKey? = getRSAPrivateKey()
    
    /**
     * Get client certificate from KeyStore.
     */
    fun getClientCertificate(): ByteArray? {
        return try {
            val certificate = getCertificate()
            certificate?.encoded
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get client certificate", e)
            null
        }
    }
    
    /**
     * Get CA certificate from KeyStore.
     */
    fun getCaCertificate(): ByteArray? {
        return try {
            val certEntry = keyStore.getCertificate(CERTIFICATE_ALIAS)
            certEntry?.encoded
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get CA certificate", e)
            null
        }
    }

    /**
     * Get RSA public key from KeyStore.
     */
    fun getRSAPublicKey(): PublicKey? {
        return try {
            val privateKeyEntry = keyStore.getEntry(KEYSTORE_ALIAS, null) as KeyStore.PrivateKeyEntry?
            privateKeyEntry?.certificate?.publicKey
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get RSA public key", e)
            null
        }
    }

    /**
     * Get certificate from KeyStore.
     */
    fun getCertificate(): Certificate? {
        return try {
            val privateKeyEntry = keyStore.getEntry(KEYSTORE_ALIAS, null) as KeyStore.PrivateKeyEntry?
            privateKeyEntry?.certificate
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get certificate", e)
            null
        }
    }

    /**
     * Import certificate into KeyStore.
     */
    fun importCertificate(certData: ByteArray): Boolean {
        return try {
            val certificateFactory = CertificateFactory.getInstance("X.509")
            val certificate = certificateFactory.generateCertificate(certData.inputStream())

            // Store certificate for verification
            val certEntry = KeyStore.TrustedCertificateEntry(certificate)
            keyStore.setEntry(CERTIFICATE_ALIAS, certEntry, null)

            Log.i(TAG, "Certificate imported successfully")
            true
        } catch (e: CertificateException) {
            Log.e(TAG, "Failed to import certificate", e)
            false
        } catch (e: IOException) {
            Log.e(TAG, "Failed to import certificate", e)
            false
        }
    }

    /**
     * Sign data with RSA private key.
     */
    fun signData(data: ByteArray): String? {
        return try {
            val privateKey = getRSAPrivateKey() ?: return null
            val signature = Signature.getInstance("SHA256withRSA")
            signature.initSign(privateKey)
            signature.update(data)
            val signatureBytes = signature.sign()
            Base64.encodeToString(signatureBytes, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to sign data", e)
            null
        }
    }

    /**
     * Verify signature with RSA public key.
     */
    fun verifySignature(data: ByteArray, signature: String): Boolean {
        return try {
            val publicKey = getRSAPublicKey() ?: return false
            val signatureBytes = Base64.decode(signature, Base64.NO_WRAP)
            val verifier = Signature.getInstance("SHA256withRSA")
            verifier.initVerify(publicKey)
            verifier.update(data)
            verifier.verify(signatureBytes)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to verify signature", e)
            false
        }
    }

    /**
     * Encrypt data with AES key.
     */
    @Throws(Exception::class)
    fun encryptData(data: ByteArray, key: SecretKey): Pair<ByteArray, ByteArray> {
        val cipher = Cipher.getInstance(ENCRYPTION_TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key)
        val iv = cipher.iv
        val encryptedData = cipher.doFinal(data)
        return Pair(encryptedData, iv)
    }

    /**
     * Decrypt data with AES key.
     */
    @Throws(Exception::class)
    fun decryptData(encryptedData: ByteArray, key: SecretKey, iv: ByteArray): ByteArray {
        val cipher = Cipher.getInstance(ENCRYPTION_TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key, IvParameterSpec(iv))
        return cipher.doFinal(encryptedData)
    }

    /**
     * Encrypt sensitive data using KeyStore.
     */
    fun encryptSensitiveData(data: String): String? {
        return try {
            val key = getOrCreateAESKey()
            val dataBytes = data.toByteArray(Charsets.UTF_8)
            val (encrypted, iv) = encryptData(dataBytes, key)

            // Combine IV and encrypted data
            val combined = iv + encrypted
            Base64.encodeToString(combined, Base64.NO_WRAP)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to encrypt sensitive data", e)
            null
        }
    }

    /**
     * Decrypt sensitive data using KeyStore.
     */
    fun decryptSensitiveData(encryptedData: String): String? {
        return try {
            val key = getOrCreateAESKey()
            val combined = Base64.decode(encryptedData, Base64.NO_WRAP)

            // Extract IV (first 12 bytes for GCM)
            val iv = combined.sliceArray(0..11)
            val encrypted = combined.sliceArray(12 until combined.size)

            val decrypted = decryptData(encrypted, key, iv)
            String(decrypted, Charsets.UTF_8)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to decrypt sensitive data", e)
            null
        }
    }

    /**
     * Get or create AES key for symmetric encryption.
     */
    private fun getOrCreateAESKey(): SecretKey {
        return try {
            // Try to get existing key from KeyStore
            val existingKey = keyStore.getKey("aes_key", null) as SecretKey?
            if (existingKey != null) {
                return existingKey
            }

            // Generate new AES key
            val newKey = generateAESKey()

            // Store AES key in KeyStore
            val keyEntry = KeyStore.SecretKeyEntry(newKey)
            val protectionParameter = android.security.keystore.KeyProtection.Builder(
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            ).setBlockModes(BLOCK_MODE)
                .setEncryptionPaddings(PADDING)
                .build()

            keyStore.setEntry("aes_key", keyEntry, protectionParameter)
            newKey
        } catch (e: Exception) {
            Log.e(TAG, "Failed to get or create AES key", e)
            throw SecurityException("AES key management failed", e)
        }
    }

    /**
     * Get certificate fingerprint.
     */
    fun getCertificateFingerprint(): String? {
        return try {
            val certificate = getCertificate() ?: return null
            val md = MessageDigest.getInstance("SHA-256")
            val digest = md.digest(certificate.encoded)

            // Convert to hexadecimal string with colons
            digest.joinToString(":") { String.format("%02x", it) }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to generate certificate fingerprint", e)
            null
        }
    }

    /**
     * Export certificate in PEM format.
     */
    fun exportCertificate(): String? {
        return try {
            val certificate = getCertificate() ?: return null
            val certBytes = certificate.encoded
            val base64Cert = Base64.encodeToString(certBytes, Base64.NO_WRAP)

            // Build PEM format
            StringBuilder().apply {
                append("-----BEGIN CERTIFICATE-----\n")
                append(base64Cert.chunked(64).joinToString("\n"))
                append("\n-----END CERTIFICATE-----\n")
            }.toString()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to export certificate", e)
            null
        }
    }

    /**
     * Check if KeyStore contains RSA key.
     */
    fun hasRSAKey(): Boolean {
        return try {
            keyStore.containsAlias(KEYSTORE_ALIAS)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to check RSA key", e)
            false
        }
    }

    /**
     * Delete RSA key from KeyStore.
     */
    fun deleteRSAKey(): Boolean {
        return try {
            if (keyStore.containsAlias(KEYSTORE_ALIAS)) {
                keyStore.deleteEntry(KEYSTORE_ALIAS)
                Log.i(TAG, "RSA key deleted from KeyStore")
                true
            } else {
                false
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to delete RSA key", e)
            false
        }
    }

    /**
     * Get key store information.
     */
    fun getKeyStoreInfo(): Map<String, Any> {
        return mapOf(
            "type" to ANDROID_KEYSTORE,
            "hasRSAKey" to hasRSAKey(),
            "hasCertificate" to (getCertificate() != null),
            "certificateFingerprint" to (getCertificateFingerprint() ?: "N/A"),
            "keyAlgorithm" to (getRSAPublicKey()?.algorithm ?: "N/A")
        )
    }
}