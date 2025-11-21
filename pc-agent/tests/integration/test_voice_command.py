"""
Integration tests for voice command flow.

Tests the complete voice command pipeline:
Audio capture -> STT -> LLM interpretation -> Command execution

These tests should FAIL initially (TDD approach) until services are implemented.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import uuid
from datetime import datetime

# These imports will fail initially - expected for TDD
try:
    from src.services.audio_processor import AudioProcessor
    from src.services.stt_service import STTService
    from src.services.command_interpreter import CommandInterpreter
    from src.services.system_controller import SystemController
    from src.models.voice_command import VoiceCommand
    from src.models.action import Action
except ImportError:
    # Placeholder for TDD
    AudioProcessor = None
    STTService = None
    CommandInterpreter = None
    SystemController = None
    VoiceCommand = None
    Action = None


@pytest.fixture
def audio_processor():
    """Initialize audio processor service."""
    if AudioProcessor is None:
        pytest.skip("AudioProcessor not yet implemented")
    processor = AudioProcessor()
    yield processor

@pytest.fixture
def stt_service():
    """Initialize speech-to-text service."""
    if STTService is None:
        pytest.skip("STTService not yet implemented")
    service = STTService(model_name="base")
    yield service

@pytest.fixture
def command_interpreter():
    """Initialize command interpreter service."""
    if CommandInterpreter is None:
        pytest.skip("CommandInterpreter not yet implemented")
    interpreter = CommandInterpreter()
    yield interpreter

@pytest.fixture
def system_controller():
    """Initialize system controller service."""
    if SystemController is None:
        pytest.skip("SystemController not yet implemented")
    controller = SystemController()
    yield controller

@pytest.fixture
def sample_audio_path():
    """Path to sample audio file for testing."""
    # This would be a real Turkish voice command: "Chrome'u aç"
    path = Path("tests/fixtures/audio/chrome_ac.opus")
    yield path
    # No cleanup needed for static path


@pytest.mark.integration
@pytest.mark.asyncio
class TestVoiceCommandFlow:
    """Integration tests for end-to-end voice command processing."""
    
    async def test_complete_voice_command_flow_success(
        self, audio_processor, stt_service, command_interpreter, system_controller
    ):
        """Test successful end-to-end voice command execution."""
        # Arrange: Mock audio data (Opus encoded)
        mock_audio_frames = [b"opus_frame_1", b"opus_frame_2", b"opus_frame_3"]
        command_id = uuid.uuid4()
        
        # Act: Process complete pipeline
        # Step 1: Decode audio
        pcm_audio = await audio_processor.decode_opus_stream(mock_audio_frames)
        assert pcm_audio is not None
        
        # Step 2: Transcribe to text
        transcription = await stt_service.transcribe(pcm_audio, language="tr")
        assert transcription.text is not None
        assert transcription.confidence >= 0.60
        
        # Step 3: Interpret command
        action = await command_interpreter.interpret(transcription.text)
        assert action.action_type in ["system", "browser", "query"]
        assert action.operation is not None
        
        # Step 4: Execute action
        result = await system_controller.execute(action)
        assert result.status in ["success", "failed"]
    
    async def test_voice_command_with_low_confidence(self, stt_service):
        """Test handling of low confidence transcription."""
        # Arrange: Poor quality audio
        noisy_audio = b"\x00" * 16000  # Silent/noisy audio
        
        # Act: Attempt transcription
        transcription = await stt_service.transcribe(noisy_audio, language="tr")
        
        # Assert: Low confidence detected
        if transcription.confidence < 0.60:
            assert transcription.requires_retry is True
            assert "düşük güven" in transcription.error_message.lower() or "low confidence" in transcription.error_message.lower()
    
    async def test_voice_command_turkish_with_english_terms(
        self, stt_service, command_interpreter
    ):
        """Test Turkish commands with English technical terms."""
        # Arrange: Mock transcription of "Chrome'u aç"
        turkish_command = "Chrome'u aç"
        
        # Act: Interpret mixed language command
        action = await command_interpreter.interpret(turkish_command)
        
        # Assert: Correctly parsed
        assert action.action_type == "system"
        assert action.operation == "launch_application"
        assert "chrome" in action.parameters.get("app_name", "").lower()
    
    async def test_voice_command_timeout_handling(self, stt_service):
        """Test timeout for long-running STT processing."""
        # Arrange: Very long audio (30+ seconds)
        long_audio = b"\x00" * (16000 * 35)  # 35 seconds
        
        # Act & Assert: Should timeout or handle gracefully
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                stt_service.transcribe(long_audio, language="tr"),
                timeout=30.0
            )
    
    async def test_voice_command_with_ambiguous_intent(self, command_interpreter):
        """Test handling of ambiguous commands."""
        # Arrange: Ambiguous command
        ambiguous_text = "aç"  # Could mean "open" but what?
        
        # Act: Attempt interpretation
        result = await command_interpreter.interpret(ambiguous_text)
        
        # Assert: Should request clarification or fail gracefully
        if result.requires_confirmation:
            assert result.confirmation_message is not None
            assert "hangi" in result.confirmation_message.lower() or "which" in result.confirmation_message.lower()
    
    async def test_voice_command_state_transitions(self):
        """Test voice command state machine transitions."""
        if VoiceCommand is None:
            pytest.skip("VoiceCommand not yet implemented")
        
        # Arrange: Create new voice command
        cmd = VoiceCommand(
            id=uuid.uuid4(),
            timestamp=datetime.now(),
            language="tr-TR",
            status="listening"
        )
        
        # Act & Assert: Verify valid state transitions
        assert cmd.status == "listening"
        
        cmd.status = "processing"
        assert cmd.status == "processing"
        
        cmd.status = "executing"
        assert cmd.status == "executing"
        
        cmd.status = "completed"
        assert cmd.status == "completed"
    
    async def test_voice_command_error_state(self):
        """Test voice command error state transition."""
        if VoiceCommand is None:
            pytest.skip("VoiceCommand not yet implemented")
        
        # Arrange: Command in processing
        cmd = VoiceCommand(
            id=uuid.uuid4(),
            timestamp=datetime.now(),
            language="tr-TR",
            status="processing"
        )
        
        # Act: Transition to error
        cmd.status = "error"
        cmd.error_code = "2002"  # AUDIO_PROCESSING_FAILED
        cmd.error_message = "STT işlemi başarısız oldu"
        
        # Assert: Error state captured
        assert cmd.status == "error"
        assert cmd.error_code is not None
        assert cmd.error_message is not None
    
    async def test_concurrent_voice_commands_handled(
        self, stt_service, command_interpreter
    ):
        """Test handling of multiple concurrent commands."""
        # Arrange: Multiple commands
        commands = [
            "Chrome'u aç",
            "ses seviyesini artır",
            "dosya bul test.txt"
        ]
        
        # Act: Process concurrently
        tasks = [
            command_interpreter.interpret(cmd)
            for cmd in commands
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assert: All processed
        assert len(results) == len(commands)
        for result in results:
            if not isinstance(result, Exception):
                assert result.action_type is not None
    
    async def test_voice_command_latency_requirement(self, audio_processor, stt_service):
        """Test <2s latency requirement for simple commands."""
        # Arrange: Short audio clip (1 second)
        mock_audio = b"\x00" * 16000
        start_time = datetime.now()
        
        # Act: Process audio
        pcm_audio = await audio_processor.decode_opus_stream([mock_audio])
        transcription = await stt_service.transcribe(pcm_audio, language="tr")
        
        # Assert: Latency under 2 seconds
        elapsed = (datetime.now() - start_time).total_seconds()
        assert elapsed < 2.0, f"Processing took {elapsed}s, requirement is <2s"
    
    async def test_audio_buffer_memory_cleanup(self, audio_processor):
        """Test audio data is not persisted (FR-017 privacy requirement)."""
        # Arrange: Process audio
        mock_frames = [b"frame1", b"frame2"]
        
        # Act: Decode audio
        pcm_audio = await audio_processor.decode_opus_stream(mock_frames)
        
        # Process and verify cleanup
        await audio_processor.cleanup_buffers()
        
        # Assert: Buffers cleared (verify no persistence)
        assert audio_processor.active_buffers == 0 or audio_processor.active_buffers is None


@pytest.mark.integration
@pytest.mark.asyncio
class TestCommandHistoryTracking:
    """Integration tests for command history functionality."""
    
    async def test_command_history_limited_to_five(self):
        """Test command history maintains max 5 entries (FR-016)."""
        if VoiceCommand is None:
            pytest.skip("VoiceCommand not yet implemented")
        
        # Arrange: Mock command history service
        from src.services.command_history_service import CommandHistoryService
        history = CommandHistoryService(max_size=5)
        
        # Act: Add 7 commands
        for i in range(7):
            cmd = VoiceCommand(
                id=uuid.uuid4(),
                transcribed_text=f"Command {i}",
                timestamp=datetime.now(),
                language="tr-TR",
                status="completed"
            )
            await history.add_command(cmd)
        
        # Assert: Only latest 5 retained
        recent = await history.get_recent()
        assert len(recent) == 5
        assert recent[0].transcribed_text == "Command 6"  # Most recent
        assert recent[-1].transcribed_text == "Command 2"  # Oldest kept
    
    async def test_command_history_10_minute_retention(self):
        """Test commands auto-expire after 10 minutes."""
        # This would be tested with time manipulation
        # Placeholder for now - requires time mocking
        pytest.skip("Requires time mocking implementation")


@pytest.mark.integration 
@pytest.mark.asyncio
class TestErrorRecovery:
    """Integration tests for error recovery scenarios."""
    
    async def test_stt_failure_recovery(self, stt_service):
        """Test graceful handling of STT service failure."""
        # Arrange: Invalid audio
        invalid_audio = b"not_valid_audio"
        
        # Act & Assert: Should not crash
        with pytest.raises(Exception) as exc_info:
            await stt_service.transcribe(invalid_audio, language="tr")
        
        # Verify proper error type returned
        assert exc_info.value is not None
    
    async def test_llm_unavailable_queuing(self, command_interpreter):
        """Test command queuing when LLM API unavailable (FR-004)."""
        # Arrange: Mock LLM unavailable
        with patch.object(command_interpreter, '_call_llm_api', side_effect=Exception("API unavailable")):
            command = "Chrome'u aç"
            
            # Act: Attempt interpretation
            result = await command_interpreter.interpret(command, retry_on_failure=True)
            
            # Assert: Queued for retry
            assert result.status == "queued" or result.requires_retry is True
            assert result.retry_count >= 0