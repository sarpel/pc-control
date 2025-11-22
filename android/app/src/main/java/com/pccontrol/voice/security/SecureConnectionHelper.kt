package com.pccontrol.voice.security

import android.content.Context
import android.util.Log
import java.io.IOException
import java.security.KeyStore
import java.security.cert.CertificateFactory
import java.security.cert.X509Certificate
import java.util.regex.Pattern
import javax.net.ssl.*

/**
 * Helper class for creating secure HTTPS connections with proper certificate validation.
 *
 * This class provides:
 * - Proper SSL/TLS certificate validation
 * - CA certificate pinning
 * - Secure hostname verification
 * - IP address validation
 * - Reusable SSL context
 */
class SecureConnectionHelper(private val context: Context) {

    companion object {
        private const val TAG = "SecureConnectionHelper"
        private const val CA_ALIAS = "pc_control_ca"

        // IP address validation pattern
        private val IP_PATTERN = Pattern.compile(
            "^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}" +
            "(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
        )

        // URL validation pattern (basic)
        private val URL_PATTERN = Pattern.compile(
            "^https?://[a-zA-Z0-9.-]+(:[0-9]+)?(/.*)?$"
        )
    }

    private var sslContext: SSLContext? = null
    private var trustManager: X509TrustManager? = null

    /**
     * Initialize SSL context with CA certificate for validation.
     *
     * @param caCertificatePem CA certificate in PEM format
     * @return true if initialization successful
     */
    fun initializeWithCACertificate(caCertificatePem: String): Boolean {
        return try {
            // Parse CA certificate
            val caCert = parseCertificateFromPem(caCertificatePem)

            // Create trust store with CA certificate
            val trustStore = KeyStore.getInstance(KeyStore.getDefaultType())
            trustStore.load(null, null)
            trustStore.setCertificateEntry(CA_ALIAS, caCert)

            // Create trust manager that validates against our CA
            val tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm())
            tmf.init(trustStore)

            val trustManagers = tmf.trustManagers
            if (trustManagers.isNotEmpty() && trustManagers[0] is X509TrustManager) {
                trustManager = trustManagers[0] as X509TrustManager
            } else {
                Log.e(TAG, "No X509TrustManager found")
                return false
            }

            // Create SSL context
            sslContext = SSLContext.getInstance("TLS")
            sslContext?.init(null, arrayOf(trustManager), null)

            Log.i(TAG, "SSL context initialized with CA certificate")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize SSL context", e)
            false
        }
    }

    /**
     * Get SSL socket factory for secure connections.
     *
     * @return SSLSocketFactory or null if not initialized
     */
    fun getSSLSocketFactory(): SSLSocketFactory? {
        return sslContext?.socketFactory
    }

    /**
     * Get hostname verifier for secure connections.
     * For development: allows connections to IP addresses.
     * For production: should use strict hostname verification.
     */
    fun getHostnameVerifier(): HostnameVerifier {
        return HostnameVerifier { hostname, session ->
            // Allow IP addresses for local network connections
            if (isValidIpAddress(hostname)) {
                return@HostnameVerifier true
            }

            // For hostnames, use default verification
            try {
                val hv = HttpsURLConnection.getDefaultHostnameVerifier()
                hv.verify(hostname, session)
            } catch (e: Exception) {
                Log.w(TAG, "Hostname verification failed for: $hostname", e)
                false
            }
        }
    }

    /**
     * Create a secure HTTPS connection.
     *
     * @param url URL to connect to
     * @return Configured HttpsURLConnection
     * @throws IOException if connection cannot be created
     * @throws IllegalArgumentException if URL is invalid
     */
    fun createSecureConnection(url: String): HttpsURLConnection {
        if (!isValidUrl(url)) {
            throw IllegalArgumentException("Invalid URL: $url")
        }

        val connection = java.net.URL(url).openConnection() as HttpsURLConnection

        // Apply SSL configuration if available
        sslContext?.let {
            connection.sslSocketFactory = it.socketFactory
        }

        connection.hostnameVerifier = getHostnameVerifier()

        return connection
    }

    /**
     * Create an unsafe HTTPS connection that trusts all certificates.
     * ONLY for use during initial pairing before we have the server's CA certificate.
     */
    fun createUnsafeConnection(url: String): HttpsURLConnection {
        if (!isValidUrl(url)) {
            throw IllegalArgumentException("Invalid URL: $url")
        }

        val connection = java.net.URL(url).openConnection() as HttpsURLConnection

        connection.sslSocketFactory = getUnsafeSslSocketFactory()
        connection.hostnameVerifier = HostnameVerifier { _, _ -> true }

        return connection
    }

    private fun getUnsafeSslSocketFactory(): SSLSocketFactory {
        val trustAllCerts = arrayOf<javax.net.ssl.TrustManager>(object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
        })

        val sc = SSLContext.getInstance("TLS")
        sc.init(null, trustAllCerts, java.security.SecureRandom())
        return sc.socketFactory
    }

    /**
     * Validate IP address format.
     *
     * @param ipAddress IP address to validate
     * @return true if valid IPv4 address
     */
    fun isValidIpAddress(ipAddress: String): Boolean {
        if (ipAddress.isBlank()) return false
        return IP_PATTERN.matcher(ipAddress).matches()
    }

    /**
     * Validate URL format.
     *
     * @param url URL to validate
     * @return true if valid HTTP/HTTPS URL
     */
    fun isValidUrl(url: String): Boolean {
        if (url.isBlank()) return false

        // Check basic URL pattern
        if (!URL_PATTERN.matcher(url).matches()) {
            return false
        }

        // Extract hostname/IP from URL
        val hostStart = url.indexOf("://") + 3
        val hostEnd = url.indexOf("/", hostStart).let { if (it == -1) url.length else it }
        val portIndex = url.indexOf(":", hostStart)

        val host = if (portIndex != -1 && portIndex < hostEnd) {
            url.substring(hostStart, portIndex)
        } else {
            url.substring(hostStart, hostEnd)
        }

        // Validate hostname or IP
        return host.isNotBlank() && (isValidIpAddress(host) || isValidHostname(host))
    }

    /**
     * Validate hostname format.
     *
     * @param hostname Hostname to validate
     * @return true if valid hostname
     */
    private fun isValidHostname(hostname: String): Boolean {
        if (hostname.length > 253) return false

        val hostnamePattern = Pattern.compile(
            "^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?" +
            "(\\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"
        )

        return hostnamePattern.matcher(hostname).matches()
    }

    /**
     * Parse X509 certificate from PEM format.
     *
     * @param pemCertificate Certificate in PEM format
     * @return X509Certificate
     */
    private fun parseCertificateFromPem(pemCertificate: String): X509Certificate {
        val certContent = pemCertificate
            .replace("-----BEGIN CERTIFICATE-----", "")
            .replace("-----END CERTIFICATE-----", "")
            .replace("\n", "")
            .replace("\r", "")
            .replace(" ", "")

        val certBytes = android.util.Base64.decode(certContent, android.util.Base64.DEFAULT)

        val certificateFactory = CertificateFactory.getInstance("X.509")
        return certificateFactory.generateCertificate(certBytes.inputStream()) as X509Certificate
    }

    /**
     * Validate certificate chain against stored CA.
     *
     * @param chain Certificate chain to validate
     * @return true if chain is valid
     */
    fun validateCertificateChain(chain: Array<X509Certificate>): Boolean {
        if (chain.isEmpty()) {
            Log.w(TAG, "Empty certificate chain")
            return false
        }

        val tm = trustManager ?: run {
            Log.w(TAG, "Trust manager not initialized")
            return false
        }

        return try {
            tm.checkServerTrusted(chain, "RSA")
            true
        } catch (e: Exception) {
            Log.e(TAG, "Certificate chain validation failed", e)
            false
        }
    }

    /**
     * Get certificate fingerprint for verification.
     *
     * @param certificate Certificate to fingerprint
     * @return SHA-256 fingerprint as hex string with colons
     */
    fun getCertificateFingerprint(certificate: X509Certificate): String {
        val md = java.security.MessageDigest.getInstance("SHA-256")
        val digest = md.digest(certificate.encoded)
        return digest.joinToString(":") { String.format("%02x", it) }
    }
}
