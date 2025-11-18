package com.pccontrol.voice.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import kotlinx.coroutines.*
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger

/**
 * Service for managing connection queuing and user notifications.
 *
 * This service handles:
 * - Connection queue management
 * - User notifications for queue status
 * - Automatic reconnection attempts
 * - Connection timeout handling
 */
class ConnectionQueueService private constructor(private val context: Context) {

    companion object {
        private const val TAG = "ConnectionQueueService"
        private const val NOTIFICATION_CHANNEL_ID = "connection_queue_channel"
        private const val NOTIFICATION_CHANNEL_NAME = "PC Connection Queue"
        private const val NOTIFICATION_CHANNEL_DESCRIPTION = "Notifications for PC connection status"

        @Volatile
        private var INSTANCE: ConnectionQueueService? = null

        fun getInstance(context: Context): ConnectionQueueService {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: ConnectionQueueService(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    private val notificationManager: NotificationManagerCompat =
        NotificationManagerCompat.from(context)
    private val handler = Handler(Looper.getMainLooper())
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    // Queue management
    private val connectionQueue = mutableListOf<QueuedConnection>()
    private val activeConnections = ConcurrentHashMap<String, ActiveConnection>()
    private val queuePositionCounter = AtomicInteger(0)

    // Notification management
    private val notificationIds = ConcurrentHashMap<String, Int>()

    // Connection timeout handling
    private var connectionTimeoutJob: Job? = null
    private var queueStatusNotificationJob: Job? = null

    // Status callbacks
    private var queueStatusCallback: ((QueueStatus) -> Unit)? = null

    /**
     * Add device to connection queue.
     */
    fun addToQueue(
        deviceName: String,
        deviceInfo: Map<String, Any>,
        maxWaitTimeMinutes: Int = 10
    ): Int {
        return synchronized(connectionQueue) {
            val queuePosition = queuePositionCounter.incrementAndGet()
            val queuedConnection = QueuedConnection(
                id = generateConnectionId(),
                deviceName = deviceName,
                deviceInfo = deviceInfo,
                queuePosition = queuePosition,
                queuedAt = System.currentTimeMillis(),
                maxWaitTimeMs = maxWaitTimeMinutes * 60 * 1000L
            )

            connectionQueue.add(queuedConnection)
            Log.i(TAG, "Device ${deviceName} added to queue at position ${queuePosition}")

            // Start queue monitoring if not already running
            startQueueMonitoring()

            // Show notification
            showQueueNotification(deviceName, queuePosition)

            // Update queue status
            updateQueueStatus()

            return queuePosition
        }
    }

    /**
     * Remove device from queue.
     */
    fun removeFromQueue(connectionId: String): Boolean {
        return synchronized(connectionQueue) {
            val iterator = connectionQueue.iterator()
            while (iterator.hasNext()) {
                val connection = iterator.next()
                if (connection.id == connectionId) {
                    iterator.remove()
                    dismissQueueNotification(connectionId)
                    updateQueueStatus()
                    Log.i(TAG, "Removed connection from queue: ${connection.deviceName}")
                    return true
                }
            }
            false
        }
    }

    /**
     * Check queue position for a connection.
     */
    fun getQueuePosition(connectionId: String): Int? {
        return synchronized(connectionQueue) {
            connectionQueue.find { it.id == connectionId }?.queuePosition
        }
    }

    /**
     * Get current queue length.
     */
    fun getQueueLength(): Int {
        return synchronized(connectionQueue) {
            connectionQueue.size
        }
    }

    /**
     * Get queue status for UI updates.
     */
    fun getQueueStatus(): QueueStatus {
        return synchronized(connectionQueue) {
            QueueStatus(
                queueLength = connectionQueue.size,
                activeConnections = activeConnections.size,
                estimatedWaitTime = calculateEstimatedWaitTime(),
                nextAvailableSlot = calculateNextAvailableSlot()
            )
        }
    }

    /**
     * Register active connection.
     */
    fun registerActiveConnection(
        connectionId: String,
        deviceName: String,
        deviceInfo: Map<String, Any>
    ) {
        val activeConnection = ActiveConnection(
            id = connectionId,
            deviceName = deviceName,
            deviceInfo = deviceInfo,
            connectedAt = System.currentTimeMillis()
        )

        activeConnections[connectionId] = activeConnection
        Log.i(TAG, "Active connection registered: ${deviceName}")

        // Update queue status
        updateQueueStatus()

        // Show connection established notification
        showConnectionEstablishedNotification(deviceName)
    }

    /**
     * Unregister active connection.
     */
    fun unregisterActiveConnection(connectionId: String) {
        activeConnections.remove(connectionId)?.let { connection ->
            Log.i(TAG, "Active connection unregistered: ${connection.deviceName}")

            // Show connection lost notification
            showConnectionLostNotification(connection.deviceName)

            // Process queue to allow next connection
            processNextInQueue()
        }

        // Update queue status
        updateQueueStatus()
    }

    /**
     * Set queue status callback for UI updates.
     */
    fun setQueueStatusCallback(callback: (QueueStatus) -> Unit) {
        this.queueStatusCallback = callback
    }

    /**
     * Start monitoring the connection queue.
     */
    private fun startQueueMonitoring() {
        // Cancel existing job if running
        connectionTimeoutJob?.cancel()

        connectionTimeoutJob = serviceScope.launch {
            while (isActive) {
                delay(1000) // Check every second

                synchronized(connectionQueue) {
                    val iterator = connectionQueue.iterator()
                    val currentTime = System.currentTimeMillis()

                    while (iterator.hasNext()) {
                        val connection = iterator.next()
                        val waitTime = currentTime - connection.queuedAt

                        // Check for timeout
                        if (waitTime > connection.maxWaitTimeMs) {
                            iterator.remove()
                            dismissQueueNotification(connection.id)
                            showQueueTimeoutNotification(connection.deviceName, connection.queuePosition)
                            Log.i(TAG, "Connection timed out: ${connection.deviceName}")
                        }
                    }
                }
            }
        }

        // Start queue status notification job
        startQueueStatusNotificationJob()
    }

    /**
     * Start periodic queue status notifications.
     */
    private fun startQueueStatusNotificationJob() {
        queueStatusNotificationJob?.cancel()

        queueStatusNotificationJob = serviceScope.launch {
            while (isActive) {
                delay(30000) // Update every 30 seconds

                val queueStatus = getQueueStatus()
                if (queueStatus.queueLength > 0) {
                    showQueueStatusNotification(queueStatus)
                }
            }
        }
    }

    /**
     * Process next connection in queue.
     */
    private fun processNextInQueue() {
        serviceScope.launch {
            synchronized(connectionQueue) {
                if (connectionQueue.isNotEmpty()) {
                    val nextConnection = connectionQueue.first()
                    dismissQueueNotification(nextConnection.id)

                    // Notify device that connection slot is available
                    showConnectionAvailableNotification(nextConnection.deviceName)

                    // Remove from queue (actual connection will be established by device)
                    connectionQueue.remove(nextConnection)

                    updateQueueStatus()
                    Log.i(TAG, "Next device notified: ${nextConnection.deviceName}")
                }
            }
        }
    }

    /**
     * Calculate estimated wait time.
     */
    private fun calculateEstimatedWaitTime(): Long {
        synchronized(connectionQueue) {
            if (connectionQueue.isEmpty()) return 0

            // Simple estimation: 30 seconds per device in queue + 10 minutes max
            val baseWaitTime = connectionQueue.size * 30000L
            return minOf(baseWaitTime, 600000L) // 10 minutes max
        }
    }

    /**
     * Calculate next available slot time.
     */
    private fun calculateNextAvailableSlot(): Long {
        // Simple estimation: current time + queue processing time
        val queueProcessingTime = calculateEstimatedWaitTime()
        return System.currentTimeMillis() + queueProcessingTime
    }

    /**
     * Update queue status and notify callback.
     */
    private fun updateQueueStatus() {
        val status = getQueueStatus()
        queueStatusCallback?.invoke(status)
    }

    /**
     * Create notification channel (required for Android 8+).
     */
    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                NOTIFICATION_CHANNEL_ID,
                NOTIFICATION_CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT
            ).apply {
                description = NOTIFICATION_CHANNEL_DESCRIPTION
                enableVibration(true)
                enableLights(true)
            }

            notificationManager.createNotificationChannel(channel)
        }
    }

    /**
     * Show queue notification.
     */
    private fun showQueueNotification(deviceName: String, queuePosition: Int) {
        createNotificationChannel()

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }

        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("PC Connection Queue")
            .setContentText("Your device is ${deviceName} is queued at position ${queuePosition}")
            .setContentText("Waiting to connect to PC...")
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setContentIntent(pendingIntent)
            .setAutoCancel(false)
            .setOngoing(true)
            .build()

        val notificationId = generateNotificationId(deviceName)
        notificationManager.notify(notificationId, notification)
        notificationIds[deviceName] = notificationId
    }

    /**
     * Show connection established notification.
     */
    private fun showConnectionEstablishedNotification(deviceName: String) {
        createNotificationChannel()

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("PC Connected")
            .setContentText("Successfully connected to PC")
            .setStyle(NotificationCompat.BigTextStyle().bigText("${deviceName} is now connected to PC"))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .setTimeoutAfter(5000) // Dismiss after 5 seconds
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    /**
     * Show connection lost notification.
     */
    private fun showConnectionLostNotification(deviceName: String) {
        createNotificationChannel()

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }

        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("PC Connection Lost")
            .setContentText("Connection to PC has been lost")
            .setStyle(NotificationCompat.BigTextStyle().bigText("${deviceName} has lost connection to PC"))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    /**
     * Show queue timeout notification.
     */
    private fun showQueueTimeoutNotification(deviceName: String, queuePosition: Int) {
        createNotificationChannel()

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("Connection Queue Timeout")
            .setContentText("Queue position ${queuePosition} has expired")
            .setStyle(NotificationCompat.BigTextStyle().bigText("${deviceName} exceeded maximum wait time"))
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    /**
     * Show connection available notification.
     */
    private fun showConnectionAvailableNotification(deviceName: String) {
        createNotificationChannel()

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }

        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("PC Connection Available")
            .setContentText("${deviceName} - Ready to connect")
            .setStyle(NotificationCompat.BigTextStyle().bigText("A connection slot is now available. Tap to connect to PC."))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)
            .setTimeoutAfter(10000) // Dismiss after 10 seconds
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    /**
     * Show queue status notification.
     */
    private fun showQueueStatusNotification(queueStatus: QueueStatus) {
        createNotificationChannel()

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
        }

        val pendingIntent = PendingIntent.getActivity(
            context, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val notification = NotificationCompat.Builder(context, NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("PC Connection Queue")
            .setContentText("${queueStatus.queueLength} devices waiting")
            .setStyle(NotificationCompat.BigTextStyle().bigText(
                "${queueStatus.queueLength} devices in queue\n" +
                "Estimated wait time: ${queueStatus.estimatedWaitTime / 1000}s\n" +
                "Active connections: ${queueStatus.activeConnections}"
            ))
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setContentIntent(pendingIntent)
            .setAutoCancel(false)
            .setOngoing(true)
            .build()

        // Use fixed ID for status notification
        notificationManager.notify(-1, notification)
    }

    /**
     * Dismiss queue notification.
     */
    private fun dismissQueueNotification(connectionId: String) {
        val queueEntry = synchronized(connectionQueue) {
            connectionQueue.find { it.id == connectionId }
        }

        queueEntry?.let {
            notificationIds.remove(it.deviceName)?.let { notificationId ->
                notificationManager.cancel(notificationId)
            }
        }
    }

    /**
     * Generate unique connection ID.
     */
    private fun generateConnectionId(): String {
        return "conn_${System.currentTimeMillis()}_${(0..999).random()}"
    }

    /**
     * Generate unique notification ID.
     */
    private fun generateNotificationId(deviceName: String): Int {
        return deviceName.hashCode()
    }

    /**
     * Cleanup resources.
     */
    fun cleanup() {
        serviceScope.cancel()
        connectionTimeoutJob?.cancel()
        queueStatusNotificationJob?.cancel()

        // Cancel all notifications
        notificationIds.values.forEach { notificationId ->
            notificationManager.cancel(notificationId)
        }
        notificationManager.cancel(-1) // Status notification
        notificationIds.clear()

        Log.i(TAG, "ConnectionQueueService cleaned up")
    }

    /**
     * Data class for queued connection information.
     */
    data class QueuedConnection(
        val id: String,
        val deviceName: String,
        val deviceInfo: Map<String, Any>,
        val queuePosition: Int,
        val queuedAt: Long,
        val maxWaitTimeMs: Long
    )

    /**
     * Data class for active connection information.
     */
    data class ActiveConnection(
        val id: String,
        val deviceName: String,
        val deviceInfo: Map<String, Any>,
        val connectedAt: Long
    )

    /**
     * Data class for queue status.
     */
    data class QueueStatus(
        val queueLength: Int,
        val activeConnections: Int,
        val estimatedWaitTime: Long,
        val nextAvailableSlot: Long
    )
}