"""
Audio processing service with adaptive bitrate adjustment and Opus encoding.

This service handles:
- Audio buffer management for 16kHz PCM input
- Opus encoding and compression
- Voice Activity Detection (VAD) with configurable thresholds
- Adaptive bitrate based on network conditions (16-48 kbps)
- Real-time audio processing with <200ms buffering
- Turkish language audio optimization
- Performance monitoring and metrics
"""

import asyncio
import logging
import numpy as np
import struct
import io
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, List, Tuple
from collections import deque

logger = logging.getLogger(__name__)


class AudioQuality(Enum):
    """Audio quality levels with corresponding bitrates."""
    LOW = 16000      # 16 kbps - Poor network
    MEDIUM = 24000   # 24 kbps - Fair network
    HIGH = 32000     # 32 kbps - Good network
    EXCELLENT = 48000  # 48 kbps - Excellent network


@dataclass
class AudioConfig:
    """Audio configuration parameters."""
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit
    bitrate: int = 24000
    buffer_size_ms: int = 200
    vad_threshold: float = 0.02


@dataclass
class AudioMetrics:
    """Audio processing metrics."""
    buffer_size_bytes: int
    buffer_duration_ms: float
    current_bitrate: int
    quality_level: AudioQuality
    packets_processed: int
    packets_dropped: int
    average_processing_time_ms: float


@dataclass
class OpusEncoderConfig:
    """Configuration for Opus encoder."""
    sample_rate: int = 16000
    channels: int = 1
    bitrate: int = 24000
    application: str = "voip"  # "voip", "audio", "lowdelay"
    complexity: int = 5  # 0-10
    frame_size_ms: int = 20  # 2.5, 5, 10, 20, 40, 60


@dataclass
class ProcessedAudioChunk:
    """Processed audio chunk with metadata."""
    data: bytes
    sequence_number: int
    timestamp: float
    is_voice: bool
    encoded_size: int
    original_size: int
    quality_level: AudioQuality


class OpusEncoder:
    """
    Opus audio encoder for speech compression.

    Note: This is a simplified implementation for MVP.
    In production, use python-opus or similar library.
    """

    def __init__(self, config: Optional[OpusEncoderConfig] = None):
        """
        Initialize Opus encoder.

        Args:
            config: Opus encoder configuration
        """
        self.config = config or OpusEncoderConfig()
        self.sequence_number = 0

        # For MVP: Simulate Opus encoding with compression
        # In production: Initialize actual Opus encoder
        logger.info(f"Opus encoder initialized: {self.config.sample_rate}Hz, "
                   f"{self.config.bitrate}bps, {self.config.application}")

    def encode_pcm(self, pcm_data: bytes) -> bytes:
        """
        Encode PCM audio data to Opus format.

        Args:
            pcm_data: 16-bit PCM audio data

        Returns:
            Opus-encoded audio data

        Note: MVP implementation uses simple compression simulation
        """
        # For MVP: Simulate Opus encoding with configurable compression
        compression_ratio = self.config.bitrate / (self.config.sample_rate * 16)
        target_size = int(len(pcm_data) * compression_ratio)

        if target_size >= len(pcm_data):
            # No compression needed
            return pcm_data

        # Simple compression: take every nth sample + add header
        step = max(1, len(pcm_data) // target_size)
        compressed = bytearray()

        # Add Opus-like header (simplified)
        compressed.extend(struct.pack('<I', len(pcm_data)))  # Original size
        compressed.extend(struct.pack('<I', self.sequence_number))  # Sequence number
        compressed.extend(struct.pack('<H', self.config.sample_rate))  # Sample rate

        # Compressed audio data
        compressed.extend(pcm_data[::step])

        self.sequence_number += 1
        return bytes(compressed)

    def get_frame_size(self) -> int:
        """Get Opus frame size in bytes."""
        samples_per_frame = int(self.config.sample_rate * self.config.frame_size_ms / 1000)
        return samples_per_frame * 2  # 16-bit samples

    def set_bitrate(self, bitrate: int):
        """Set encoder bitrate."""
        self.config.bitrate = max(6000, min(510000, bitrate))  # Opus limits
        logger.info(f"Opus bitrate set to {self.config.bitrate}bps")

    def get_compression_ratio(self, input_size: int, output_size: int) -> float:
        """Get compression ratio for the latest encoding."""
        return input_size / output_size if output_size > 0 else 1.0


class AudioProcessor:
    """
    Process audio with adaptive bitrate based on network conditions.

    Features:
    - Adaptive bitrate adjustment
    - Buffer management
    - Voice Activity Detection
    - Audio quality optimization
    - Performance metrics tracking
    """

    def __init__(self, config: Optional[AudioConfig] = None):
        """
        Initialize audio processor with Opus encoding support.

        Args:
            config: Audio configuration parameters
        """
        self.config = config or AudioConfig()

        # Bitrate management
        self.current_quality = AudioQuality.MEDIUM
        self.target_bitrate = self.config.bitrate

        # Opus encoder
        opus_config = OpusEncoderConfig(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
            bitrate=self.config.bitrate,
            application="voip"
        )
        self.opus_encoder = OpusEncoder(opus_config)

        # Buffer management
        self.audio_buffer: deque[bytes] = deque(maxlen=10)  # Keep last 10 chunks
        self.buffer_size_bytes = (
            self.config.sample_rate *
            self.config.sample_width *
            self.config.channels *
            self.config.buffer_size_ms // 1000
        )

        # VAD (Voice Activity Detection)
        self.vad_enabled = True
        self.vad_threshold = self.config.vad_threshold

        # Sequence numbering for audio frames
        self.sequence_number = 0

        # Processing metrics
        self.packets_processed = 0
        self.packets_dropped = 0
        self.processing_times: deque[float] = deque(maxlen=100)
        self.total_compression_ratio = 0.0
        self.voice_activity_count = 0
        self.silence_count = 0

        # Callbacks
        self.quality_change_callback: Optional[Callable[[AudioQuality], None]] = None
        self.metrics_callback: Optional[Callable[[AudioMetrics], None]] = None

        logger.info(f"Audio processor initialized with {self.config.sample_rate}Hz, "
                   f"{self.config.bitrate}bps, Opus encoding enabled")

    def adjust_bitrate_for_network(
        self,
        latency_ms: float,
        packet_loss_percent: float
    ):
        """
        Adjust audio bitrate based on network conditions.

        Args:
            latency_ms: Current network latency in milliseconds
            packet_loss_percent: Current packet loss percentage

        Strategy:
        - Excellent network (<50ms, 0% loss): 48 kbps
        - Good network (50-100ms, <5% loss): 32 kbps
        - Fair network (100-200ms, 5-10% loss): 24 kbps
        - Poor network (>200ms or >10% loss): 16 kbps
        """
        previous_quality = self.current_quality

        # Determine quality based on network conditions
        if latency_ms < 50 and packet_loss_percent < 1:
            self.current_quality = AudioQuality.EXCELLENT
        elif latency_ms < 100 and packet_loss_percent < 5:
            self.current_quality = AudioQuality.HIGH
        elif latency_ms < 200 and packet_loss_percent < 10:
            self.current_quality = AudioQuality.MEDIUM
        else:
            self.current_quality = AudioQuality.LOW

        self.target_bitrate = self.current_quality.value

        # Update Opus encoder bitrate
        self.opus_encoder.set_bitrate(self.target_bitrate)

        # Log quality change
        if self.current_quality != previous_quality:
            logger.info(
                f"Audio quality adjusted: {previous_quality.name} -> {self.current_quality.name} "
                f"({self.target_bitrate}bps) due to latency={latency_ms:.1f}ms, "
                f"loss={packet_loss_percent:.1f}%"
            )

            # Invoke callback
            if self.quality_change_callback:
                try:
                    self.quality_change_callback(self.current_quality)
                except Exception as e:
                    logger.error(f"Error in quality change callback: {e}", exc_info=True)

    def process_audio_chunk(
        self,
        audio_data: bytes,
        detect_voice: bool = True
    ) -> Optional[ProcessedAudioChunk]:
        """
        Process audio chunk with VAD, Opus encoding, and quality adjustment.

        Args:
            audio_data: Raw 16-bit PCM audio data
            detect_voice: Whether to apply VAD filtering

        Returns:
            ProcessedAudioChunk with encoded data or None if silent (VAD filtered)
        """
        import time
        start_time = time.time()

        try:
            # Validate input
            if not audio_data:
                return None

            # Add to buffer
            self.audio_buffer.append(audio_data)

            # Apply VAD if enabled
            is_voice = True
            if detect_voice and self.vad_enabled:
                is_voice = self._detect_voice_activity(audio_data)
                if not is_voice:
                    self.silence_count += 1
                    logger.debug("No voice activity detected, skipping chunk")
                    return None
                else:
                    self.voice_activity_count += 1

            # Encode with Opus
            encoded_data = self.opus_encoder.encode_pcm(audio_data)

            # Create processed chunk
            processed_chunk = ProcessedAudioChunk(
                data=encoded_data,
                sequence_number=self.sequence_number,
                timestamp=time.time(),
                is_voice=is_voice,
                encoded_size=len(encoded_data),
                original_size=len(audio_data),
                quality_level=self.current_quality
            )

            # Update sequence number
            self.sequence_number += 1

            # Update compression metrics
            compression_ratio = self.opus_encoder.get_compression_ratio(
                len(audio_data), len(encoded_data)
            )
            self.total_compression_ratio = (
                (self.total_compression_ratio * (self.packets_processed - 1) + compression_ratio) /
                self.packets_processed if self.packets_processed > 0 else compression_ratio
            )

            # Update metrics
            self.packets_processed += 1
            processing_time = (time.time() - start_time) * 1000
            self.processing_times.append(processing_time)

            # Invoke metrics callback periodically
            if self.packets_processed % 10 == 0 and self.metrics_callback:
                metrics = self.get_metrics()
                try:
                    self.metrics_callback(metrics)
                except Exception as e:
                    logger.error(f"Error in metrics callback: {e}", exc_info=True)

            return processed_chunk

        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}", exc_info=True)
            self.packets_dropped += 1
            return None

    def _detect_voice_activity(self, audio_data: bytes) -> bool:
        """
        Detect voice activity using simple energy-based VAD.

        Args:
            audio_data: Raw audio data

        Returns:
            True if voice activity detected, False otherwise
        """
        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16)

            # Normalize to [-1, 1]
            audio_normalized = audio_array.astype(np.float32) / 32768.0

            # Calculate energy (RMS)
            energy = np.sqrt(np.mean(audio_normalized ** 2))

            # Check against threshold
            return energy > self.vad_threshold

        except Exception as e:
            logger.error(f"Error in VAD: {e}", exc_info=True)
            return True  # Assume voice activity on error

    def _apply_quality_settings(self, audio_data: bytes) -> bytes:
        """
        Apply current quality settings to audio data.

        Args:
            audio_data: Raw audio data

        Returns:
            Processed audio data

        Note: This method is kept for compatibility but actual processing
        happens in process_audio_chunk() with Opus encoding.
        """
        # Return original data as Opus encoding is handled in process_audio_chunk
        return audio_data

    def set_vad_threshold(self, threshold: float):
        """
        Set VAD threshold.

        Args:
            threshold: Energy threshold (0.0 - 1.0)
        """
        self.vad_threshold = max(0.0, min(1.0, threshold))
        logger.info(f"VAD threshold set to {self.vad_threshold}")

    def enable_vad(self, enabled: bool):
        """
        Enable or disable VAD.

        Args:
            enabled: True to enable VAD, False to disable
        """
        self.vad_enabled = enabled
        logger.info(f"VAD {'enabled' if enabled else 'disabled'}")

    def set_quality_change_callback(self, callback: Callable[[AudioQuality], None]):
        """
        Set callback for quality changes.

        Args:
            callback: Function to call when quality changes
        """
        self.quality_change_callback = callback

    def set_metrics_callback(self, callback: Callable[[AudioMetrics], None]):
        """
        Set callback for metrics updates.

        Args:
            callback: Function to call with AudioMetrics
        """
        self.metrics_callback = callback

    def get_metrics(self) -> AudioMetrics:
        """
        Get current audio processing metrics.

        Returns:
            AudioMetrics object
        """
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0.0
        )

        buffer_duration_ms = (
            len(self.audio_buffer) * self.config.buffer_size_ms
            if self.audio_buffer else 0
        )

        return AudioMetrics(
            buffer_size_bytes=self.buffer_size_bytes,
            buffer_duration_ms=buffer_duration_ms,
            current_bitrate=self.target_bitrate,
            quality_level=self.current_quality,
            packets_processed=self.packets_processed,
            packets_dropped=self.packets_dropped,
            average_processing_time_ms=avg_processing_time
        )

    def get_buffer_usage(self) -> float:
        """
        Get current buffer usage percentage.

        Returns:
            Buffer usage (0.0 - 100.0)
        """
        if not self.audio_buffer.maxlen:
            return 0.0

        return (len(self.audio_buffer) / self.audio_buffer.maxlen) * 100

    def clear_buffer(self):
        """Clear audio buffer."""
        self.audio_buffer.clear()
        logger.info("Audio buffer cleared")

    def reset_metrics(self):
        """Reset processing metrics."""
        self.packets_processed = 0
        self.packets_dropped = 0
        self.processing_times.clear()
        logger.info("Audio processor metrics reset")

    def get_recommended_buffer_size(self, latency_ms: float) -> int:
        """
        Get recommended buffer size based on network latency.

        Args:
            latency_ms: Network latency in milliseconds

        Returns:
            Recommended buffer size in milliseconds

        Strategy:
        - Low latency (<50ms): 100ms buffer
        - Medium latency (50-100ms): 200ms buffer
        - High latency (100-200ms): 300ms buffer
        - Very high latency (>200ms): 500ms buffer
        """
        if latency_ms < 50:
            return 100
        elif latency_ms < 100:
            return 200
        elif latency_ms < 200:
            return 300
        else:
            return 500

    def update_buffer_size(self, buffer_size_ms: int):
        """
        Update buffer size based on network conditions.

        Args:
            buffer_size_ms: New buffer size in milliseconds
        """
        self.config.buffer_size_ms = buffer_size_ms
        self.buffer_size_bytes = (
            self.config.sample_rate *
            self.config.sample_width *
            self.config.channels *
            buffer_size_ms // 1000
        )
        logger.info(f"Buffer size updated to {buffer_size_ms}ms ({self.buffer_size_bytes} bytes)")

    def get_voice_activity_ratio(self) -> float:
        """
        Get the ratio of voice activity to total processed chunks.

        Returns:
            Voice activity ratio (0.0 - 1.0)
        """
        total_chunks = self.voice_activity_count + self.silence_count
        if total_chunks == 0:
            return 0.0
        return self.voice_activity_count / total_chunks

    def get_compression_metrics(self) -> dict:
        """
        Get compression-related metrics.

        Returns:
            Dictionary with compression metrics
        """
        return {
            "average_compression_ratio": self.total_compression_ratio,
            "target_bitrate": self.target_bitrate,
            "current_quality": self.current_quality.name,
            "opus_config": {
                "sample_rate": self.opus_encoder.config.sample_rate,
                "bitrate": self.opus_encoder.config.bitrate,
                "application": self.opus_encoder.config.application,
                "frame_size_ms": self.opus_encoder.config.frame_size_ms
            }
        }

    def configure_for_turkish(self):
        """
        Optimize audio processing for Turkish language characteristics.

        Turkish has different frequency characteristics than English.
        This method adjusts VAD thresholds and quality settings accordingly.
        """
        # Turkish speech typically has different frequency characteristics
        # Adjust VAD to be more sensitive to Turkish phonemes
        self.vad_threshold = 0.015  # Slightly more sensitive
        self.opus_encoder.config.application = "voip"  # Optimized for speech

        logger.info("Audio processor configured for Turkish language")

    def validate_audio_format(self, audio_data: bytes) -> Tuple[bool, str]:
        """
        Validate that audio data meets expected format requirements.

        Args:
            audio_data: Raw audio data

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not audio_data:
            return False, "Empty audio data"

        # Check if data size is reasonable for 16kHz mono audio
        expected_frame_size = self.opus_encoder.get_frame_size()
        if len(audio_data) % 2 != 0:
            return False, f"Audio data size must be multiple of 2 (16-bit samples), got {len(audio_data)}"

        # Check for reasonable audio levels (basic validation)
        try:
            samples = struct.unpack(f'<{len(audio_data)//2}h', audio_data)
            max_sample = max(abs(s) for s in samples)
            if max_sample == 0:
                return False, "Audio signal appears to be silent"
            if max_sample > 32767:
                return False, f"Audio samples exceed 16-bit range: {max_sample}"
        except struct.error as e:
            return False, f"Invalid audio data format: {str(e)}"

        return True, ""

    def get_real_time_metrics(self) -> dict:
        """
        Get real-time performance metrics for monitoring.

        Returns:
            Dictionary with real-time metrics
        """
        import time
        current_time = time.time()

        return {
            "timestamp": current_time,
            "packets_processed": self.packets_processed,
            "packets_dropped": self.packets_dropped,
            "drop_rate": (self.packets_dropped / max(1, self.packets_processed + self.packets_dropped)) * 100,
            "voice_activity_ratio": self.get_voice_activity_ratio(),
            "buffer_usage_percent": self.get_buffer_usage(),
            "average_compression_ratio": self.total_compression_ratio,
            "current_bitrate": self.target_bitrate,
            "current_quality": self.current_quality.name,
            "last_processing_time_ms": self.processing_times[-1] if self.processing_times else 0
        }

    def reset(self):
        """Reset audio processor to initial state."""
        self.sequence_number = 0
        self.packets_processed = 0
        self.packets_dropped = 0
        self.voice_activity_count = 0
        self.silence_count = 0
        self.total_compression_ratio = 0.0
        self.processing_times.clear()
        self.audio_buffer.clear()
        logger.info("Audio processor reset to initial state")
