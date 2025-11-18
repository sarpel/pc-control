package com.pccontrol.voice.domain.services

import android.content.Context
import android.util.Log
import com.pccontrol.voice.data.models.Action
import com.pccontrol.voice.data.models.ActionStatus
import com.pccontrol.voice.data.models.ActionType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.*

/**
 * Browser Action Handler
 *
 * Handles browser-specific actions (navigate, search, extract, interact).
 * Coordinates with the PC agent for browser automation and provides feedback
 * to the Android UI.
 *
 * Task: T065 [P] [US2] Create browser command handling in Android action processing
 */
class BrowserActionHandler(private val context: Context) {

    companion object {
        private const val TAG = "BrowserActionHandler"

        @Volatile
        private var INSTANCE: BrowserActionHandler? = null

        fun getInstance(context: Context): BrowserActionHandler {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: BrowserActionHandler(context.applicationContext).also {
                    INSTANCE = it
                }
            }
        }
    }

    // State for page summary results (displayed in dialog)
    private val _pageSummary = MutableStateFlow<PageSummaryState>(PageSummaryState.Idle)
    val pageSummary: StateFlow<PageSummaryState> = _pageSummary.asStateFlow()

    // State for browser errors
    private val _browserError = MutableStateFlow<BrowserError?>(null)
    val browserError: StateFlow<BrowserError?> = _browserError.asStateFlow()

    /**
     * Process a browser action received from the PC agent.
     *
     * @param action The browser action to process
     * @return Updated action with result or error
     */
    suspend fun processAction(action: Action): Action {
        if (!action.actionType.isBrowserAction()) {
            Log.w(TAG, "Action ${action.actionId} is not a browser action: ${action.actionType}")
            return action.withResult(
                success = false,
                error = "İşlem bir tarayıcı komutu değil" // "Action is not a browser command"
            )
        }

        Log.d(TAG, "Processing browser action: ${action.actionType}")

        return try {
            when (action.actionType) {
                ActionType.BROWSER_NAVIGATE -> handleNavigate(action)
                ActionType.BROWSER_SEARCH -> handleSearch(action)
                ActionType.BROWSER_EXTRACT -> handleExtract(action)
                ActionType.BROWSER_INTERACT -> handleInteract(action)
                else -> action.withResult(
                    success = false,
                    error = "Bilinmeyen tarayıcı komutu" // "Unknown browser command"
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error processing browser action: ${e.message}", e)

            // Emit error for UI feedback
            _browserError.value = BrowserError(
                actionId = action.actionId,
                actionType = action.actionType,
                errorMessage = e.message ?: "Bilinmeyen hata", // "Unknown error"
                timestamp = System.currentTimeMillis()
            )

            action.withResult(
                success = false,
                error = "Tarayıcı işlemi başarısız: ${e.message}" // "Browser operation failed"
            )
        }
    }

    private fun handleNavigate(action: Action): Action {
        val url = action.parameters["url"] as? String

        if (url.isNullOrBlank()) {
            return action.withResult(
                success = false,
                error = "URL belirtilmedi" // "URL not specified"
            )
        }

        Log.d(TAG, "Browser navigate to: $url")

        // PC agent will handle the actual navigation
        // Android just tracks the command
        return action.withStatus(ActionStatus.EXECUTING)
    }

    private fun handleSearch(action: Action): Action {
        val searchQuery = action.parameters["search_query"] as? String
        val searchEngine = action.parameters["search_engine"] as? String ?: "google"

        if (searchQuery.isNullOrBlank()) {
            return action.withResult(
                success = false,
                error = "Arama sorgusu belirtilmedi" // "Search query not specified"
            )
        }

        Log.d(TAG, "Browser search: '$searchQuery' on $searchEngine")

        // PC agent will handle the actual search
        return action.withStatus(ActionStatus.EXECUTING)
    }

    private fun handleExtract(action: Action): Action {
        val extractType = action.parameters["extract_type"] as? String ?: "summary"
        val selector = action.parameters["selector"] as? String

        Log.d(TAG, "Browser extract: type=$extractType, selector=$selector")

        // Prepare to receive extracted content
        _pageSummary.value = PageSummaryState.Loading

        // PC agent will send the extracted content back
        return action.withStatus(ActionStatus.EXECUTING)
    }

    private fun handleInteract(action: Action): Action {
        val interactionType = action.parameters["interaction_type"] as? String
        val target = action.parameters["target"] as? String

        if (interactionType.isNullOrBlank()) {
            return action.withResult(
                success = false,
                error = "Etkileşim türü belirtilmedi" // "Interaction type not specified"
            )
        }

        Log.d(TAG, "Browser interact: type=$interactionType, target=$target")

        // PC agent will handle the interaction
        return action.withStatus(ActionStatus.EXECUTING)
    }

    /**
     * Handle browser action result from PC agent.
     * Called when the PC sends back the result of a browser operation.
     */
    fun handleActionResult(action: Action, resultData: Map<String, Any>?, error: String?) {
        Log.d(TAG, "Received browser action result: actionId=${action.actionId}, success=${error == null}")

        if (error != null) {
            _browserError.value = BrowserError(
                actionId = action.actionId,
                actionType = action.actionType,
                errorMessage = error,
                timestamp = System.currentTimeMillis()
            )
            return
        }

        // Handle specific result types
        when (action.actionType) {
            ActionType.BROWSER_EXTRACT -> {
                handleExtractResult(resultData)
            }
            ActionType.BROWSER_NAVIGATE, ActionType.BROWSER_SEARCH -> {
                // Navigation/search completed successfully
                Log.d(TAG, "Browser ${action.actionType} completed successfully")
            }
            ActionType.BROWSER_INTERACT -> {
                // Interaction completed
                Log.d(TAG, "Browser interaction completed successfully")
            }
            else -> {}
        }
    }

    private fun handleExtractResult(resultData: Map<String, Any>?) {
        if (resultData == null) {
            _pageSummary.value = PageSummaryState.Error("Sonuç alınamadı") // "No result received"
            return
        }

        val extractedContent = resultData["extracted_content"] as? String
        val pageTitle = resultData["page_title"] as? String
        val pageUrl = resultData["page_url"] as? String

        if (extractedContent != null) {
            _pageSummary.value = PageSummaryState.Success(
                PageSummary(
                    title = pageTitle ?: "Sayfa İçeriği", // "Page Content"
                    url = pageUrl,
                    content = extractedContent,
                    timestamp = System.currentTimeMillis()
                )
            )
        } else {
            _pageSummary.value = PageSummaryState.Error("İçerik çıkarılamadı") // "Content could not be extracted"
        }
    }

    /**
     * Clear the current page summary (dismiss dialog).
     */
    fun clearPageSummary() {
        _pageSummary.value = PageSummaryState.Idle
    }

    /**
     * Clear the current browser error.
     */
    fun clearBrowserError() {
        _browserError.value = null
    }

    /**
     * Check if there's an active browser operation.
     */
    fun hasActiveOperation(): Boolean {
        return _pageSummary.value is PageSummaryState.Loading
    }
}

/**
 * Page Summary State
 */
sealed class PageSummaryState {
    object Idle : PageSummaryState()
    object Loading : PageSummaryState()
    data class Success(val summary: PageSummary) : PageSummaryState()
    data class Error(val message: String) : PageSummaryState()
}

/**
 * Page Summary data class
 */
data class PageSummary(
    val title: String,
    val url: String?,
    val content: String,
    val timestamp: Long
)

/**
 * Browser Error data class
 */
data class BrowserError(
    val actionId: UUID,
    val actionType: ActionType,
    val errorMessage: String,
    val timestamp: Long
) {
    fun getDisplayMessage(): String {
        return when {
            errorMessage.contains("timeout", ignoreCase = true) ->
                "Tarayıcı işlemi zaman aşımına uğradı" // "Browser operation timed out"
            errorMessage.contains("not found", ignoreCase = true) ->
                "Sayfa bulunamadı" // "Page not found"
            errorMessage.contains("connection", ignoreCase = true) ->
                "Bağlantı hatası" // "Connection error"
            else -> "Tarayıcı hatası: $errorMessage" // "Browser error: ..."
        }
    }

    fun isRecoverable(): Boolean {
        return errorMessage.contains("timeout", ignoreCase = true) ||
               errorMessage.contains("connection", ignoreCase = true)
    }
}
