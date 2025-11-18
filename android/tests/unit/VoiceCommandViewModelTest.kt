package com.pccontrol.voice.presentation.viewmodel

import androidx.arch.core.executor.testing.InstantTaskExecutorRule
import app.cash.turbine.test
import com.google.common.truth.Truth.assertThat
import com.pccontrol.voice.audio.AudioProcessingService
import com.pccontrol.voice.network.WebSocketManager
import com.pccontrol.voice.presentation.viewmodel.VoiceCommandUiState
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Before
import org.junit.Rule
import org.junit.Test

/**
 * Unit tests for VoiceCommandViewModel.
 */
@ExperimentalCoroutinesApi
class VoiceCommandViewModelTest {

    @get:Rule
    val instantTaskExecutorRule = InstantTaskExecutorRule()

    private lateinit var viewModel: VoiceCommandViewModel
    private lateinit var mockAudioProcessingService: AudioProcessingService
    private lateinit var mockWebSocketManager: WebSocketManager

    @Before
    fun setup() {
        mockAudioProcessingService = mockk()
        mockWebSocketManager = mockk()

        // Mock default behavior
        every { mockAudioProcessingService.initialize() } returns mockk()
        coEvery { mockWebSocketManager.isConnected } returns mockk()
        every { mockWebSocketManager.isConnected } returns mockk()
        every { mockAudioProcessingService.cancelProcessing() } returns mockk()

        viewModel = VoiceCommandViewModel(
            audioProcessingService = mockAudioProcessingService,
            webSocketManager = mockWebSocketManager
        )
    }

    @Test
    fun `initialize should set up services and collect connection status`() = runTest {
        // Given
        every { mockWebSocketManager.isConnected } returns mockk()

        // When
        viewModel.initialize()

        // Then
        verify { mockAudioProcessingService.initialize() }
    }

    @Test
    fun `startListening should update UI state to listening`() = runTest {
        // Given
        val mockResult = mockk<AudioProcessingService.VoiceCommandResult>()
        every { mockResult.isValid } returns true
        every { mockResult.transcription } returns "Chrome'u aç"
        every { mockResult.confidence } returns 0.9f

        coEvery { mockAudioProcessingService.startVoiceCommandProcessing() } returns mockResult
        coEvery { mockWebSocketManager.sendVoiceCommand(any(), any(), any()) } returns true

        // When
        viewModel.startListening()

        // Then
        viewModel.uiState.test {
            // Should show listening state
            assertThat(awaitItem().isListening).isTrue()
            assertThat(awaitItem().statusMessage).isEqualTo("Dinleniyor...")
            assertThat(awaitItem().isError).isFalse()
        }
    }

    @Test
    fun `startListening should handle successful voice command processing`() = runTest {
        // Given
        val mockResult = mockk<AudioProcessingService.VoiceCommandResult>()
        every { mockResult.isValid } returns true
        every { mockResult.transcription } returns "Chrome'u aç"
        every { mockResult.confidence } returns 0.9f

        coEvery { mockAudioProcessingService.startVoiceCommandProcessing() } returns mockResult
        coEvery { mockWebSocketManager.sendVoiceCommand(any(), any(), any()) } returns true

        // When
        viewModel.startListening()

        // Then
        viewModel.uiState.test {
            val finalState = awaitItem()
            assertThat(finalState.statusMessage).isEqualTo("Chrome'u aç")
            assertThat(finalState.isError).isFalse()
            assertThat(finalState.recentCommands).hasSize(1)
            assertThat(finalState.recentCommands.first().transcription).isEqualTo("Chrome'u aç")
        }
    }

    @Test
    fun `startListening should handle failed voice command processing`() = runTest {
        // Given
        coEvery { mockAudioProcessingService.startVoiceCommandProcessing() } throws
            Exception("Audio processing error")

        // When
        viewModel.startListening()

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            assertThat(state.statusMessage).isEqualTo("Hata: Audio processing error")
            assertThat(state.isError).isTrue()
            assertThat(state.isListening).isFalse()
        }
    }

    @Test
    fun `stopListening should update UI state to stopped`() = runTest {
        // Given
        val initialUIState = VoiceCommandUiState(isListening = true)

        // When
        viewModel.stopListening()

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            assertThat(state.isListening).isFalse()
            assertThat(state.statusMessage).isEqualTo("Durduruldu")
            assertThat(state.currentTranscription).isEmpty()
        }

        verify { mockAudioProcessingService.cancelProcessing() }
    }

    @Test
    fun `stopListening should handle errors gracefully`() = runTest {
        // Given
        coEvery { mockAudioProcessingService.cancelProcessing() } throws
            Exception("Cancellation error")

        // When
        viewModel.stopListening()

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            assertThat(state.statusMessage).isEqualTo("Hata: Cancellation error")
            assertThat(state.isError).isTrue()
        }
    }

    @Test
    fun `WebSocket connection status should update UI state`() = runTest {
        // Given
        every { mockWebSocketManager.isConnected } returns true

        // When
        viewModel.initialize()

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            assertThat(state.isConnected).isTrue()
            assertThat(state.connectedPcName).isEqualTo("PC")
        }
    }

    @Test
    fun `recent commands should be limited to 5 items`() = runTest {
        // Given
        val mockResults = List(6) { index ->
            mockk<AudioProcessingService.VoiceCommandResult>().apply {
                every { isValid } returns true
                every { transcription } returns "Komut $index"
                every { confidence } returns 0.9f
            }
        }

        coEvery { mockAudioProcessingService.startVoiceCommandProcessing() } returnsMany(mockResults)
        coEvery { mockWebSocketManager.sendVoiceCommand(any(), any(), any()) } returns true

        // When - Process 6 commands
        repeat(6) {
            viewModel.startListening()
        }

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            assertThat(state.recentCommands).hasSize(5)
            // Should keep the 5 most recent (last 5 in the list)
            assertThat(state.recentCommands.first().transcription).isEqualTo("Komut 6")
            assertThat(state.recentCommands.last().transcription).isEqualTo("Komut 2")
        }
    }

    @Test
    fun `command result suggestions should be included in recent commands`() = runTest {
        // Given
        val mockResult = mockk<AudioProcessingService.VoiceCommandResult>()
        every { mockResult.isValid } returns true
        every { mockResult.transcription } returns "Google ara"
        every { mockResult.confidence } returns 0.8f

        coEvery { mockAudioProcessingService.startVoiceCommandProcessing() } returns mockResult
        coEvery { mockWebSocketManager.sendVoiceCommand(any(), any(), any()) } returns true

        // When
        viewModel.startListening()

        // Then
        viewModel.uiState.test {
            val state = awaitItem()
            val recentCommand = state.recentCommands.first()
            assertThat(recentCommand.transcription).isEqualTo("Google ara")
            assertThat(recentCommand.success).isTrue()
        }
    }
}