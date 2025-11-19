package com.pccontrol.voice.audio

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.File
import java.util.*
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Audio processing service that combines recording and transcription.
 *
 * Features:
 * - Voice command detection
 * - Automatic recording control
 * - Real-time transcription
 * - Noise filtering
 * - Command validation
 */
class AudioProcessingService private constructor(
    private val context: Context
) {
    private val audioRecorder = AudioRecorder.getInstance(context)
    private val speechToTextService = SpeechToTextService.getInstance(context)

    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private val isProcessing = AtomicBoolean(false)
    private var currentRecordingFile: File? = null
    private var transcriptionJob: Job? = null

    // State flows
    private val _processingState = MutableStateFlow(ProcessingState.IDLE)
    private val _currentTranscription = MutableStateFlow<String?>(null)
    private val _transcriptionConfidence = MutableStateFlow(0f)
    private val _voiceLevel = MutableStateFlow(0f)
    private val _errors = MutableSharedFlow<AudioProcessingError>()

    companion object {
        private const val MIN_VOICE_LEVEL_THRESHOLD = 0.1f
        private const val MAX_SILENCE_DURATION_MS = 2000L
        private const val MIN_RECORDING_DURATION_MS = 500L
        private const val MAX_RECORDING_DURATION_MS = 10000L

        @Volatile
        private var INSTANCE: AudioProcessingService? = null

        fun getInstance(context: Context): AudioProcessingService {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: AudioProcessingService(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    /**
     * Observe processing state.
     */
    val processingState: StateFlow<ProcessingState> = _processingState.asStateFlow()

    /**
     * Observe current transcription.
     */
    val currentTranscription: StateFlow<String?> = _currentTranscription.asStateFlow()

    /**
     * Observe transcription confidence.
     */
    val transcriptionConfidence: StateFlow<Float> = _transcriptionConfidence.asStateFlow()

    /**
     * Observe voice level.
     */
    val voiceLevel: StateFlow<Float> = _voiceLevel.asStateFlow()

    /**
     * Observe processing errors.
     */
    val errors: SharedFlow<AudioProcessingError> = _errors.asSharedFlow()

    /**
     * Initialize the audio processing service.
     */
    suspend fun initialize(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            // Initialize STT service
            speechToTextService.initialize()
            Result.success(Unit)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Start voice command processing.
     */
    suspend fun startVoiceCommandProcessing(): Result<VoiceCommandResult> = withContext(Dispatchers.Main) {
        try {
            if (isProcessing.get()) {
                return@withContext Result.failure(Exception("Already processing"))
            }

            if (!audioRecorder.hasRecordingPermission()) {
                return@withContext Result.failure(Exception("Recording permission not granted"))
            }

            isProcessing.set(true)
            _processingState.value = ProcessingState.LISTENING

            // Start recording
            val recordingResult = audioRecorder.startRecording()
            if (recordingResult.isFailure) {
                throw recordingResult.exceptionOrNull() ?: Exception("Failed to start recording")
            }

            currentRecordingFile = recordingResult.getOrThrow()

            // Start monitoring
            startAudioMonitoring()

            Result.success(VoiceCommandResult(status = VoiceCommandStatus.LISTENING))

        } catch (e: Exception) {
            isProcessing.set(false)
            _processingState.value = ProcessingState.ERROR
            _errors.emit(AudioProcessingError.RecordingError(message = e.message, cause = e))
            Result.failure(e)
        }
    }

    /**
     * Stop current voice command processing.
     */
    suspend fun stopVoiceCommandProcessing(): Result<VoiceCommandResult> = withContext(Dispatchers.Main) {
        try {
            if (!isProcessing.get()) {
                return@withContext Result.success(
                    VoiceCommandResult(status = VoiceCommandStatus.IDLE)
                )
            }

            _processingState.value = ProcessingState.PROCESSING

            // Stop recording
            val recordingResult = audioRecorder.stopRecording()
            if (recordingResult.isFailure) {
                throw recordingResult.exceptionOrNull() ?: Exception("Failed to stop recording")
            }

            val audioFile = recordingResult.getOrThrow()
            currentRecordingFile = null

            // Start transcription
            val transcriptionResult = transcribeAudioFile(audioFile)

            // Update state
            isProcessing.set(false)
            _processingState.value = ProcessingState.IDLE

            Result.success(transcriptionResult)

        } catch (e: Exception) {
            isProcessing.set(false)
            _processingState.value = ProcessingState.ERROR
            _errors.emit(AudioProcessingError.TranscriptionError(message = e.message, cause = e))
            Result.failure(e)
        }
    }

    /**
     * Cancel current processing.
     */
    suspend fun cancelProcessing(): Result<Unit> = withContext(Dispatchers.Main) {
        try {
            transcriptionJob?.cancel()
            audioRecorder.cancelRecording()
            currentRecordingFile = null

            isProcessing.set(false)
            _processingState.value = ProcessingState.IDLE
            _currentTranscription.value = null
            _transcriptionConfidence.value = 0f

            Result.success(Unit)

        } catch (e: Exception) {
            _errors.emit(AudioProcessingError.CancellationError(message = e.message, cause = e))
            Result.failure(e)
        }
    }

    /**
     * Process audio file directly.
     */
    suspend fun processAudioFile(audioFile: File): Result<VoiceCommandResult> = withContext(Dispatchers.IO) {
        try {
            if (!audioFile.exists()) {
                return@withContext Result.failure(Exception("Audio file not found"))
            }

            _processingState.value = ProcessingState.PROCESSING

            val transcriptionResult = transcribeAudioFile(audioFile)

            Result.success(transcriptionResult)

        } catch (e: Exception) {
            _processingState.value = ProcessingState.ERROR
            _errors.emit(AudioProcessingError.TranscriptionError(message = e.message, cause = e))
            Result.failure(e)
        }
    }

    /**
     * Check if currently processing.
     */
    fun isProcessing(): Boolean = isProcessing.get()

    private fun startAudioMonitoring() {
        scope.launch {
            // Monitor audio level
            launch {
                audioRecorder.audioLevel.collect { level ->
                    _voiceLevel.value = level
                }
            }

            // Monitor recording state
            launch {
                audioRecorder.recordingState.collect { state ->
                    when (state) {
                        AudioRecorder.RecordingState.RECORDING -> {
                            // Active recording
                        }
                        AudioRecorder.RecordingState.COMPLETED -> {
                            // Recording completed
                        }
                        AudioRecorder.RecordingState.CANCELLED -> {
                            // Recording cancelled
                        }
                        AudioRecorder.RecordingState.ERROR -> {
                            _errors.emit(AudioProcessingError.RecordingError(message = "Recording error"))
                        }
                        else -> {
                            // Other states
                        }
                    }
                }
            }

            // Auto-stop on silence
            launch {
                var lastVoiceDetectedTime = System.currentTimeMillis()
                var recordingStartTime = System.currentTimeMillis()

                while (isProcessing.get()) {
                    val currentLevel = _voiceLevel.value
                    val currentTime = System.currentTimeMillis()
                    val recordingDuration = currentTime - recordingStartTime

                    if (currentLevel > MIN_VOICE_LEVEL_THRESHOLD) {
                        lastVoiceDetectedTime = currentTime
                    }

                    // Check if should auto-stop
                    val silenceDuration = currentTime - lastVoiceDetectedTime
                    if (silenceDuration > MAX_SILENCE_DURATION_MS && recordingDuration > MIN_RECORDING_DURATION_MS) {
                        // Stop recording due to silence
                        stopVoiceCommandProcessing()
                        break
                    }

                    if (recordingDuration > MAX_RECORDING_DURATION_MS) {
                        // Stop recording due to max duration
                        stopVoiceCommandProcessing()
                        break
                    }

                    delay(100)
                }
            }
        }
    }

    private suspend fun transcribeAudioFile(audioFile: File): VoiceCommandResult {
        return try {
            val transcriptionResult = speechToTextService.transcribe(audioFile)

            if (transcriptionResult.isSuccess) {
                val transcription = transcriptionResult.getOrThrow()
                _currentTranscription.value = transcription.text
                _transcriptionConfidence.value = transcription.confidence

                if (transcription.isValid()) {
                    VoiceCommandResult(
                        status = VoiceCommandStatus.COMPLETED,
                        transcription = transcription.text,
                        confidence = transcription.confidence,
                        audioFile = audioFile,
                        language = transcription.language,
                        durationMs = audioRecorder.recordingDuration.value
                    )
                } else {
                    VoiceCommandResult(
                        status = VoiceCommandStatus.LOW_CONFIDENCE,
                        transcription = transcription.text,
                        confidence = transcription.confidence,
                        audioFile = audioFile,
                        errorMessage = "Low confidence transcription"
                    )
                }
            } else {
                val error = transcriptionResult.exceptionOrNull()
                VoiceCommandResult(
                    status = VoiceCommandStatus.TRANSCRIPTION_FAILED,
                    audioFile = audioFile,
                    errorMessage = error?.message ?: "Transcription failed"
                )
            }

        } catch (e: Exception) {
            VoiceCommandResult(
                status = VoiceCommandStatus.TRANSCRIPTION_FAILED,
                audioFile = audioFile,
                errorMessage = e.message ?: "Unknown error"
            )
        }
    }

    /**
     * Cleanup resources.
     */
    fun cleanup() {
        scope.cancel()
        audioRecorder.cleanup()
        speechToTextService.cleanup()
    }

    /**
     * Processing states.
     */
    enum class ProcessingState {
        IDLE,
        LISTENING,
        PROCESSING,
        COMPLETED,
        ERROR
    }

    /**
     * Voice command status.
     */
    enum class VoiceCommandStatus {
        IDLE,
        LISTENING,
        PROCESSING,
        COMPLETED,
        LOW_CONFIDENCE,
        TRANSCRIPTION_FAILED,
        CANCELLED,
        ERROR
    }

    /**
     * Voice command result.
     */
    data class VoiceCommandResult(
        val status: VoiceCommandStatus,
        val transcription: String? = null,
        val confidence: Float = 0f,
        val audioFile: File? = null,
        val language: String? = null,
        val durationMs: Long = 0L,
        val errorMessage: String? = null,
        val timestamp: Long = System.currentTimeMillis()
    ) {
        val isValid: Boolean
            get() = status == VoiceCommandStatus.COMPLETED && !transcription.isNullOrBlank()

        fun toMap(): Map<String, Any> {
            return mapOf(
                "status" to status.name,
                "transcription" to (transcription ?: ""),
                "confidence" to confidence,
                "language" to (language ?: ""),
                "durationMs" to durationMs,
                "timestamp" to timestamp,
                "isValid" to isValid,
                "errorMessage" to (errorMessage ?: "")
            )
        }
    }

    /**
     * Processing error types.
     */
    sealed class AudioProcessingError : Exception() {
        data class RecordingError(override val message: String? = null, override val cause: Throwable? = null) : AudioProcessingError()
        data class TranscriptionError(override val message: String? = null, override val cause: Throwable? = null) : AudioProcessingError()
        data class CancellationError(override val message: String? = null, override val cause: Throwable? = null) : AudioProcessingError()
        data class ProcessingError(override val message: String? = null, override val cause: Throwable? = null) : AudioProcessingError()
    }
}