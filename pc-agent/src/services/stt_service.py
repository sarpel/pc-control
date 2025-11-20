"""
Speech-to-Text Service using Whisper.cpp

This service handles:
- Whisper.cpp STT integration for local processing
- Turkish language support with English technical terms
- Confidence scoring and validation
- Model loading and management
- Performance monitoring
- Error handling with Turkish error messages

Following requirements from spec and test T043.
"""

import asyncio
import logging
import json
import os
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path
import struct

logger = logging.getLogger(__name__)


class STTModelState(Enum):
    """State of the STT model."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    READY = "ready"
    ERROR = "error"


@dataclass
class STTConfig:
    """Configuration for Speech-to-Text service."""
    model_path: str = "models/whisper-base.bin"
    language: str = "tr"  # Primary Turkish with English terms
    translate: bool = False
    initial_prompt: str = ""
    temperature: float = 0.0
    no_speech_threshold: float = 0.6
    logprob_threshold: float = -1.0
    compression_ratio_threshold: float = 2.4
    condition_on_previous_text: bool = True


@dataclass
class STTResult:
    """Result of speech-to-text processing."""
    text: str
    confidence: float
    language: str
    processing_time_ms: float
    no_speech_prob: float
    segments: List[Dict[str, Any]]
    model_used: str
    success: bool
    error: Optional[str] = None


@dataclass
class STTMetrics:
    """Metrics for STT service performance."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_processing_time_ms: float
    average_confidence: float
    model_load_time_ms: float
    model_state: STTModelState


class WhisperService:
    """
    Whisper.cpp Speech-to-Text service implementation.

    Features:
    - Local STT processing with Whisper.cpp
    - Turkish language support with English technical terms
    - Confidence scoring and validation
    - Model state management
    - Performance monitoring
    - Graceful error handling
    """

    def __init__(self, config: Optional[STTConfig] = None):
        """
        Initialize Whisper STT service.

        Args:
            config: STT configuration parameters
        """
        self.config = config or STTConfig()
        self.model_state = STTModelState.UNLOADED
        self.model_path = Path(self.config.model_path)
        self.whisper_executable = None

        # Metrics
        self.metrics = STTMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_processing_time_ms=0.0,
            average_confidence=0.0,
            model_load_time_ms=0.0,
            model_state=self.model_state
        )

        # Processing times for averaging
        self.processing_times: List[float] = []
        self.confidence_scores: List[float] = []

        # Turkish language configuration
        self._configure_for_turkish()

        logger.info(f"Whisper STT service initialized with model: {self.model_path}")

    def _configure_for_turkish(self):
        """Configure Whisper for Turkish language with English technical terms."""
        # Turkish prompt with common technical terms
        self.config.initial_prompt = (
            "Bu bir Türkçe konuşma metnidir. "
            "Chrome, Windows, internet, bilgisayar gibi teknik terimler İngilizce olarak kullanılabilir. "
            "Lütfen Türkçe cümleleri doğru şekilde tanı."
        )

        # Set language auto-detection with Turkish preference
        self.config.language = "auto"  # Whisper will detect language
        self.config.temperature = 0.0  # Lower temperature for more consistent results

        logger.info("Whisper configured for Turkish with English technical terms")

    async def initialize_model(self) -> bool:
        """
        Initialize Whisper.cpp model.

        Returns:
            True if model loaded successfully, False otherwise
        """
        if self.model_state == STTModelState.READY:
            return True

        if self.model_state == STTModelState.LOADING:
            logger.warning("Model already loading")
            return False

        try:
            self.model_state = STTModelState.LOADING
            start_time = asyncio.get_event_loop().time()

            # Check if model file exists
            if not self.model_path.exists():
                logger.error(f"Model file not found: {self.model_path}")
                await self._download_model()

            if not self.model_path.exists():
                raise FileNotFoundError(f"Model file not found: {self.model_path}")

            # Find whisper executable
            self.whisper_executable = await self._find_whisper_executable()
            if not self.whisper_executable:
                raise RuntimeError("Whisper.cpp executable not found")

            # Test model by running a simple command
            test_result = await self._test_model()
            if not test_result:
                raise RuntimeError("Model test failed")

            load_time = (asyncio.get_event_loop().time() - start_time) * 1000
            self.metrics.model_load_time_ms = load_time
            self.metrics.model_state = STTModelState.READY
            self.model_state = STTModelState.READY

            logger.info(f"Whisper model loaded successfully in {load_time:.1f}ms")
            return True

        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
            self.model_state = STTModelState.ERROR
            self.metrics.model_state = STTModelState.ERROR
            return False

    async def transcribe_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> STTResult:
        """
        Transcribe audio data to text using Whisper.cpp.

        Args:
            audio_data: Raw PCM audio data (16-bit)
            sample_rate: Audio sample rate (default 16000)
            channels: Number of audio channels (default 1)

        Returns:
            STTResult with transcription text and metadata
        """
        if self.model_state != STTModelState.READY:
            # Try to initialize model if not ready
            if not await self.initialize_model():
                return STTResult(
                    text="",
                    confidence=0.0,
                    language="unknown",
                    processing_time_ms=0.0,
                    no_speech_prob=1.0,
                    segments=[],
                    model_used="none",
                    success=False,
                    error="STT servisi hazır değil. Model yüklenemedi."
                )

        start_time = asyncio.get_event_loop().time()
        self.metrics.total_requests += 1

        try:
            # Validate audio data
            if not audio_data:
                raise ValueError("Boş ses verisi")

            # Save audio data to temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                await self._save_audio_to_wav(audio_data, temp_file.name, sample_rate, channels)
                temp_wav_path = temp_file.name

            try:
                # Run Whisper.cpp
                result = await self._run_whisper_inference(temp_wav_path)

                # Update metrics
                processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
                self.processing_times.append(processing_time)
                if result.confidence > 0:
                    self.confidence_scores.append(result.confidence)

                # Update average metrics
                self._update_average_metrics()

                if result.success:
                    self.metrics.successful_requests += 1
                    logger.info(f"Transcription successful: '{result.text}' (confidence: {result.confidence:.2f})")
                else:
                    self.metrics.failed_requests += 1
                    logger.warning(f"Transcription failed: {result.error}")

                return result

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_wav_path)
                except OSError:
                    pass

        except Exception as e:
            logger.error(f"Error during transcription: {e}", exc_info=True)
            self.metrics.failed_requests += 1

            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

            # Return Turkish error message
            turkish_error = self._get_turkish_error_message(e)

            return STTResult(
                text="",
                confidence=0.0,
                language="unknown",
                processing_time_ms=processing_time,
                no_speech_prob=1.0,
                segments=[],
                model_used=str(self.model_path),
                success=False,
                error=turkish_error
            )

    async def _save_audio_to_wav(
        self,
        audio_data: bytes,
        file_path: str,
        sample_rate: int,
        channels: int
    ):
        """Save raw PCM audio data to WAV file."""
        with wave.open(file_path, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)

    async def _run_whisper_inference(self, wav_file_path: str) -> STTResult:
        """Run Whisper.cpp inference on WAV file."""
        try:
            # Build command arguments
            cmd = [
                str(self.whisper_executable),
                "-m", str(self.model_path),
                "-l", self.config.language,
                "-f", wav_file_path,
                "--output-json",
                "--temperature", str(self.config.temperature),
                "--no-speech-threshold", str(self.config.no_speech_threshold)
            ]

            if self.config.initial_prompt:
                cmd.extend(["--initial-prompt", self.config.initial_prompt])

            if self.config.translate:
                cmd.append("--translate")

            # Run command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore').strip()
                logger.error(f"Whisper.cpp failed: {error_msg}")
                return STTResult(
                    text="",
                    confidence=0.0,
                    language="unknown",
                    processing_time_ms=0.0,
                    no_speech_prob=1.0,
                    segments=[],
                    model_used=str(self.model_path),
                    success=False,
                    error=f"Whisper.cpp hata kodu: {process.returncode}"
                )

            # Parse JSON output
            try:
                result_json = json.loads(stdout.decode('utf-8'))
                return self._parse_whisper_result(result_json)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Whisper JSON output: {e}")
                return STTResult(
                    text="",
                    confidence=0.0,
                    language="unknown",
                    processing_time_ms=0.0,
                    no_speech_prob=1.0,
                    segments=[],
                    model_used=str(self.model_path),
                    success=False,
                    error="Whisper sonucu ayrıştırılamadı"
                )

        except Exception as e:
            logger.error(f"Error running Whisper inference: {e}", exc_info=True)
            return STTResult(
                text="",
                confidence=0.0,
                language="unknown",
                processing_time_ms=0.0,
                no_speech_prob=1.0,
                segments=[],
                model_used=str(self.model_path),
                success=False,
                error=f"Whisper çıkarımı başarısız: {str(e)}"
            )

    def _parse_whisper_result(self, result_json: Dict[str, Any]) -> STTResult:
        """Parse Whisper.cpp JSON output."""
        try:
            # Extract text from segments
            segments = result_json.get("segments", [])
            text_parts = [segment.get("text", "").strip() for segment in segments]
            full_text = " ".join(text_parts).strip()

            if not full_text:
                return STTResult(
                    text="",
                    confidence=0.0,
                    language=result_json.get("language", "unknown"),
                    processing_time_ms=0.0,
                    no_speech_prob=1.0,
                    segments=segments,
                    model_used=str(self.model_path),
                    success=True,
                    error="Konuşma algılanamadı"
                )

            # Calculate average confidence from segments
            confidences = [segment.get("avg_logprob", 0.0) for segment in segments]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            # Normalize confidence to 0-1 range (Whisper uses log probabilities)
            normalized_confidence = max(0.0, min(1.0, (avg_confidence + 1.0) / 2.0))

            # Get no_speech probability
            no_speech_prob = result_json.get("no_speech_prob", 0.0)

            return STTResult(
                text=full_text,
                confidence=normalized_confidence,
                language=result_json.get("language", "unknown"),
                processing_time_ms=0.0,  # Will be set by caller
                no_speech_prob=no_speech_prob,
                segments=segments,
                model_used=str(self.model_path),
                success=True
            )

        except Exception as e:
            logger.error(f"Error parsing Whisper result: {e}", exc_info=True)
            return STTResult(
                text="",
                confidence=0.0,
                language="unknown",
                processing_time_ms=0.0,
                no_speech_prob=1.0,
                segments=[],
                model_used=str(self.model_path),
                success=False,
                error=f"Sonuç ayrıştırma hatası: {str(e)}"
            )

    async def _find_whisper_executable(self) -> Optional[str]:
        """Find Whisper.cpp executable."""
        possible_paths = [
            "whisper",
            "./whisper",
            "./whisper.exe",
            "/usr/local/bin/whisper",
            "/usr/bin/whisper"
        ]

        for path in possible_paths:
            try:
                # Test if executable exists and is runnable
                process = await asyncio.create_subprocess_exec(
                    path, "--help",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                await process.communicate()

                if process.returncode == 0 or "whisper" in str(process.returncode):
                    logger.info(f"Found Whisper executable at: {path}")
                    return path

            except Exception as e:
                logger.debug(f"Whisper executable not found at {path}: {e}")
                continue

        return None

    async def _test_model(self) -> bool:
        """Test if model can be loaded by Whisper.cpp."""
        try:
            process = await asyncio.create_subprocess_exec(
                self.whisper_executable,
                "-m", str(self.model_path),
                "--help",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await process.communicate()
            return process.returncode == 0

        except Exception:
            return False

    async def _download_model(self):
        """Download Whisper model if not available."""
        try:
            logger.info(f"Downloading Whisper model to {self.model_path}...")
            
            # Ensure directory exists
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Use huggingface_hub to download the model
            # We download the ggml model file for whisper.cpp
            from huggingface_hub import hf_hub_download
            
            # Map model size to file name
            # Using ggml-base.bin as default for base model
            model_filename = f"ggml-{self.model_size}.bin"
            
            hf_hub_download(
                repo_id="ggerganov/whisper.cpp",
                filename=model_filename,
                local_dir=str(self.model_path.parent),
                local_dir_use_symlinks=False
            )
            
            # Rename if necessary to match expected path
            downloaded_file = self.model_path.parent / model_filename
            if downloaded_file != self.model_path and downloaded_file.exists():
                if self.model_path.exists():
                    self.model_path.unlink()
                downloaded_file.rename(self.model_path)
                
            logger.info("Model download completed successfully.")
            
        except Exception as e:
            logger.error(f"Failed to download model: {e}")
            raise

    def _get_turkish_error_message(self, error: Exception) -> str:
        """Convert error to Turkish error message."""
        error_str = str(error).lower()

        if "no such file" in error_str or "file not found" in error_str:
            return "Model dosyası bulunamadı"
        elif "permission denied" in error_str:
            return "Dosya erişim izni reddedildi"
        elif "invalid format" in error_str:
            return "Geçersiz ses formatı"
        elif "whisper" in error_str:
            return "Whisper.cpp işlem hatası"
        else:
            return f"Ses metni çevirme hatası: {str(error)}"

    def _update_average_metrics(self):
        """Update average processing metrics."""
        if self.processing_times:
            self.metrics.average_processing_time_ms = sum(self.processing_times) / len(self.processing_times)

        if self.confidence_scores:
            self.metrics.average_confidence = sum(self.confidence_scores) / len(self.confidence_scores)

    def get_metrics(self) -> STTMetrics:
        """
        Get current STT service metrics.

        Returns:
            STTMetrics object with current metrics
        """
        self.metrics.model_state = self.model_state
        self.metrics.average_processing_time_ms = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0.0
        )
        self.metrics.average_confidence = (
            sum(self.confidence_scores) / len(self.confidence_scores)
            if self.confidence_scores else 0.0
        )

        return self.metrics

    def reset_metrics(self):
        """Reset STT service metrics."""
        self.metrics = STTMetrics(
            total_requests=0,
            successful_requests=0,
            failed_requests=0,
            average_processing_time_ms=0.0,
            average_confidence=0.0,
            model_load_time_ms=self.metrics.model_load_time_ms,
            model_state=self.model_state
        )
        self.processing_times.clear()
        self.confidence_scores.clear()
        logger.info("STT metrics reset")

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on STT service.

        Returns:
            Health check result
        """
        return {
            "model_state": self.model_state.value,
            "model_path": str(self.model_path),
            "model_exists": self.model_path.exists(),
            "whisper_executable": self.whisper_executable is not None,
            "total_requests": self.metrics.total_requests,
            "success_rate": (
                self.metrics.successful_requests / max(1, self.metrics.total_requests) * 100
            ),
            "average_processing_time_ms": self.metrics.average_processing_time_ms
        }


# Global service instance
stt_service = WhisperService()