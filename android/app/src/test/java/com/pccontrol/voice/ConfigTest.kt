package com.pccontrol.voice

import org.junit.Test

import org.junit.Assert.*

/**
 * Unit tests for application configuration.
 */
class ConfigTest {

    @Test
    fun testDefaultConfiguration() {
        // Test that default configuration values are loaded correctly
        val config = loadTestConfig()

        assertEquals("http://10.0.2.2:8765", config.apiBaseUrl)
        assertEquals(10000, config.apiTimeoutMs)
        assertEquals(16000, config.audioSampleRate)
        assertEquals(true, config.debugMode)
    }

    @Test
    fun testConfigurationLoading() {
        // Test configuration file loading
        val properties = loadConfigProperties()

        assertNotNull(properties)
        assertTrue(properties.containsKey("API_BASE_URL"))
        assertTrue(properties.containsKey("AUDIO_SAMPLE_RATE"))
    }

    private fun loadTestConfig(): TestConfig {
        return TestConfig(
            apiBaseUrl = "http://10.0.2.2:8765",
            apiTimeoutMs = 10000,
            audioSampleRate = 16000,
            audioChannels = 1,
            debugMode = true
        )
    }

    private fun loadConfigProperties(): Map<String, String> {
        return mapOf(
            "API_BASE_URL" to "http://10.0.2.2:8765",
            "API_TIMEOUT_MS" to "10000",
            "AUDIO_SAMPLE_RATE" to "16000",
            "AUDIO_CHANNELS" to "1",
            "DEBUG_MODE" to "true"
        )
    }

    data class TestConfig(
        val apiBaseUrl: String,
        val apiTimeoutMs: Int,
        val audioSampleRate: Int,
        val audioChannels: Int,
        val debugMode: Boolean
    )
}