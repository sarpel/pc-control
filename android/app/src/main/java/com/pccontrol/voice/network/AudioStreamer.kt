package com.pccontrol.voice.network

import android.media.MediaCodec
import android.media.MediaFormat
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.withContext
import java.nio.ByteBuffer
import java.util.UUID

/**
 * Audio streaming utility for encoding and streaming audio data to PC.
 *
 * This class handles:
 * - Opus encoding of PCM audio data
 * - Chunking audio for network transmission
 * - Creating audio chunk messages for WebSocket
 */
class AudioStreamer {

    companion object {
        private const val TAG = "AudioStreamer"
        private const val SAMPLE_RATE = 16000
        private const val CHANNEL_COUNT = 1 // Mono
        private const val BIT_RATE = 24000 // 24kbps VBR
        private const val CHUNK_SIZE = 4096 // Bytes per chunk
        private const val MIME_TYPE = "audio/opus"
    }

    private var encoder: MediaCodec? = null
    private var isInitialized = false

    /**
     * Initialize the Opus encoder.
     *
     * @throws IllegalStateException if encoder initialization fails
     */
    fun initialize() {
        try {
            val format = MediaFormat.createAudioFormat(MIME_TYPE, SAMPLE_RATE, CHANNEL_COUNT).apply {
                setInteger(MediaFormat.KEY_BIT_RATE, BIT_RATE)
                setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, CHUNK_SIZE)
            }

            encoder = MediaCodec.createEncoderByType(MIME_TYPE).apply {
                configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                start()
            }

            isInitialized = true
            Log.d(TAG, "Opus encoder initialized successfully")

        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize encoder", e)
            throw IllegalStateException("Failed to initialize Opus encoder", e)
        }
    }

    /**
     * Stream audio data with encoding.
     *
     * @param commandId The command ID associated with this audio stream
     * @param audioData Raw PCM audio data (16kHz, mono, 16-bit)
     * @return Flow of encoded audio chunks ready for transmission
     */
    fun streamAudio(commandId: UUID, audioData: ByteArray): Flow<AudioChunk> = flow {
        if (!isInitialized) {
            throw IllegalStateException("AudioStreamer not initialized. Call initialize() first.")
        }

        try {
            val chunks = encodeAudio(audioData, commandId)
            var chunkIndex = 0

            chunks.forEach { encodedData ->
                emit(AudioChunk(
                    commandId = commandId.toString(),
                    chunkIndex = chunkIndex++,
                    audioData = encodedData,
                    isFinal = false,
                    encoding = "opus",
                    sampleRate = SAMPLE_RATE
                ))
            }

            // Emit final chunk marker
            emit(AudioChunk(
                commandId = commandId.toString(),
                chunkIndex = chunkIndex,
                audioData = byteArrayOf(),
                isFinal = true,
                encoding = "opus",
                sampleRate = SAMPLE_RATE
            ))

        } catch (e: Exception) {
            Log.e(TAG, "Error streaming audio", e)
            throw e
        }
    }

    /**
     * Encode raw PCM audio data to Opus format.
     *
     * @param pcmData Raw PCM audio data
     * @param commandId Command ID for logging
     * @return List of encoded audio chunks
     */
    private suspend fun encodeAudio(pcmData: ByteArray, commandId: UUID): List<ByteArray> = withContext(Dispatchers.Default) {
        val encodedChunks = mutableListOf<ByteArray>()
        val codec = encoder ?: throw IllegalStateException("Encoder not initialized")

        try {
            var inputIndex = 0
            var outputEos = false

            // Feed input data
            while (inputIndex < pcmData.size && !outputEos) {
                val inputBufferId = codec.dequeueInputBuffer(10000)
                if (inputBufferId >= 0) {
                    val inputBuffer = codec.getInputBuffer(inputBufferId)
                    inputBuffer?.clear()

                    val remaining = pcmData.size - inputIndex
                    val sampleSize = minOf(CHUNK_SIZE, remaining)

                    inputBuffer?.put(pcmData, inputIndex, sampleSize)
                    inputIndex += sampleSize

                    val presentationTimeUs = (inputIndex / (SAMPLE_RATE * 2)) * 1_000_000L
                    val flags = if (inputIndex >= pcmData.size) MediaCodec.BUFFER_FLAG_END_OF_STREAM else 0

                    codec.queueInputBuffer(
                        inputBufferId,
                        0,
                        sampleSize,
                        presentationTimeUs,
                        flags
                    )

                    if (flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        outputEos = true
                    }
                }

                // Get encoded output
                val bufferInfo = MediaCodec.BufferInfo()
                var outputBufferId = codec.dequeueOutputBuffer(bufferInfo, 0)

                while (outputBufferId >= 0) {
                    val outputBuffer = codec.getOutputBuffer(outputBufferId)

                    if (outputBuffer != null && bufferInfo.size > 0) {
                        val encodedData = ByteArray(bufferInfo.size)
                        outputBuffer.position(bufferInfo.offset)
                        outputBuffer.get(encodedData, 0, bufferInfo.size)
                        encodedChunks.add(encodedData)
                    }

                    codec.releaseOutputBuffer(outputBufferId, false)

                    if (bufferInfo.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                        break
                    }

                    outputBufferId = codec.dequeueOutputBuffer(bufferInfo, 0)
                }
            }

            Log.d(TAG, "Encoded ${encodedChunks.size} audio chunks for command $commandId")

        } catch (e: Exception) {
            Log.e(TAG, "Error during audio encoding", e)
            throw e
        }

        encodedChunks
    }

    /**
     * Release encoder resources.
     */
    fun release() {
        try {
            encoder?.stop()
            encoder?.release()
            encoder = null
            isInitialized = false
            Log.d(TAG, "Opus encoder released")
        } catch (e: Exception) {
            Log.e(TAG, "Error releasing encoder", e)
        }
    }

    /**
     * Data class representing an audio chunk ready for transmission.
     */
    data class AudioChunk(
        val commandId: String,
        val chunkIndex: Int,
        val audioData: ByteArray,
        val isFinal: Boolean,
        val encoding: String = "opus",
        val sampleRate: Int = 16000
    ) {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (javaClass != other?.javaClass) return false

            other as AudioChunk

            if (commandId != other.commandId) return false
            if (chunkIndex != other.chunkIndex) return false
            if (!audioData.contentEquals(other.audioData)) return false
            if (isFinal != other.isFinal) return false

            return true
        }

        override fun hashCode(): Int {
            var result = commandId.hashCode()
            result = 31 * result + chunkIndex
            result = 31 * result + audioData.contentHashCode()
            result = 31 * result + isFinal.hashCode()
            return result
        }
    }
}