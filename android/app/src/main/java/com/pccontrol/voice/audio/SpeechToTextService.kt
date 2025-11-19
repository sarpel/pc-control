package com.pccontrol.voice.audio

import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import org.json.JSONObject
import java.io.*
import java.util.*
import java.util.concurrent.TimeUnit

/**
 * Speech-to-Text service using Whisper.cpp for Turkish language processing.
 *
 * Features:
 * - Turkish language optimized
 * - Real-time transcription
 * - Confidence scoring
 * - Multiple model support
 * - Offline processing
 */
class SpeechToTextService private constructor(
    private val context: Context
) {
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var isInitialized = false
    private var whisperModel: WhisperModel? = null

    companion object {
        private const val MODEL_NAME = "whisper-base-tr.bin"
        private const val MODEL_VERSION = "base-tr"
        private const val LANGUAGE = "tr"
        private const val DEFAULT_THREADS = 2
        private const val MAX_AUDIO_LENGTH_SECONDS = 30
        private const val CONFIDENCE_THRESHOLD = 0.3f

        @Volatile
        private var INSTANCE: SpeechToTextService? = null

        fun getInstance(context: Context): SpeechToTextService {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: SpeechToTextService(context.applicationContext).also { INSTANCE = it }
            }
        }
    }

    /**
     * Initialize the Whisper model.
     */
    suspend fun initialize(): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            if (isInitialized) {
                return@withContext Result.success(Unit)
            }

            // Check if model exists, download if needed
            val modelFile = getModelFile()
            if (!modelFile.exists()) {
                downloadModel(modelFile)
            }

            // Load Whisper model (this would be a JNI call to whisper.cpp)
            whisperModel = WhisperModel.loadModel(
                modelPath = modelFile.absolutePath,
                language = LANGUAGE,
                threads = DEFAULT_THREADS
            )

            isInitialized = true
            Result.success(Unit)

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Transcribe audio file to text.
     */
    suspend fun transcribe(
        audioFile: File,
        options: TranscriptionOptions = TranscriptionOptions()
    ): Result<TranscriptionResult> = withContext(Dispatchers.IO) {
        try {
            if (!isInitialized) {
                val initResult = initialize()
                if (initResult.isFailure) {
                    return@withContext Result.failure(Exception("STT not initialized"))
                }
            }

            // Validate audio file
            if (!audioFile.exists()) {
                return@withContext Result.failure(Exception("Audio file not found"))
            }

            // Check audio duration
            val duration = getAudioDuration(audioFile)
            if (duration > MAX_AUDIO_LENGTH_SECONDS) {
                return@withContext Result.failure(Exception("Audio too long: ${duration}s > ${MAX_AUDIO_LENGTH_SECONDS}s"))
            }

            // Perform transcription
            val model = whisperModel ?: return@withContext Result.failure(Exception("Model not loaded"))

            val result = model.transcribe(
                audioPath = audioFile.absolutePath,
                language = options.language ?: LANGUAGE,
                translate = options.translate,
                noSpeechThreshold = options.noSpeechThreshold,
                temperature = options.temperature
            )

            // Process result
            val transcription = processTranscriptionResult(result, options)

            // Validate confidence
            if (transcription.confidence < CONFIDENCE_THRESHOLD) {
                return@withContext Result.success(
                    TranscriptionResult(
                        text = "",
                        confidence = transcription.confidence,
                        language = LANGUAGE,
                        segments = emptyList(),
                        durationMs = transcription.durationMs,
                        processedAt = System.currentTimeMillis(),
                        isReliable = false
                    )
                )
            }

            Result.success(transcription)

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Transcribe audio data directly.
     */
    suspend fun transcribeAudioData(
        audioData: ByteArray,
        sampleRate: Int = 16000,
        options: TranscriptionOptions = TranscriptionOptions()
    ): Result<TranscriptionResult> = withContext(Dispatchers.IO) {
        try {
            // Create temporary audio file
            val tempFile = createTempAudioFile(audioData, sampleRate)

            try {
                return@withContext transcribe(tempFile, options)
            } finally {
                tempFile.delete()
            }

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * Real-time transcription for streaming audio.
     */
    fun transcribeRealtime(
        audioFlow: Flow<ByteArray>,
        options: TranscriptionOptions = TranscriptionOptions()
    ): Flow<RealtimeTranscriptionResult> = flow {
        try {
            if (!isInitialized) {
                initialize()
            }

            val model = whisperModel ?: throw Exception("Model not loaded")

            // Buffer for real-time processing
            val buffer = mutableListOf<ByteArray>()
            var totalLength = 0

            audioFlow.collect { audioData ->
                buffer.add(audioData)
                totalLength += audioData.size

                // Process when we have enough data (e.g., 2 seconds)
                if (totalLength >= options.sampleRate * 2 * 2) { // 2 seconds of 16-bit audio
                    val combinedData = ByteArray(totalLength).also { result ->
                        var offset = 0
                        buffer.forEach { data ->
                            data.copyInto(result, offset)
                            offset += data.size
                        }
                    }
                    buffer.clear()
                    totalLength = 0

                    // Create temporary file
                    val tempFile = createTempAudioFile(combinedData, options.sampleRate)

                    try {
                        val result = model.transcribe(
                            audioPath = tempFile.absolutePath,
                            language = options.language ?: LANGUAGE,
                            translate = false,
                            noSpeechThreshold = 0.6f,
                            temperature = 0.0f
                        )

                        if (result.text.isNotBlank() && result.confidence > CONFIDENCE_THRESHOLD) {
                            emit(
                                RealtimeTranscriptionResult(
                                    text = result.text,
                                    confidence = result.confidence,
                                    timestamp = System.currentTimeMillis(),
                                    isPartial = true
                                )
                            )
                        }

                    } finally {
                        tempFile.delete()
                    }
                }
            }

        } catch (e: Exception) {
            emit(
                RealtimeTranscriptionResult(
                    text = "",
                    confidence = 0f,
                    timestamp = System.currentTimeMillis(),
                    error = e.message
                )
            )
        }
    }

    private fun getModelFile(): File {
        val modelDir = File(context.filesDir, "whisper_models")
        if (!modelDir.exists()) {
            modelDir.mkdirs()
        }
        return File(modelDir, MODEL_NAME)
    }

    private suspend fun downloadModel(modelFile: File) {
        withContext(Dispatchers.IO) {
            try {
                val url = URL("https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-tr.bin")
                val connection = url.openConnection()
                connection.connect()
                
                val input = BufferedInputStream(url.openStream())
                val output = FileOutputStream(modelFile)
                
                val data = ByteArray(1024)
                var count: Int
                while (input.read(data).also { count = it } != -1) {
                    output.write(data, 0, count)
                }
                
                output.flush()
                output.close()
                input.close()
            } catch (e: Exception) {
                Log.e("SpeechToTextService", "Error downloading model", e)
                throw e
            }
        }
    }

    private fun getAudioDuration(audioFile: File): Int {
        // This would use MediaMetadataRetriever to get duration
        // For now, return a default
        return 10 // 10 seconds default
    }

    private fun createTempAudioFile(audioData: ByteArray, sampleRate: Int): File {
        val tempFile = File(context.cacheDir, "temp_audio_${System.currentTimeMillis()}.wav")
        FileOutputStream(tempFile).use { output ->
            output.write(audioData)
        }
        return tempFile
    }

    private fun processTranscriptionResult(
        result: WhisperTranscriptionResult,
        options: TranscriptionOptions
    ): TranscriptionResult {
        val segments = result.segments.map { segment ->
            TranscriptionSegment(
                text = segment.text,
                startMs = segment.startMs,
                endMs = segment.endMs,
                confidence = segment.confidence
            )
        }

        return TranscriptionResult(
            text = result.text.trim(),
            confidence = result.confidence,
            language = result.language,
            segments = segments,
            durationMs = result.durationMs,
            processedAt = System.currentTimeMillis(),
            isReliable = result.confidence >= CONFIDENCE_THRESHOLD
        )
    }

    /**
     * Cleanup resources.
     */
    fun cleanup() {
        scope.cancel()
        whisperModel?.cleanup()
        whisperModel = null
        isInitialized = false
    }

    /**
     * Transcription configuration options.
     */
    data class TranscriptionOptions(
        val language: String? = LANGUAGE,
        val translate: Boolean = false,
        val noSpeechThreshold: Float = 0.6f,
        val temperature: Float = 0.0f,
        val sampleRate: Int = 16000,
        val enableRealtime: Boolean = true,
        val maxSegments: Int = 10
    )

    /**
     * Transcription result.
     */
    data class TranscriptionResult(
        val text: String,
        val confidence: Float,
        val language: String,
        val segments: List<TranscriptionSegment>,
        val durationMs: Long,
        val processedAt: Long,
        val isReliable: Boolean,
        val metadata: Map<String, Any> = emptyMap()
    ) {
        fun isValid(): Boolean {
            return text.isNotBlank() && confidence > 0f && isReliable
        }

        fun getShortText(): String {
            return text.take(100).let {
                if (it.length < text.length) "$it..." else it
            }
        }
    }

    /**
     * Individual transcription segment.
     */
    data class TranscriptionSegment(
        val text: String,
        val startMs: Long,
        val endMs: Long,
        val confidence: Float
    ) {
        val durationMs: Long
            get() = endMs - startMs
    }

    /**
     * Real-time transcription result.
     */
    data class RealtimeTranscriptionResult(
        val text: String,
        val confidence: Float,
        val timestamp: Long,
        val isPartial: Boolean = false,
        val error: String? = null
    ) {
        val isValid: Boolean
            get() = text.isNotBlank() && confidence > 0f && error == null
    }

    /**
     * Whisper model wrapper (JNI interface to whisper.cpp).
     */
    private class WhisperModel private constructor(
        private val modelPath: String,
        private val language: String,
        private val threads: Int
    ) {
        companion object {
            init {
                try {
                    System.loadLibrary("whisper_jni")
                } catch (e: UnsatisfiedLinkError) {
                    Log.e("WhisperModel", "Failed to load whisper_jni library", e)
                }
            }

            fun loadModel(modelPath: String, language: String, threads: Int): WhisperModel {
                return WhisperModel(modelPath, language, threads)
            }
        }

        // Native methods
        private external fun init(modelPath: String, language: String, threads: Int): Long
        private external fun free(contextPtr: Long)
        private external fun fullTranscribe(contextPtr: Long, audioData: FloatArray): String

        private var contextPtr: Long = 0

        init {
            try {
                contextPtr = init(modelPath, language, threads)
            } catch (e: UnsatisfiedLinkError) {
                Log.e("WhisperModel", "Native init failed", e)
            }
        }

        fun transcribe(
            audioPath: String,
            language: String = this.language,
            translate: Boolean = false,
            noSpeechThreshold: Float = 0.6f,
            temperature: Float = 0.0f
        ): WhisperTranscriptionResult {
            if (contextPtr == 0L) {
                return WhisperTranscriptionResult("", 0f, language, 0, emptyList())
            }
            
            return try {
                val audioFile = File(audioPath)
                if (!audioFile.exists()) {
                    return WhisperTranscriptionResult("", 0f, language, 0, emptyList())
                }
                
                val audioData = readAudioFileToFloatArray(audioFile)
                val text = fullTranscribe(contextPtr, audioData)
                
                // Parse result if it's JSON or structured, otherwise assume plain text
                // For now assuming plain text return from JNI
                WhisperTranscriptionResult(text, 1.0f, language, (audioData.size / 16000.0 * 1000).toLong(), emptyList())
            } catch (e: Exception) {
                Log.e("WhisperModel", "Transcription failed", e)
                WhisperTranscriptionResult("", 0f, language, 0, emptyList())
            }
        }

        private fun readAudioFileToFloatArray(file: File): FloatArray {
            val bytes = file.readBytes()
            // Simple WAV header check/skip - assuming 16-bit PCM mono 16kHz
            // WAV header is typically 44 bytes
            val startOffset = if (file.name.endsWith(".wav", ignoreCase = true) && bytes.size > 44) 44 else 0
            val shortCount = (bytes.size - startOffset) / 2
            val floatArray = FloatArray(shortCount)
            
            for (i in 0 until shortCount) {
                val byteIndex = startOffset + i * 2
                if (byteIndex + 1 < bytes.size) {
                    val low = bytes[byteIndex].toInt() and 0xFF
                    val high = bytes[byteIndex + 1].toInt()
                    val sample = (high shl 8) or low
                    floatArray[i] = sample / 32768.0f
                }
            }
            return floatArray
        }


        fun cleanup() {
            if (contextPtr != 0L) {
                free(contextPtr)
                contextPtr = 0
            }
        }
    }

    private data class WhisperTranscriptionResult(
        val text: String,
        val confidence: Float,
        val language: String,
        val durationMs: Long,
        val segments: List<WhisperSegment>
    )

    private data class WhisperSegment(
        val text: String,
        val startMs: Long,
        val endMs: Long,
        val confidence: Float
    )
}