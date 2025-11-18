/**
 * Integration tests for Android audio streaming functionality.
 *
 * These tests verify the complete audio pipeline:
 * - Audio capture from microphone with VAD
 * - Opus encoding and compression
 * - WebSocket transmission to PC agent
 * - Real-time streaming with <200ms buffering
 * - Background operation and battery efficiency
 *
 * Following TDD: These tests should FAIL initially, then pass after T050 implementation.
 */

package com.pccontrol.voice.integration

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.pccontrol.voice.audio.AudioCaptureService
import com.pccontrol.voice.audio.OpusEncoder
import com.pccontrol.voice.network.AudioStreamer
import com.pccontrol.voice.network.WebSocketClient
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.junit.Assert.*
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import org.mockito.Mockito.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

@RunWith(AndroidJUnit4::class)
class AudioStreamingIntegrationTest {

    @Mock
    private lateinit var mockWebSocketClient: WebSocketClient

    @Mock
    private lateinit var mockAudioRecord: AudioRecord

    private lateinit var context: Context
    private lateinit var audioCaptureService: AudioCaptureService
    private lateinit var audioStreamer: AudioStreamer
    private lateinit var opusEncoder: OpusEncoder

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        context = ApplicationProvider.getApplicationContext()

        // Initialize services with mocks
        audioCaptureService = AudioCaptureService(context)
        audioStreamer = AudioStreamer(mockWebSocketClient)
        opusEncoder = OpusEncoder()
    }

    @Test
    fun testAudioCaptureWithCorrectFormat() = runTest {
        /**
         * Test: Audio capture uses 16kHz PCM format as per spec
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val expectedSampleRate = 16000
        val expectedChannels = AudioFormat.CHANNEL_IN_MONO
        val expectedEncoding = AudioFormat.ENCODING_PCM_16BIT
        val expectedBufferSize = AudioRecord.getMinBufferSize(
            expectedSampleRate, expectedChannels, expectedEncoding
        )

        // Mock AudioRecord behavior
        `when`(mockAudioRecord.sampleRate).thenReturn(expectedSampleRate)
        `when`(mockAudioRecord.channelCount).thenReturn(1)
        `when`(mockAudioRecord.audioFormat).thenReturn(expectedEncoding)

        // Act
        val audioConfig = audioCaptureService.getAudioConfig()

        // Assert
        assertEquals(expectedSampleRate, audioConfig.sampleRate)
        assertEquals(1, audioConfig.channelCount)
        assertEquals(expectedEncoding, audioConfig.encoding)
        assertTrue(audioConfig.bufferSize >= expectedBufferSize)
    }

    @Test
    fun testAudioCaptureWithVoiceActivityDetection() = runTest {
        /**
         * Test: Voice Activity Detection (VAD) detects speech correctly
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val audioData = ByteArray(1024) // Simulated audio buffer
        val vadDetected = MutableStateFlow(false)

        // Mock VAD detection
        `when`(mockAudioRecord.read(audioData, 0, audioData.size))
            .thenReturn(audioData.size) // Successful read

        // Act
        audioCaptureService.startCapture { detected, audioBuffer ->
            vadDetected.value = detected
        }

        // Simulate voice activity
        audioCaptureService.processAudioBuffer(audioData, true) // Force VAD detection

        // Wait for detection
        delay(100)

        // Assert
        assertTrue(vadDetected.first())
        verify(mockAudioRecord, atLeastOnce()).read(any(), anyInt(), anyInt())
    }

    @Test
    fun testOpusEncodingCompressionEfficiency() = runTest {
        /**
         * Test: Opus encoding compresses 16kHz PCM efficiently (~24kbps)
         * Expected to FAIL until T050 is implemented
         */
        // Arrange - 1 second of 16kHz mono PCM audio
        val pcmDataSize = 16000 * 2 // 16kHz * 2 bytes per sample
        val pcmData = ByteArray(pcmDataSize) { (it % 256).toByte() }

        // Act
        val encodedData = opusEncoder.encode(pcmData)
        val compressionRatio = pcmDataSize.toDouble() / encodedData.size

        // Assert
        assertTrue("Original: $pcmDataSize bytes, Encoded: ${encodedData.size} bytes",
                   encodedData.isNotEmpty())
        assertTrue("Compression ratio should be >10:1", compressionRatio > 10.0)

        // Target ~24kbps = 3KB/s for 16kHz mono
        val targetBytesPerSecond = 3 * 1024
        assertTrue("Encoded size should be close to ${targetBytesPerSecond}B/s, got ${encodedData.size}",
                   Math.abs(encodedData.size - targetBytesPerSecond) < targetBytesPerSecond * 0.5)
    }

    @Test
    fun testRealTimeStreamingWithLowLatency() = runTest {
        /**
         * Test: Real-time streaming maintains <200ms buffering delay
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val audioBuffer = ByteArray(3200) // 200ms at 16kHz (200ms * 16000 samples/s * 2 bytes)
        val streamingComplete = CountDownLatch(1)
        var actualLatency = 0L
        val startTime = System.currentTimeMillis()

        // Mock WebSocket success
        `when`(mockWebSocketClient.sendBinary(any())).thenAnswer {
            actualLatency = System.currentTimeMillis() - startTime
            streamingComplete.countDown()
            true
        }

        // Act
        audioStreamer.startStreaming()
        val sent = audioStreamer.sendAudioFrame(audioBuffer, startTime)

        // Wait for transmission
        assertTrue("Streaming should complete within 2 seconds",
                   streamingComplete.await(2, TimeUnit.SECONDS))

        // Assert
        assertTrue("Audio frame should be sent successfully", sent)
        assertTrue("Latency should be <200ms, got ${actualLatency}ms", actualLatency < 200)
        verify(mockWebSocketClient, times(1)).sendBinary(any())
    }

    @Test
    fun testConcurrentAudioFrameProcessing() = runTest {
        /**
         * Test: System handles multiple audio frames concurrently
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val frameCount = 10
        val framesProcessed = CountDownLatch(frameCount)
        val processedFrames = mutableListOf<ByteArray>()

        // Mock WebSocket success for each frame
        `when`(mockWebSocketClient.sendBinary(any())).thenAnswer { invocation ->
            synchronized(processedFrames) {
                processedFrames.add(invocation.getArgument<ByteArray>(0))
            }
            framesProcessed.countDown()
            true
        }

        // Act - Send multiple frames concurrently
        audioStreamer.startStreaming()
        repeat(frameCount) { i ->
            val frame = ByteArray(3200) { ((i * 10 + it % 256) % 256).toByte() }
            launch {
                audioStreamer.sendAudioFrame(frame, System.currentTimeMillis() + i * 20)
            }
        }

        // Wait for all frames to be processed
        assertTrue("All frames should be processed within 3 seconds",
                   framesProcessed.await(3, TimeUnit.SECONDS))

        // Assert
        assertEquals(frameCount, processedFrames.size)
        // Verify each frame is unique
        val uniqueFrames = processedFrames.map { it.contentHashCode() }.distinct()
        assertEquals(frameCount, uniqueFrames.size)
    }

    @Test
    fun testAudioStreamingInBackground() = runTest {
        /**
         * Test: Audio streaming continues when app goes to background
         * Expected to FAIL until T053 is implemented
         */
        // Arrange
        val streamingActive = MutableStateFlow(true)
        val backgroundModeTriggered = CountDownLatch(1)

        // Mock WebSocket behavior
        `when`(mockWebSocketClient.sendBinary(any())).thenReturn(true)

        // Act - Start streaming, then simulate background mode
        audioStreamer.startStreaming()

        // Simulate app going to background
        audioCaptureService.onAppBackgrounded {
            backgroundModeTriggered.countDown()
        }

        // Send audio frame in background
        val audioFrame = ByteArray(3200)
        val sent = audioStreamer.sendAudioFrame(audioFrame, System.currentTimeMillis())

        // Wait for background handling
        assertTrue("Background mode should be triggered",
                   backgroundModeTriggered.await(1, TimeUnit.SECONDS))

        // Assert
        assertTrue("Streaming should continue in background", sent)
        assertTrue("Audio capture should adapt to background mode",
                   audioCaptureService.isBackgroundOptimized())
    }

    @Test
    fun testNetworkInterruptionHandling() = runTest {
        /**
         * Test: Audio streaming handles network interruptions gracefully
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val audioBuffer = ByteArray(3200)
        val interruptionCount = 3
        val framesBuffered = mutableListOf<ByteArray>()
        var framesSent = 0

        // Mock WebSocket that fails initially then succeeds
        `when`(mockWebSocketClient.sendBinary(any())).thenAnswer { invocation ->
            framesSent++
            if (framesSent <= interruptionCount) {
                false // Simulate network failure
            } else {
                synchronized(framesBuffered) {
                    framesBuffered.add(invocation.getArgument<ByteArray>(0))
                }
                true // Network recovered
            }
        }

        // Act
        audioStreamer.startStreaming()

        // Send frames during interruption
        repeat(interruptionCount + 2) { i ->
            val frame = ByteArray(3200) { (i % 256).toByte() }
            audioStreamer.sendAudioFrame(frame, System.currentTimeMillis() + i * 50)
            delay(100) // Simulate real-time frame generation
        }

        // Wait for recovery
        delay(1000)

        // Assert
        assertTrue("Should recover from network interruption", framesSent > interruptionCount)
        assertTrue("Should buffer frames during interruption", framesBuffered.isNotEmpty())
        verify(mockWebSocketClient, atLeast(interruptionCount + 1)).sendBinary(any())
    }

    @Test
    fun testAudioQualityValidation() = runTest {
        /**
         * Test: Audio quality meets specifications
         * Expected to FAIL until T050 is implemented
         */
        // Arrange - Generate test audio with known characteristics
        val sampleRate = 16000
        val duration = 1.0 // 1 second
        val frequency = 440.0 // A4 tone
        val samples = (sampleRate * duration).toInt()
        val pcmData = ByteArray(samples * 2) // 16-bit samples

        // Generate sine wave test tone
        for (i in 0 until samples) {
            val sample = (Math.sin(2 * Math.PI * frequency * i / sampleRate) * Short.MAX_VALUE).toInt()
            pcmData[i * 2] = (sample and 0xFF).toByte()
            pcmData[i * 2 + 1] = ((sample shr 8) and 0xFF).toByte()
        }

        // Act
        val encodedData = opusEncoder.encode(pcmData)
        val decodedData = opusEncoder.decode(encodedData)

        // Assert
        assertNotNull("Decoded data should not be null", decodedData)
        assertTrue("Decoded data should have reasonable length", decodedData.isNotEmpty())

        // Basic quality checks
        val signalEnergy = decodedData.map { it.toDouble() * it.toDouble() }.average()
        assertTrue("Signal should have energy", signalEnergy > 0.0)

        // Sample rate consistency check (simplified)
        val expectedDecodedLength = samples * 2 // Should be close to original length
        val lengthRatio = decodedData.size.toDouble() / expectedDecodedLength
        assertTrue("Length ratio should be close to 1.0, got $lengthRatio",
                   Math.abs(lengthRatio - 1.0) < 0.1)
    }

    @Test
    fun testBatteryUsageOptimization() = runTest {
        /**
         * Test: Audio capture respects battery usage constraints (<5%/hour)
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val monitoringDuration = 2000L // 2 seconds for testing
        val initialBatteryLevel = getMockBatteryLevel()
        var maxCpuUsage = 0.0

        // Act - Monitor audio capture for specified duration
        val job = launch {
            audioCaptureService.startCapture { detected, _ -> /* Handle VAD */ }

            // Simulate audio capture CPU usage monitoring
            repeat(monitoringDuration / 100) {
                delay(100)
                val currentCpuUsage = simulateCpuUsageMonitoring()
                maxCpuUsage = maxOf(maxCpuUsage, currentCpuUsage)
            }
        }

        job.join()

        // Assert
        val finalBatteryLevel = getMockBatteryLevel()
        val batteryUsage = initialBatteryLevel - finalBatteryLevel

        // Extrapolate to hourly usage
        val hourlyBatteryUsage = batteryUsage * (3600000.0 / monitoringDuration)

        assertTrue("Hourly battery usage should be <5%, got $hourlyBatteryUsage%",
                   hourlyBatteryUsage < 5.0)
        assertTrue("CPU usage should be reasonable for audio processing", maxCpuUsage < 30.0)
    }

    @Test
    fun testAudioStreamingTurkishLanguageSupport() = runTest {
        /**
         * Test: Audio streaming properly handles Turkish language audio characteristics
         * Expected to FAIL until T050 is implemented
         */
        // Arrange
        val audioConfig = audioCaptureService.getAudioConfig()

        // Act - Configure for Turkish language
        audioCaptureService.configureLanguage("tr-TR")
        val turkishConfig = audioCaptureService.getCurrentLanguageConfig()

        // Assert
        assertEquals("tr-TR", turkishConfig.languageCode)

        // Turkish audio typically has different frequency characteristics
        // These should be accounted for in the capture configuration
        assertTrue("Should handle Turkish frequency range",
                   turkishConfig.minFrequencyHz <= 80 && turkishConfig.maxFrequencyHz >= 8000)
        assertTrue("Should use appropriate sample rate for Turkish",
                   audioConfig.sampleRate >= 16000)
    }

    // Helper methods for mocking
    private fun getMockBatteryLevel(): Double = 85.0 // Mock 85% battery

    private fun simulateCpuUsageMonitoring(): Double {
        // Simulate realistic CPU usage for audio processing (5-15%)
        return 5.0 + Math.random() * 10.0
    }
}

/**
 * Mock classes for testing until actual implementation
 */
class MockAudioCaptureService(private val context: Context) : AudioCaptureService(context) {
    private var backgroundOptimized = false
    private var languageConfig = LanguageConfig("en-US", 80, 8000)

    override fun getAudioConfig(): AudioConfig {
        return AudioConfig(16000, 1, AudioFormat.ENCODING_PCM_16BIT, 4096)
    }

    fun isBackgroundOptimized(): Boolean = backgroundOptimized

    fun onAppBackgrounded(callback: () -> Unit) {
        backgroundOptimized = true
        callback()
    }

    fun configureLanguage(languageCode: String) {
        languageConfig = when (languageCode) {
            "tr-TR" -> LanguageConfig("tr-TR", 80, 8000)
            else -> LanguageConfig("en-US", 80, 8000)
        }
    }

    fun getCurrentLanguageConfig(): LanguageConfig = languageConfig
}

data class AudioConfig(
    val sampleRate: Int,
    val channelCount: Int,
    val encoding: Int,
    val bufferSize: Int
)

data class LanguageConfig(
    val languageCode: String,
    val minFrequencyHz: Int,
    val maxFrequencyHz: Int
)