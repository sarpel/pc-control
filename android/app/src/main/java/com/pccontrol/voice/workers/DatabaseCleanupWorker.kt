package com.pccontrol.voice.workers

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkRequest
import androidx.work.WorkerParameters
import com.pccontrol.voice.data.database.AppDatabase
import java.util.concurrent.TimeUnit

/**
 * Background worker for periodic database cleanup.
 * Removes expired command history and offline commands.
 */
class DatabaseCleanupWorker(
    context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        return try {
            val database = AppDatabase.getInstance(applicationContext)
            val currentTime = System.currentTimeMillis()

            // Clean up expired command history (older than 30 days)
            val thirtyDaysAgo = currentTime - TimeUnit.DAYS.toMillis(30)
            database.commandHistoryDao().deleteOlderThan(thirtyDaysAgo)

            // Clean up old offline commands (completed or failed older than 7 days)
            val sevenDaysAgo = currentTime - TimeUnit.DAYS.toMillis(7)
            database.offlineCommandDao().deleteCompletedOlderThan(sevenDaysAgo)

            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    companion object {
        /**
         * Build a periodic cleanup request that runs daily.
         */
        fun buildCleanupRequest(): WorkRequest {
            return PeriodicWorkRequestBuilder<DatabaseCleanupWorker>(
                repeatInterval = 1,
                repeatIntervalTimeUnit = TimeUnit.DAYS
            ).build()
        }

        /**
         * Build a one-time cleanup request.
         */
        fun buildOneTimeCleanupRequest(): WorkRequest {
            return OneTimeWorkRequestBuilder<DatabaseCleanupWorker>().build()
        }
    }
}
