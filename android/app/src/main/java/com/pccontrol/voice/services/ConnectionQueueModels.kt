package com.pccontrol.voice.services

/**
 * Data models for connection queue management
 */

data class QueuedConnection(
    val id: String,
    val deviceName: String,
    val deviceInfo: Map<String, Any>,
    val queuePosition: Int,
    val queuedAt: Long,
    val maxWaitTimeMs: Long
)

data class ActiveConnection(
    val id: String,
    val deviceName: String,
    val connectedAt: Long,
    val connectionInfo: Map<String, Any>
)

data class QueueStatus(
    val queueLength: Int,
    val activeConnections: Int,
    val averageWaitTimeMs: Long,
    val timestamp: Long = System.currentTimeMillis()
)

/**
 * Generate a unique connection ID using UUID for cryptographic security
 */
fun generateConnectionId(): String {
    return java.util.UUID.randomUUID().toString()
}
