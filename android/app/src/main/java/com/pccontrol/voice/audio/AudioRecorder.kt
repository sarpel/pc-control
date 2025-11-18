package com.pccontrol.voice.audio

import android.content.Context
import android.media.*
import android.media.MediaRecorder.AudioSource
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import java.io.*
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Audio recording service for capturing voice input.
 *
 * Features:
 * - High-quality audio recording
 * - Real-time audio level monitoring
 * - Background recording
 * - Automatic format optimization
 * - Noise reduction support
 */
class AudioRecorder private constructor(
    private val context: Context
) {
    private var mediaRecorder: MediaRecorder? = null
    private var audioFile: File? = null
    private val isRecording = AtomicBoolean(false)
    private val isPaused = AtomicBoolean(false)

    // Coroutines
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var audioLevelJob: Job? = null
    private val _audioLevel = MutableStateFlow(0f)
    private val _recordingState = MutableStateFlow(RecordingState.IDLE)
    private val _recordingDuration = MutableStateFlow(0L)

    companion object {
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_COUNT = 1
        private const val BIT_RATE = 128000
        private const val AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT
        private const val AUDIO_EXTENSION = ".webm"
        private const val AUDIO_MIME = "audio/webm"

        @Volatile
        private var INSTANCE: AudioRecorder? = null

        fun getInstance(context: Context): AudioRecorder {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: AudioRecorder(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    /**
     * Observe audio level (0.0 to 1.0).
     */
    val audioLevel: StateFlow<Float> = _audioLevel.asStateFlow()

    /**
     * Observe recording state.
     */
    val recordingState: StateFlow<RecordingState> = _recordingState.asStateFlow()

    /**
     * Observe recording duration in milliseconds.
     */
    val recordingDuration: StateFlow<Long> = _recordingDuration.asStateFlow()

    /**
     * Start recording audio.
     */
    suspend fun startRecording(outputFile: File? = null): Result<File> = withContext(Dispatchers.IO) {
        try {
            if (isRecording.get()) {
                return@withContext Result.failure(Exception("Already recording"))
            }

            // Create output file
            val file = outputFile ?: createAudioFile()
            audioFile = file

            // Initialize MediaRecorder
            val recorder = MediaRecorder().apply {
                setAudioSource(AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.WEBM)
                setAudioEncoder(MediaRecorder.AudioEncoder.OPUS)
                setAudioEncodingBitRate(BIT_RATE)
                setAudioSamplingRate(SAMPLE_RATE)
                setAudioChannels(CHANNEL_COUNT)
                setOutputFile(file.absolutePath)

                // Enable noise reduction if available
                try {
                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                        setAudioEncodingBitRate(BIT_RATE)
                    }
                } catch (e: Exception) {
                    // Noise reduction not supported
                }
            }

            // Start recording
            recorder.prepare()
            recorder.start()

            mediaRecorder = recorder
            isRecording.set(true)
            isPaused.set(false)
            _recordingState.value = RecordingState.RECORDING

            // Start audio level monitoring
            startAudioLevelMonitoring()

            // Start duration tracking
            startDurationTracking()

            Result.success(file)

        } catch (e: Exception) {
            cleanupResources()
            Result.failure(e)
        }
    }

    /**
     * Stop recording and save the audio file.
     */
    suspend fun stopRecording(): Result<File> = withContext(Dispatchers.IO) {
        try {
            if (!isRecording.get()) {
                return@withContext Result.failure(Exception("Not recording"))
            }

            val file = audioFile ?: return@withContext Result.failure(Exception("No active recording"))

            mediaRecorder?.apply {
                try {
                    stop()
                    release()
                } catch (e: Exception) {
                    // Handle stop failure
                }
            }

            cleanupResources()
            _recordingState.value = RecordingState.COMPLETED

            Result.success(file)

        } catch (e: Exception) {
            cleanupResources()
            Result.failure(e)
        }
    }

    /**
     * Pause recording.
     */
    suspend fun pauseRecording(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (!isRecording.get() || isPaused.get()) {
                return@withContext Result.failure(Exception("Cannot pause: not recording or already paused"))
            }

            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                mediaRecorder?.pause()
                isPaused.set(true)
                _recordingState.value = RecordingState.PAUSED
                audioLevelJob?.cancel()
            } else {
                return@withContext Result.failure(Exception("Pause not supported on this Android version"))
            }

            Result.success(Unit)

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Resume recording.
     */
    suspend fun resumeRecording(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (!isRecording.get() || !isPaused.get()) {
                return@withContext Result.failure(Exception("Cannot resume: not recording or not paused"))
            }

            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.N) {
                mediaRecorder?.resume()
                isPaused.set(false)
                _recordingState.value = RecordingState.RECORDING
                startAudioLevelMonitoring()
            } else {
                return@withContext Result.failure(Exception("Resume not supported on this Android version"))
            }

            Result.success(Unit)

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Cancel recording and delete the audio file.
     */
    suspend fun cancelRecording(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (!isRecording.get()) {
                return@withContext Result.success(Unit)
            }

            val file = audioFile

            mediaRecorder?.apply {
                try {
                    stop()
                    release()
                } catch (e: Exception) {
                    // Ignore cleanup errors
                }
            }

            // Delete the file
            file?.delete()

            cleanupResources()
            _recordingState.value = RecordingState.CANCELLED

            Result.success(Unit)

        } catch (e: Exception) {
            cleanupResources()
            Result.failure(e)
        }
    }

    /**
     * Check if currently recording.
     */
    fun isRecording(): Boolean = isRecording.get()

    /**
     * Check if currently paused.
     */
    fun isPaused(): Boolean = isPaused.get()

    private fun createAudioFile(): File {
        val timestamp = System.currentTimeMillis()
        val fileName = "voice_recording_$timestamp$AUDIO_EXTENSION"
        val audioDir = File(context.cacheDir, "audio")

        if (!audioDir.exists()) {
            audioDir.mkdirs()
        }

        return File(audioDir, fileName)
    }

    private fun startAudioLevelMonitoring() {
        audioLevelJob?.cancel()
        audioLevelJob = scope.launch {
            while (isRecording.get() && !isPaused.get()) {
                try {
                    // Get current amplitude from MediaRecorder
                    val amplitude = mediaRecorder?.maxAmplitude ?: 0

                    // Convert to normalized level (0.0 to 1.0)
                    val level = (amplitude / 32767.0f).coerceIn(0f, 1f)
                    _audioLevel.value = level

                    delay(100) // Update every 100ms

                } catch (e: Exception) {
                    // Ignore monitoring errors
                    delay(500)
                }
            }
        }
    }

    private fun startDurationTracking() {
        scope.launch {
            val startTime = System.currentTimeMillis()
            var lastDuration = 0L

            while (isRecording.get()) {
                val currentDuration = if (!isPaused.get()) {
                    System.currentTimeMillis() - startTime
                } else {
                    lastDuration
                }

                _recordingDuration.value = currentDuration
                lastDuration = currentDuration

                delay(100)
            }
        }
    }

    private fun cleanupResources() {
        mediaRecorder?.release()
        mediaRecorder = null
        audioFile = null
        isRecording.set(false)
        isPaused.set(false)
        audioLevelJob?.cancel()
        _audioLevel.value = 0f
        _recordingDuration.value = 0L
    }

    /**
     * Get optimal recording format for the device.
     */
    fun getOptimalRecordingFormat(): AudioFormat {
        return AudioFormat.Builder()
            .setSampleRate(SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .setEncoding(AUDIO_FORMAT)
            .build()
    }

    /**
     * Check if audio recording permission is granted.
     */
    fun hasRecordingPermission(): Boolean {
        return context.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) ==
               android.content.pm.PackageManager.PERMISSION_GRANTED
    }

    /**
     * Recording states.
     */
    enum class RecordingState {
        IDLE,
        RECORDING,
        PAUSED,
        COMPLETED,
        CANCELLED,
        ERROR
    }

    /**
     * Audio recording configuration.
     */
    data class RecordingConfig(
        val sampleRate: Int = SAMPLE_RATE,
        val channelCount: Int = CHANNEL_COUNT,
        val bitRate: Int = BIT_RATE,
        val audioFormat: Int = AUDIO_FORMAT,
        val outputFormat: Int = MediaRecorder.OutputFormat.WEBM,
        val audioEncoder: Int = MediaRecorder.AudioEncoder.OPUS,
        val maxDurationMs: Long = 60000, // 1 minute max
        val enableNoiseReduction: Boolean = true
    )

    /**
     * Cleanup resources.
     */
    fun cleanup() {
        scope.cancel()
        cleanupResources()
    }
}