package com.pccontrol.voice.security

import android.util.Base64
import android.util.Log
import java.io.IOException
import java.security.MessageDigest
import java.security.NoSuchAlgorithmException
import java.security.cert.Certificate
import java.security.cert.CertificateException
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.SSLPeerUnverifiedException
import javax.net.ssl.SSLSession
import javax.net.ssl.X509TrustManager

/**
 * Certificate pinning validator for mTLS connections.
 *
 * Implements certificate pinning to prevent man-in-the-middle attacks
 * by validating server certificates against known trusted certificates.
 *
 * Features:
 * - SHA-256 certificate fingerprint pinning
 * - Public key pinning (SPKI)
 * - Certificate chain validation
 * - Hostname verification
 * - Certificate expiry checking
 * - Backup pins support
 *
 * Security Requirements (FR-005):
 * - Mutual TLS authentication
 * - Certificate pinning validation
 * - Protection against MITM attacks
 */
class CertificateValidator(
    private val keyStoreManager: KeyStoreManager
) {

    companion object {
        private const val TAG = "CertificateValidator"

        // Pin types
        const val PIN_TYPE_CERTIFICATE = "certificate"
        const val PIN_TYPE_PUBLIC_KEY = "publickey"

        // Hash algorithms
        private const val HASH_ALGORITHM_SHA256 = "SHA-256"

        // Certificate validation result codes
        const val VALIDATION_SUCCESS = 0
        const val VALIDATION_ERROR_NO_PINS = 1
        const val VALIDATION_ERROR_NO_MATCH = 2
        const val VALIDATION_ERROR_EXPIRED = 3
        const val VALIDATION_ERROR_HOSTNAME_MISMATCH = 4
        const val VALIDATION_ERROR_CHAIN_INVALID = 5
        const val VALIDATION_ERROR_EXCEPTION = 6
    }

    /**
     * Certificate pin configuration.
     */
    data class CertificatePin(
        val hostname: String,
        val pins: Set<String>,  // SHA-256 hashes (Base64 encoded)
        val pinType: String = PIN_TYPE_CERTIFICATE,
        val backupPins: Set<String> = emptySet()
    )

    /**
     * Certificate validation result.
     */
    data class ValidationResult(
        val isValid: Boolean,
        val code: Int,
        val message: String,
        val certificateInfo: Map<String, Any>? = null
    )

    // Pinned certificates storage
    private val pinnedCertificates = mutableMapOf<String, CertificatePin>()

    /**
     * Add a certificate pin for a hostname.
     */
    fun addCertificatePin(pin: CertificatePin) {
        synchronized(pinnedCertificates) {
            pinnedCertificates[pin.hostname] = pin
            Log.i(TAG, "Added certificate pin for ${pin.hostname}: ${pin.pins.size} primary pins, ${pin.backupPins.size} backup pins")
        }
    }

    /**
     * Add certificate pin from certificate data.
     */
    fun addCertificatePin(hostname: String, certificateData: ByteArray, addBackupPins: Boolean = true): Boolean {
        return try {
            val certificate = parseCertificate(certificateData)
            val fingerprint = getCertificateFingerprint(certificate)

            val pins = setOf(fingerprint)
            val backupPins = if (addBackupPins) {
                // Add public key hash as backup
                setOf(getPublicKeyHash(certificate))
            } else {
                emptySet()
            }

            val pin = CertificatePin(
                hostname = hostname,
                pins = pins,
                pinType = PIN_TYPE_CERTIFICATE,
                backupPins = backupPins
            )

            addCertificatePin(pin)
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to add certificate pin from data", e)
            false
        }
    }

    /**
     * Add public key pin for a hostname.
     */
    fun addPublicKeyPin(hostname: String, publicKeyHash: String, backupHashes: Set<String> = emptySet()) {
        val pin = CertificatePin(
            hostname = hostname,
            pins = setOf(publicKeyHash),
            pinType = PIN_TYPE_PUBLIC_KEY,
            backupPins = backupHashes
        )
        addCertificatePin(pin)
    }

    /**
     * Remove certificate pin for a hostname.
     */
    fun removeCertificatePin(hostname: String): Boolean {
        synchronized(pinnedCertificates) {
            val removed = pinnedCertificates.remove(hostname)
            if (removed != null) {
                Log.i(TAG, "Removed certificate pin for $hostname")
                return true
            }
            return false
        }
    }

    /**
     * Get certificate pin for a hostname.
     */
    fun getCertificatePin(hostname: String): CertificatePin? {
        synchronized(pinnedCertificates) {
            return pinnedCertificates[hostname]
        }
    }

    /**
     * Validate certificate chain against pinned certificates.
     */
    fun validateCertificateChain(hostname: String, certificates: Array<Certificate>): ValidationResult {
        if (certificates.isEmpty()) {
            return ValidationResult(
                isValid = false,
                code = VALIDATION_ERROR_CHAIN_INVALID,
                message = "Empty certificate chain"
            )
        }

        val pin = getCertificatePin(hostname)
        if (pin == null) {
            return ValidationResult(
                isValid = false,
                code = VALIDATION_ERROR_NO_PINS,
                message = "No certificate pins configured for $hostname"
            )
        }

        // Validate each certificate in the chain
        for (cert in certificates) {
            if (cert !is X509Certificate) {
                continue
            }

            // Check expiry
            try {
                cert.checkValidity()
            } catch (e: CertificateException) {
                return ValidationResult(
                    isValid = false,
                    code = VALIDATION_ERROR_EXPIRED,
                    message = "Certificate expired or not yet valid",
                    certificateInfo = extractCertificateInfo(cert)
                )
            }

            // Check pins
            val pinMatch = when (pin.pinType) {
                PIN_TYPE_CERTIFICATE -> validateCertificatePin(cert, pin)
                PIN_TYPE_PUBLIC_KEY -> validatePublicKeyPin(cert, pin)
                else -> false
            }

            if (pinMatch) {
                return ValidationResult(
                    isValid = true,
                    code = VALIDATION_SUCCESS,
                    message = "Certificate validation successful",
                    certificateInfo = extractCertificateInfo(cert)
                )
            }
        }

        return ValidationResult(
            isValid = false,
            code = VALIDATION_ERROR_NO_MATCH,
            message = "No certificate in chain matches pinned certificates",
            certificateInfo = extractCertificateInfo(certificates[0] as X509Certificate)
        )
    }

    /**
     * Validate SSL session.
     */
    fun validateSSLSession(session: SSLSession, hostname: String): ValidationResult {
        return try {
            // Get peer certificates
            val peerCertificates = session.peerCertificates

            // Validate certificate chain
            val chainResult = validateCertificateChain(hostname, peerCertificates)
            if (!chainResult.isValid) {
                return chainResult
            }

            // Validate hostname
            val hostnameValid = validateHostname(hostname, peerCertificates[0] as X509Certificate)
            if (!hostnameValid) {
                return ValidationResult(
                    isValid = false,
                    code = VALIDATION_ERROR_HOSTNAME_MISMATCH,
                    message = "Hostname verification failed for $hostname"
                )
            }

            ValidationResult(
                isValid = true,
                code = VALIDATION_SUCCESS,
                message = "SSL session validation successful",
                certificateInfo = extractCertificateInfo(peerCertificates[0] as X509Certificate)
            )
        } catch (e: SSLPeerUnverifiedException) {
            ValidationResult(
                isValid = false,
                code = VALIDATION_ERROR_EXCEPTION,
                message = "SSL peer unverified: ${e.message}"
            )
        } catch (e: Exception) {
            ValidationResult(
                isValid = false,
                code = VALIDATION_ERROR_EXCEPTION,
                message = "Validation exception: ${e.message}"
            )
        }
    }

    /**
     * Validate certificate fingerprint against pins.
     */
    private fun validateCertificatePin(certificate: X509Certificate, pin: CertificatePin): Boolean {
        val fingerprint = getCertificateFingerprint(certificate)

        // Check primary pins
        if (pin.pins.contains(fingerprint)) {
            Log.d(TAG, "Certificate matched primary pin")
            return true
        }

        // Check backup pins
        if (pin.backupPins.contains(fingerprint)) {
            Log.d(TAG, "Certificate matched backup pin")
            return true
        }

        return false
    }

    /**
     * Validate public key hash against pins.
     */
    private fun validatePublicKeyPin(certificate: X509Certificate, pin: CertificatePin): Boolean {
        val publicKeyHash = getPublicKeyHash(certificate)

        // Check primary pins
        if (pin.pins.contains(publicKeyHash)) {
            Log.d(TAG, "Public key matched primary pin")
            return true
        }

        // Check backup pins
        if (pin.backupPins.contains(publicKeyHash)) {
            Log.d(TAG, "Public key matched backup pin")
            return true
        }

        return false
    }

    /**
     * Get certificate fingerprint (SHA-256).
     */
    private fun getCertificateFingerprint(certificate: Certificate): String {
        return try {
            val digest = MessageDigest.getInstance(HASH_ALGORITHM_SHA256)
            val hash = digest.digest(certificate.encoded)
            Base64.encodeToString(hash, Base64.NO_WRAP)
        } catch (e: NoSuchAlgorithmException) {
            Log.e(TAG, "SHA-256 algorithm not available", e)
            throw SecurityException("Certificate fingerprint generation failed", e)
        }
    }

    /**
     * Get public key hash (SPKI - Subject Public Key Info).
     */
    private fun getPublicKeyHash(certificate: X509Certificate): String {
        return try {
            val publicKeyInfo = certificate.publicKey.encoded
            val digest = MessageDigest.getInstance(HASH_ALGORITHM_SHA256)
            val hash = digest.digest(publicKeyInfo)
            Base64.encodeToString(hash, Base64.NO_WRAP)
        } catch (e: NoSuchAlgorithmException) {
            Log.e(TAG, "SHA-256 algorithm not available", e)
            throw SecurityException("Public key hash generation failed", e)
        }
    }

    /**
     * Parse certificate from byte array.
     */
    private fun parseCertificate(certificateData: ByteArray): X509Certificate {
        return try {
            val certificateFactory = CertificateFactory.getInstance("X.509")
            certificateFactory.generateCertificate(certificateData.inputStream()) as X509Certificate
        } catch (e: CertificateException) {
            Log.e(TAG, "Failed to parse certificate", e)
            throw SecurityException("Certificate parsing failed", e)
        } catch (e: IOException) {
            Log.e(TAG, "Failed to read certificate data", e)
            throw SecurityException("Certificate reading failed", e)
        }
    }

    /**
     * Validate hostname against certificate.
     */
    private fun validateHostname(hostname: String, certificate: X509Certificate): Boolean {
        return try {
            // Get subject alternative names
            val sanList = certificate.subjectAlternativeNames
            if (sanList != null) {
                for (san in sanList) {
                    val sanType = san[0] as Int
                    val sanValue = san[1] as String

                    // Type 2 = DNS name
                    if (sanType == 2 && matchesHostname(hostname, sanValue)) {
                        return true
                    }
                }
            }

            // Check CN in subject DN
            val subjectDN = certificate.subjectX500Principal.name
            val cn = extractCN(subjectDN)
            if (cn != null && matchesHostname(hostname, cn)) {
                return true
            }

            false
        } catch (e: Exception) {
            Log.e(TAG, "Hostname validation failed", e)
            false
        }
    }

    /**
     * Extract CN from subject DN.
     */
    private fun extractCN(subjectDN: String): String? {
        val cnPrefix = "CN="
        val parts = subjectDN.split(",")
        for (part in parts) {
            val trimmed = part.trim()
            if (trimmed.startsWith(cnPrefix, ignoreCase = true)) {
                return trimmed.substring(cnPrefix.length)
            }
        }
        return null
    }

    /**
     * Match hostname with wildcard support.
     */
    private fun matchesHostname(hostname: String, pattern: String): Boolean {
        // Exact match
        if (hostname.equals(pattern, ignoreCase = true)) {
            return true
        }

        // Wildcard match (e.g., *.example.com)
        if (pattern.startsWith("*.")) {
            val patternSuffix = pattern.substring(2)
            val hostnameParts = hostname.split(".")
            val patternParts = patternSuffix.split(".")

            // Wildcard can only replace one subdomain level
            if (hostnameParts.size == patternParts.size + 1) {
                val hostnameSuffix = hostnameParts.drop(1).joinToString(".")
                return hostnameSuffix.equals(patternSuffix, ignoreCase = true)
            }
        }

        return false
    }

    /**
     * Extract certificate information for logging/debugging.
     */
    private fun extractCertificateInfo(certificate: X509Certificate): Map<String, Any> {
        return mapOf(
            "subject" to certificate.subjectX500Principal.name,
            "issuer" to certificate.issuerX500Principal.name,
            "serialNumber" to certificate.serialNumber.toString(16),
            "notBefore" to certificate.notBefore.toString(),
            "notAfter" to certificate.notAfter.toString(),
            "signatureAlgorithm" to certificate.sigAlgName,
            "version" to certificate.version,
            "fingerprint" to getCertificateFingerprint(certificate)
        )
    }

    /**
     * Create X509TrustManager with certificate pinning.
     */
    fun createPinningTrustManager(hostname: String): X509TrustManager {
        return object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {
                // Not used for client-side validation
            }

            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {
                val result = validateCertificateChain(hostname, chain)
                if (!result.isValid) {
                    throw CertificateException("Certificate pinning validation failed: ${result.message}")
                }
            }

            override fun getAcceptedIssuers(): Array<X509Certificate> {
                return emptyArray()
            }
        }
    }

    /**
     * Create HostnameVerifier with certificate pinning.
     */
    fun createPinningHostnameVerifier(): HostnameVerifier {
        return HostnameVerifier { hostname, session ->
            val result = validateSSLSession(session, hostname)
            if (!result.isValid) {
                Log.w(TAG, "Hostname verification failed for $hostname: ${result.message}")
            }
            result.isValid
        }
    }

    /**
     * Get all pinned hostnames.
     */
    fun getPinnedHostnames(): Set<String> {
        synchronized(pinnedCertificates) {
            return pinnedCertificates.keys.toSet()
        }
    }

    /**
     * Clear all certificate pins.
     */
    fun clearAllPins() {
        synchronized(pinnedCertificates) {
            val count = pinnedCertificates.size
            pinnedCertificates.clear()
            Log.i(TAG, "Cleared $count certificate pins")
        }
    }

    /**
     * Export certificate pins as JSON for backup.
     */
    fun exportPins(): String {
        synchronized(pinnedCertificates) {
            val pinsData = pinnedCertificates.map { (hostname, pin) ->
                """
                {
                    "hostname": "$hostname",
                    "pins": [${pin.pins.joinToString(",") { "\"$it\"" }}],
                    "pinType": "${pin.pinType}",
                    "backupPins": [${pin.backupPins.joinToString(",") { "\"$it\"" }}]
                }
                """.trimIndent()
            }

            return "[${pinsData.joinToString(",\n")}]"
        }
    }

    /**
     * Get certificate validator statistics.
     */
    fun getStatistics(): Map<String, Any> {
        synchronized(pinnedCertificates) {
            return mapOf(
                "totalPins" to pinnedCertificates.size,
                "hostnames" to pinnedCertificates.keys.toList(),
                "certificatePins" to pinnedCertificates.count { it.value.pinType == PIN_TYPE_CERTIFICATE },
                "publicKeyPins" to pinnedCertificates.count { it.value.pinType == PIN_TYPE_PUBLIC_KEY }
            )
        }
    }
}
