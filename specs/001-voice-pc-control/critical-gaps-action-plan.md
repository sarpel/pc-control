# Critical Gaps Action Plan: Voice-Controlled PC Assistant

**Date**: 2025-11-18
**Current Progress**: ~31% complete (40/129 tasks)
**Status**: Phase 2 (Foundational) mostly complete, Phase 3-4 partially started

## Executive Summary

Implementation is ~40 tasks into a 129-task roadmap. **Critical blocker**: Constitution mandates TDD workflow, but tests are not being written before implementation. This violates Principle II and risks technical debt. Additionally, 6 core MVP features are missing.

## Critical Issues

### =4 **BLOCKING: TDD Violation**
**Problem**: Implementation proceeding without test-first approach
**Impact**: Violates constitution Principle II, risks untestable code
**Priority**: **IMMEDIATE FIX REQUIRED**

### =4 **BLOCKING: MVP Features Missing**
Six critical features prevent User Story 1 (MVP) from functioning:
1. Wake-on-LAN service
2. Whisper.cpp STT integration
3. Claude API command interpreter
4. Quick Settings Tile
5. Foreground service
6. Pairing workflow completion

---

## Detailed Action Plan

### Priority 1: Fix TDD Violations (IMMEDIATE)

#### Task Group 1A: Write Missing Tests for User Story 1
**Files to create**: `pc-agent/tests/contract/test_wol_api.py`
**Time estimate**: 2 hours
**Acceptance criteria**: Test fails with "NotImplementedError"

```python
# pc-agent/tests/contract/test_wol_api.py
import pytest
from fastapi.testclient import TestClient

class TestWakeOnLANAPI:
    """Contract tests for Wake-on-LAN API (T042)"""

    def test_wake_pc_endpoint_exists(self, client: TestClient):
        """Verify /api/wol/wake endpoint exists"""
        response = client.post("/api/wol/wake", json={
            "mac_address": "AA:BB:CC:DD:EE:FF"
        })
        assert response.status_code != 404, "Endpoint should exist"

    def test_wake_pc_validates_mac_address(self, client: TestClient):
        """Verify MAC address validation"""
        response = client.post("/api/wol/wake", json={
            "mac_address": "invalid"
        })
        assert response.status_code == 422, "Should reject invalid MAC"

    def test_wake_pc_returns_status(self, client: TestClient):
        """Verify response includes wake status"""
        response = client.post("/api/wol/wake", json={
            "mac_address": "AA:BB:CC:DD:EE:FF"
        })
        data = response.json()
        assert "status" in data, "Response should include status"
        assert data["status"] in ["waking", "awake", "timeout"]

    def test_wake_pc_with_timeout(self, client: TestClient):
        """Verify 15-second service startup timeout"""
        response = client.post("/api/wol/wake", json={
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "timeout_seconds": 15
        })
        assert response.status_code == 200
        data = response.json()
        assert "elapsedMs" in data
```

**Action steps**:
1. Create `test_wol_api.py` with above content
2. Run `pytest pc-agent/tests/contract/test_wol_api.py`
3. **VERIFY ALL TESTS FAIL** (red phase)
4. Only then proceed to implement Wake-on-LAN

---

#### Task Group 1B: Write Voice Command Flow Tests
**Files to create**: `pc-agent/tests/integration/test_voice_command.py`
**Time estimate**: 3 hours
**Dependencies**: Contract tests from 1A

```python
# pc-agent/tests/integration/test_voice_command.py
import pytest
from unittest.mock import Mock, patch
import asyncio

class TestVoiceCommandFlow:
    """Integration tests for end-to-end voice command flow (T043)"""

    @pytest.mark.asyncio
    async def test_audio_to_transcription_pipeline(self):
        """Verify audio bytes -> Whisper -> text transcription"""
        # Arrange
        audio_data = b"fake_opus_audio_data"

        # Act
        with pytest.raises(NotImplementedError):
            transcription = await process_audio_to_text(audio_data)

        # Assert (will fail until implemented)
        assert False, "Whisper.cpp integration not implemented"

    @pytest.mark.asyncio
    async def test_transcription_to_action_pipeline(self):
        """Verify transcription -> Claude API -> action interpretation"""
        # Arrange
        transcription = "Chrome'u aç"

        # Act
        with pytest.raises(NotImplementedError):
            action = await interpret_command(transcription)

        # Assert (will fail until implemented)
        assert False, "Claude API command interpreter not implemented"

    @pytest.mark.asyncio
    async def test_end_to_end_voice_command(self, mock_whisper, mock_claude):
        """Verify full pipeline: audio -> transcription -> interpretation -> execution"""
        # Arrange
        audio_data = create_test_audio("Chrome'u aç")

        # Act & Assert
        with pytest.raises(NotImplementedError):
            result = await execute_voice_command(audio_data)

        assert False, "End-to-end pipeline not implemented"

    @pytest.mark.asyncio
    async def test_latency_under_2_seconds(self):
        """Verify <2s end-to-end latency (SC-003)"""
        import time

        audio_data = create_test_audio("sesi yüzde 50'ye ayarla")

        start = time.time()
        # Will fail until implemented
        with pytest.raises(NotImplementedError):
            result = await execute_voice_command(audio_data)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"Latency {elapsed}s exceeds 2s requirement"
```

**Action steps**:
1. Create `test_voice_command.py` with above content
2. Run tests, **verify all fail**
3. Implement features to make tests pass (green phase)

---

#### Task Group 1C: Write Android Audio Streaming Tests
**Files to create**: `android/tests/integration/AudioStreamingTest.kt`
**Time estimate**: 2 hours

```kotlin
// android/tests/integration/AudioStreamingTest.kt
package com.pccontrol.voice.tests.integration

import androidx.test.ext.junit.runners.AndroidJUnit4
import com.pccontrol.voice.audio.AudioRecorder
import com.pccontrol.voice.network.AudioStreamer
import kotlinx.coroutines.runBlocking
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.test.assertTrue
import kotlin.test.fail

@RunWith(AndroidJUnit4::class)
class AudioStreamingTest {

    @Test
    fun testAudioCaptureAt16kHz() = runBlocking {
        // Arrange
        val recorder = AudioRecorder()

        // Act & Assert
        try {
            val audioData = recorder.recordAudio(durationMs = 1000)
            fail("AudioRecorder.recordAudio() not implemented - test should fail")
        } catch (e: NotImplementedError) {
            // Expected until implementation
            assertTrue(true, "Test correctly fails before implementation")
        }
    }

    @Test
    fun testOpusEncodingReducesBandwidth() = runBlocking {
        // Verify 85% bandwidth reduction (256kbps PCM -> 24kbps Opus)
        val rawPcmData = ByteArray(32000) // 1 second at 16kHz 16-bit

        try {
            val opusData = encodeToOpus(rawPcmData)
            fail("Opus encoding not implemented")
        } catch (e: NotImplementedError) {
            assertTrue(true, "Test correctly fails")
        }
    }

    @Test
    fun testWebSocketBinaryFrameTransmission() = runBlocking {
        // Verify binary frame format: UUID (16) + sequence (8) + audio (N)
        val commandId = UUID.randomUUID()
        val audioData = ByteArray(480) // 20ms Opus frame

        try {
            val streamer = AudioStreamer(mockWebSocket)
            streamer.sendAudioFrame(commandId, sequence = 0, audioData)
            fail("AudioStreamer.sendAudioFrame() not implemented")
        } catch (e: NotImplementedError) {
            assertTrue(true, "Test correctly fails")
        }
    }

    @Test
    fun testAudioBufferingUnder200ms() = runBlocking {
        // Verify <200ms audio buffering delay (FR-008)
        val startTime = System.currentTimeMillis()

        try {
            val recorder = AudioRecorder()
            recorder.startRecording()
            val firstFrame = recorder.getNextFrame() // Should arrive <200ms
            val elapsed = System.currentTimeMillis() - startTime

            assertTrue(elapsed < 200, "Buffering delay $elapsed ms exceeds 200ms")
        } catch (e: NotImplementedError) {
            assertTrue(true, "Test correctly fails")
        }
    }
}
```

**Action steps**:
1. Create `AudioStreamingTest.kt`
2. Run `./gradlew connectedAndroidTest`
3. **Verify tests fail** (red phase)
4. Implement audio streaming features

---

### Priority 2: Complete Phase 2 Networking (3 tasks)

#### Task 2A: Network Latency Monitoring (T117)
**File**: `pc-agent/src/services/network_monitor.py`
**Time estimate**: 2 hours
**Purpose**: Monitor latency and trigger warnings per FR-021

```python
# pc-agent/src/services/network_monitor.py
from dataclasses import dataclass
from enum import Enum
import asyncio
import time

class LatencyThreshold(Enum):
    NORMAL = (0, 200)       # <200ms: Normal operation
    WARNING = (200, 500)    # 200-500ms: Display warning
    SEVERE = (500, 1000)    # 500-1000ms: Severe warning
    CRITICAL = (1000, float('inf'))  # >1000ms: Error

@dataclass
class NetworkQuality:
    latency_ms: int
    threshold: LatencyThreshold
    message_tr: str  # Turkish message for user

class NetworkMonitor:
    """Monitor network latency and provide quality indicators (T117)"""

    def __init__(self, websocket_connection):
        self.connection = websocket_connection
        self.latency_history = []
        self.current_quality = NetworkQuality(0, LatencyThreshold.NORMAL, "Normal")

    async def measure_latency(self) -> int:
        """Send ping, measure round-trip time"""
        start = time.time()
        await self.connection.send_json({"type": "ping", "timestamp": start})

        # Wait for pong response
        response = await self.connection.receive_json()
        assert response["type"] == "pong"

        elapsed_ms = int((time.time() - start) * 1000)
        self.latency_history.append(elapsed_ms)
        return elapsed_ms

    def get_quality_status(self, latency_ms: int) -> NetworkQuality:
        """Determine quality based on latency thresholds"""
        if latency_ms < 200:
            return NetworkQuality(
                latency_ms,
                LatencyThreshold.NORMAL,
                ""  # No message for normal
            )
        elif latency_ms < 500:
            return NetworkQuality(
                latency_ms,
                LatencyThreshold.WARNING,
                "Yava_ a tespit edildi. Sesli komutlar gecikebilir."
            )
        elif latency_ms < 1000:
            return NetworkQuality(
                latency_ms,
                LatencyThreshold.SEVERE,
                "Çok yava_ a. Ses kalitesi dü_ebilir."
            )
        else:
            return NetworkQuality(
                latency_ms,
                LatencyThreshold.CRITICAL,
                "A çok yava_. Sesli komutlar çal1_mayabilir."
            )

    async def monitor_continuously(self, interval_seconds: int = 10):
        """Continuously monitor latency every N seconds"""
        while True:
            latency = await self.measure_latency()
            self.current_quality = self.get_quality_status(latency)

            # Broadcast quality change to Android client
            if self.current_quality.message_tr:
                await self.connection.send_json({
                    "type": "network_quality_update",
                    "latency_ms": latency,
                    "status": self.current_quality.threshold.name,
                    "message": self.current_quality.message_tr
                })

            await asyncio.sleep(interval_seconds)
```

**Implementation steps**:
1. Create test for `NetworkMonitor` (TDD!)
2. Implement `network_monitor.py`
3. Integrate into WebSocket server
4. Add Android UI indicator (Task 2C)

---

#### Task 2B: Adaptive Bitrate Adjustment (T118)
**File**: `pc-agent/src/services/audio_processor.py` (extend existing)
**Time estimate**: 3 hours
**Purpose**: Adjust Opus bitrate based on network quality

```python
# pc-agent/src/services/audio_processor.py (extend)
class AdaptiveBitrateController:
    """Adjust Opus bitrate based on network conditions (T118)"""

    BITRATE_PRESETS = {
        LatencyThreshold.NORMAL: 24000,    # 24 kbps (high quality)
        LatencyThreshold.WARNING: 16000,   # 16 kbps (medium)
        LatencyThreshold.SEVERE: 12000,    # 12 kbps (low)
        LatencyThreshold.CRITICAL: 8000,   # 8 kbps (minimum)
    }

    def __init__(self, network_monitor: NetworkMonitor):
        self.network_monitor = network_monitor
        self.current_bitrate = self.BITRATE_PRESETS[LatencyThreshold.NORMAL]

    def adjust_bitrate_for_quality(self, quality: NetworkQuality) -> int:
        """Adjust Opus bitrate based on current network quality"""
        new_bitrate = self.BITRATE_PRESETS[quality.threshold]

        if new_bitrate != self.current_bitrate:
            logger.info(f"Adjusting bitrate: {self.current_bitrate} -> {new_bitrate} bps")
            self.current_bitrate = new_bitrate

            # Notify Android client to adjust encoder
            return new_bitrate

        return self.current_bitrate

    async def monitor_and_adjust(self):
        """Continuously adjust bitrate based on network quality"""
        while True:
            quality = self.network_monitor.current_quality
            new_bitrate = self.adjust_bitrate_for_quality(quality)

            if new_bitrate != self.current_bitrate:
                await self.send_bitrate_update_to_android(new_bitrate)

            await asyncio.sleep(5)  # Check every 5 seconds
```

**Implementation steps**:
1. Write test for adaptive bitrate
2. Implement `AdaptiveBitrateController`
3. Integrate with audio processing pipeline
4. Add Android Opus encoder bitrate adjustment

---

#### Task 2C: Network Quality Android UI (T119)
**File**: `android/app/src/main/java/com/pccontrol/voice/presentation/ui/components/NetworkQualityIndicator.kt`
**Time estimate**: 2 hours

```kotlin
// NetworkQualityIndicator.kt
package com.pccontrol.voice.presentation.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

enum class NetworkQualityLevel {
    NORMAL,    // <200ms: Green
    WARNING,   // 200-500ms: Yellow
    SEVERE,    // 500-1000ms: Orange
    CRITICAL   // >1000ms: Red
}

@Composable
fun NetworkQualityIndicator(
    latencyMs: Int,
    qualityLevel: NetworkQualityLevel,
    message: String,
    modifier: Modifier = Modifier
) {
    val indicatorColor = when (qualityLevel) {
        NetworkQualityLevel.NORMAL -> Color.Green
        NetworkQualityLevel.WARNING -> Color.Yellow
        NetworkQualityLevel.SEVERE -> Color(0xFFFF9800) // Orange
        NetworkQualityLevel.CRITICAL -> Color.Red
    }

    Row(
        modifier = modifier
            .fillMaxWidth()
            .padding(8.dp)
    ) {
        // Colored indicator dot
        Box(
            modifier = Modifier
                .size(12.dp)
                .background(indicatorColor, shape = MaterialTheme.shapes.small)
        )

        Spacer(modifier = Modifier.width(8.dp))

        // Latency text
        Text(
            text = "${latencyMs}ms",
            style = MaterialTheme.typography.bodyMedium
        )

        // Warning message (if any)
        if (message.isNotEmpty()) {
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                color = indicatorColor
            )
        }
    }
}
```

**Implementation steps**:
1. Create `NetworkQualityIndicator` composable
2. Integrate into `ConnectionStatusScreen`
3. Connect to WebSocket quality updates
4. Test visual feedback timing

---

### Priority 3: Wake-on-LAN Implementation (T045)

#### Task 3A: Wake-on-LAN Service
**File**: `pc-agent/src/services/wol_service.py`
**Time estimate**: 2 hours
**Prerequisites**: Tests from Priority 1A must be written first

```python
# pc-agent/src/services/wol_service.py
import socket
import asyncio
import time
from typing import Tuple

class WakeOnLANService:
    """Send Wake-on-LAN magic packets and monitor PC wake status (T045)"""

    def __init__(self, health_check_endpoint: str = "http://localhost:8080/health"):
        self.health_endpoint = health_check_endpoint
        self.broadcast_port = 9  # Standard WoL port

    def create_magic_packet(self, mac_address: str) -> bytes:
        """Create WoL magic packet: FF*6 + MAC*16"""
        # Remove separators from MAC address
        mac = mac_address.replace(":", "").replace("-", "")

        # Validate MAC address
        if len(mac) != 12:
            raise ValueError(f"Invalid MAC address: {mac_address}")

        # Convert to bytes
        mac_bytes = bytes.fromhex(mac)

        # Magic packet: 6 bytes of FF + MAC repeated 16 times
        magic_packet = b'\xff' * 6 + mac_bytes * 16
        return magic_packet

    def send_wol_packet(self, mac_address: str, broadcast_ip: str = "255.255.255.255"):
        """Send WoL magic packet via UDP broadcast"""
        magic_packet = self.create_magic_packet(mac_address)

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, (broadcast_ip, self.broadcast_port))

        logger.info(f"WoL packet sent to {mac_address}")

    async def wait_for_service_ready(self, timeout_seconds: int = 15) -> Tuple[bool, int]:
        """Wait for PC service to become available after wake"""
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Attempt health check
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.health_endpoint, timeout=2) as response:
                        if response.status == 200:
                            elapsed_ms = int((time.time() - start_time) * 1000)
                            logger.info(f"Service ready after {elapsed_ms}ms")
                            return True, elapsed_ms
            except (aiohttp.ClientError, asyncio.TimeoutError):
                # Service not ready yet, wait and retry
                await asyncio.sleep(1)

        # Timeout reached
        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Service not ready after {elapsed_ms}ms")
        return False, elapsed_ms

    async def wake_and_wait(self, mac_address: str, timeout_seconds: int = 15) -> dict:
        """Send WoL packet and wait for service availability"""
        # Send WoL packet
        self.send_wol_packet(mac_address)

        # Wait for service to become available
        is_ready, elapsed_ms = await self.wait_for_service_ready(timeout_seconds)

        if is_ready:
            return {
                "status": "awake",
                "elapsedMs": elapsed_ms,
                "message": "PC uyan1k ve haz1r"
            }
        else:
            return {
                "status": "timeout",
                "elapsedMs": elapsed_ms,
                "message": "PC yan1t vermiyor. Servis durumunu kontrol edin."
            }
```

**Implementation steps**:
1. **VERIFY tests fail** (from Priority 1A)
2. Implement `wol_service.py`
3. Run tests until they pass (green phase)
4. Add REST endpoint `/api/wol/wake`
5. Integrate with Android WoL trigger

---

### Priority 4: Whisper.cpp STT Integration (T047)

#### Task 4A: Whisper.cpp Python Bindings
**File**: `pc-agent/src/services/stt_service.py`
**Time estimate**: 4 hours
**Prerequisites**: Whisper model downloaded

```python
# pc-agent/src/services/stt_service.py
from whisper_cpp import Whisper
import numpy as np
from pathlib import Path

class WhisperSTTService:
    """Local speech-to-text using Whisper.cpp (T047)"""

    def __init__(self, model_path: str = "models/ggml-base.bin"):
        """Initialize Whisper model"""
        if not Path(model_path).exists():
            raise FileNotFoundError(
                f"Whisper model not found: {model_path}\n"
                f"Run: python scripts/download_whisper_model.py --model base"
            )

        # Load Whisper base model (74M params, ~500ms inference)
        self.model = Whisper(model_path)
        self.sample_rate = 16000  # Required by Whisper

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language: str = "tr"  # Turkish primary language
    ) -> dict:
        """
        Transcribe audio to text

        Args:
            audio_bytes: Raw PCM audio data (16kHz, 16-bit, mono)
            language: ISO 639-1 language code (tr=Turkish)

        Returns:
            {
                "text": str,
                "confidence": float (0.0-1.0),
                "language": str,
                "duration_ms": int
            }
        """
        import time
        start = time.time()

        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        # Transcribe with Whisper
        result = self.model.transcribe(
            audio_array,
            language=language,
            task="transcribe"  # Not translate
        )

        elapsed_ms = int((time.time() - start) * 1000)

        # Extract confidence score from segments
        confidence = self._calculate_confidence(result.get("segments", []))

        return {
            "text": result["text"].strip(),
            "confidence": confidence,
            "language": language,
            "duration_ms": elapsed_ms
        }

    def _calculate_confidence(self, segments: list) -> float:
        """Calculate average confidence from segment probabilities"""
        if not segments:
            return 0.0

        # Average probability across all segments
        total_prob = sum(seg.get("avg_logprob", 0.0) for seg in segments)
        avg_prob = total_prob / len(segments)

        # Convert log probability to confidence (0.0-1.0)
        confidence = np.exp(avg_prob)
        return min(max(confidence, 0.0), 1.0)

    def validate_confidence(self, confidence: float, threshold: float = 0.60) -> bool:
        """Check if confidence meets minimum threshold"""
        return confidence >= threshold
```

**Implementation steps**:
1. Install `whisper-cpp-python`: `pip install whisper-cpp-python`
2. Download Whisper base model: `python scripts/download_whisper_model.py`
3. Write test for `WhisperSTTService`
4. Implement service
5. Integrate into audio processing pipeline

**Download script** (`scripts/download_whisper_model.py`):
```python
import urllib.request
from pathlib import Path

MODELS = {
    "base": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"
}

def download_model(model_name: str = "base"):
    models_dir = Path("pc-agent/models")
    models_dir.mkdir(exist_ok=True)

    url = MODELS[model_name]
    output_path = models_dir / f"ggml-{model_name}.bin"

    if output_path.exists():
        print(f"Model already exists: {output_path}")
        return

    print(f"Downloading Whisper {model_name} model...")
    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded to: {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="base", choices=["base"])
    args = parser.parse_args()
    download_model(args.model)
```

---

### Priority 5: Claude API Command Interpreter (T048)

#### Task 5A: Claude API Integration with MCP Tools
**File**: `pc-agent/src/services/command_interpreter.py`
**Time estimate**: 5 hours
**Prerequisites**: MCP tool schemas from contracts/

```python
# pc-agent/src/services/command_interpreter.py
import anthropic
import json
from typing import Dict, Any
import asyncio

class ClaudeCommandInterpreter:
    """Interpret voice commands using Claude API with MCP tool routing (T048)"""

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4"
        self.max_retries = 3
        self.retry_timeout = 30  # seconds

        # Load MCP tool definitions
        self.tools = self._load_mcp_tools()

    def _load_mcp_tools(self) -> list:
        """Load MCP tool schemas from contracts/mcp-tools-schema.json"""
        with open("specs/001-voice-pc-control/contracts/mcp-tools-schema.json") as f:
            schema = json.load(f)

        # Convert to Claude tool format
        return [
            {
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": tool["inputSchema"]
            }
            for tool in schema["tools"]
        ]

    async def interpret_command(
        self,
        transcription: str,
        command_history: list = None
    ) -> Dict[str, Any]:
        """
        Interpret voice command and determine PC action

        Args:
            transcription: Turkish text from STT (may include English technical terms)
            command_history: Recent commands for context (last 5)

        Returns:
            {
                "action": {
                    "actionType": "system" | "browser" | "query",
                    "operation": str,
                    "parameters": dict,
                    "requiresConfirmation": bool
                },
                "confidence": float,
                "reasoning": str
            }
        """
        # Build prompt with Turkish context
        system_prompt = """Sen bir Türkçe sesli komut yorumlay1c1s1s1n.
Kullan1c1 Türkçe komutlar verir, baz1 teknik terimler 0ngilizce olabilir (Chrome, Notepad, volume gibi).
Komutu analiz et ve uygun MCP tool'u seç.

Örnek komutlar:
- "Chrome'u aç" -> browser_navigate tool
- "sesi yüzde 50'ye ayarla" -> adjust_volume tool
- "Python eitimleri ara" -> browser_search tool
- "özgeçmi_imi bul" -> find_files tool

Sistem dizinlerinden (C:\\Windows, C:\\Program Files) dosya silme requiresConfirmation=true olmal1."""

        # Add command history for context
        context_messages = []
        if command_history:
            context_messages.append({
                "role": "user",
                "content": f"Son komutlar: {', '.join(command_history)}"
            })

        # Interpret command with retries
        for attempt in range(self.max_retries):
            try:
                response = await self._call_claude_with_tools(
                    system_prompt=system_prompt,
                    user_message=transcription,
                    context_messages=context_messages
                )
                return response

            except anthropic.APIConnectionError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Claude API unavailable, retry {attempt+1}/{self.max_retries} after {wait_time}s")
                    await asyncio.sleep(wait_time)
                else:
                    # Max retries reached
                    raise CommandInterpretationError(
                        "LLM_UNAVAILABLE",
                        "Komut yorumlama servisi kullan1lam1yor. Lütfen tekrar deneyin."
                    )

    async def _call_claude_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        context_messages: list
    ) -> Dict[str, Any]:
        """Call Claude API with MCP tools"""
        messages = context_messages + [{
            "role": "user",
            "content": user_message
        }]

        response = await asyncio.to_thread(
            self.client.messages.create,
            model=self.model,
            max_tokens=1024,
            system=system_prompt,
            messages=messages,
            tools=self.tools
        )

        # Extract tool use from response
        tool_use = None
        for content_block in response.content:
            if content_block.type == "tool_use":
                tool_use = content_block
                break

        if not tool_use:
            raise CommandInterpretationError(
                "INTERPRETATION_FAILED",
                "Komut anla_1lamad1. Lütfen tekrar edin."
            )

        # Map tool to action
        action = self._map_tool_to_action(tool_use)

        # Check if requires confirmation (system directory file deletion)
        action["requiresConfirmation"] = self._check_confirmation_required(action)

        return {
            "action": action,
            "confidence": 0.95,  # Claude API confidence is implicit
            "reasoning": response.stop_reason
        }

    def _map_tool_to_action(self, tool_use) -> Dict[str, Any]:
        """Map Claude tool use to Action model"""
        tool_name = tool_use.name
        tool_input = tool_use.input

        # Determine action type from tool category
        if tool_name.startswith("browser_"):
            action_type = "browser"
        elif tool_name in ["launch_application", "adjust_volume", "find_files", "delete_file", "query_system_info"]:
            action_type = "system"
        else:
            action_type = "query"

        return {
            "actionType": action_type,
            "operation": tool_name,
            "parameters": tool_input
        }

    def _check_confirmation_required(self, action: Dict[str, Any]) -> bool:
        """Check if action requires user confirmation"""
        if action["operation"] == "delete_file":
            path = action["parameters"].get("path", "")
            # Require confirmation for system directories
            system_dirs = ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"]
            return any(path.startswith(sysdir) for sysdir in system_dirs)

        return False

class CommandInterpretationError(Exception):
    def __init__(self, error_code: str, message_tr: str):
        self.error_code = error_code
        self.message_tr = message_tr
        super().__init__(message_tr)
```

**Implementation steps**:
1. Write test for command interpretation
2. Get Claude API key: `export CLAUDE_API_KEY=...`
3. Implement `ClaudeCommandInterpreter`
4. Test with Turkish commands
5. Integrate into voice command pipeline

---

### Priority 6: Quick Settings Tile (T051)

#### Task 6A: Android Quick Settings Tile Service
**File**: `android/app/src/main/java/com/pccontrol/voice/presentation/QuickSettingsTileService.kt`
**Time estimate**: 3 hours

```kotlin
// QuickSettingsTileService.kt
package com.pccontrol.voice.presentation

import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.content.Intent
import com.pccontrol.voice.domain.services.VoiceAssistantService
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class QuickSettingsTileService : TileService() {

    override fun onStartListening() {
        super.onStartListening()
        updateTileState()
    }

    override fun onClick() {
        super.onClick()

        val tile = qsTile
        when (tile.state) {
            Tile.STATE_INACTIVE -> {
                // Start voice assistant service
                startVoiceAssistant()
                tile.state = Tile.STATE_ACTIVE
                tile.label = "Dinliyor..."
            }
            Tile.STATE_ACTIVE -> {
                // Stop voice assistant service
                stopVoiceAssistant()
                tile.state = Tile.STATE_INACTIVE
                tile.label = "Sesli Asistan"
            }
        }

        tile.updateTile()
    }

    private fun startVoiceAssistant() {
        val intent = Intent(this, VoiceAssistantService::class.java).apply {
            action = VoiceAssistantService.ACTION_START_LISTENING
        }
        startForegroundService(intent)
    }

    private fun stopVoiceAssistant() {
        val intent = Intent(this, VoiceAssistantService::class.java).apply {
            action = VoiceAssistantService.ACTION_STOP_LISTENING
        }
        startService(intent)
    }

    private fun updateTileState() {
        val tile = qsTile ?: return

        // Check if service is running
        val isServiceActive = VoiceAssistantService.isRunning()

        tile.state = if (isServiceActive) {
            Tile.STATE_ACTIVE
        } else {
            Tile.STATE_INACTIVE
        }

        tile.label = if (isServiceActive) {
            "Dinliyor..."
        } else {
            "Sesli Asistan"
        }

        tile.updateTile()
    }
}
```

**Manifest addition** (`AndroidManifest.xml`):
```xml
<service
    android:name=".presentation.QuickSettingsTileService"
    android:icon="@drawable/ic_microphone"
    android:label="@string/quick_settings_label"
    android:permission="android.permission.BIND_QUICK_SETTINGS_TILE"
    android:exported="true">
    <intent-filter>
        <action android:name="android.service.quicksettings.action.QS_TILE" />
    </intent-filter>
</service>
```

**Implementation steps**:
1. Create `QuickSettingsTileService`
2. Add service to AndroidManifest.xml
3. Create microphone icon drawable
4. Test tile in Quick Settings panel
5. Connect to VoiceAssistantService (Priority 7)

---

### Priority 7: Foreground Service (T053)

#### Task 7A: Voice Assistant Foreground Service
**File**: `android/app/src/main/java/com/pccontrol/voice/domain/services/VoiceAssistantService.kt`
**Time estimate**: 4 hours
**Purpose**: Enable background operation with screen locked (FR-014)

```kotlin
// VoiceAssistantService.kt
package com.pccontrol.voice.domain.services

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.pccontrol.voice.MainActivity
import com.pccontrol.voice.R
import com.pccontrol.voice.audio.AudioRecorder
import com.pccontrol.voice.network.WebSocketManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.*
import javax.inject.Inject

@AndroidEntryPoint
class VoiceAssistantService : Service() {

    @Inject lateinit var audioRecorder: AudioRecorder
    @Inject lateinit var webSocketManager: WebSocketManager

    private val serviceScope = CoroutineScope(Dispatchers.Default + SupervisorJob())
    private var isListening = false

    companion object {
        const val ACTION_START_LISTENING = "com.pccontrol.voice.START_LISTENING"
        const val ACTION_STOP_LISTENING = "com.pccontrol.voice.STOP_LISTENING"
        const val NOTIFICATION_ID = 1001
        const val CHANNEL_ID = "voice_assistant_channel"

        private var serviceInstance: VoiceAssistantService? = null

        fun isRunning(): Boolean = serviceInstance != null
    }

    override fun onCreate() {
        super.onCreate()
        serviceInstance = this
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_LISTENING -> {
                startListening()
            }
            ACTION_STOP_LISTENING -> {
                stopListening()
            }
        }

        return START_STICKY // Restart if killed by system
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        serviceInstance = null
        stopListening()
        serviceScope.cancel()
    }

    private fun startListening() {
        if (isListening) return

        isListening = true

        // Start foreground service with notification
        val notification = createNotification("Dinliyor...")
        startForeground(NOTIFICATION_ID, notification)

        // Start audio recording and WebSocket connection
        serviceScope.launch {
            try {
                webSocketManager.connect()
                audioRecorder.startRecording { audioData ->
                    // Stream audio to PC
                    webSocketManager.sendAudioFrame(audioData)
                }
            } catch (e: Exception) {
                // Handle error
                updateNotification("Hata: ${e.message}")
            }
        }
    }

    private fun stopListening() {
        if (!isListening) return

        isListening = false

        serviceScope.launch {
            audioRecorder.stopRecording()
            webSocketManager.disconnect()
        }

        // Update notification or stop foreground
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Sesli Asistan",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Sesli komutlar dinleniyor"
            }

            val notificationManager = getSystemService(NotificationManager::class.java)
            notificationManager.createNotificationChannel(channel)
        }
    }

    private fun createNotification(contentText: String): Notification {
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Sesli Asistan")
            .setContentText(contentText)
            .setSmallIcon(R.drawable.ic_microphone)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(contentText: String) {
        val notification = createNotification(contentText)
        val notificationManager = getSystemService(NotificationManager::class.java)
        notificationManager.notify(NOTIFICATION_ID, notification)
    }
}
```

**Manifest permissions**:
```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE" />
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />

<service
    android:name=".domain.services.VoiceAssistantService"
    android:foregroundServiceType="microphone"
    android:exported="false" />
```

**Implementation steps**:
1. Create `VoiceAssistantService`
2. Add permissions to AndroidManifest
3. Test with screen locked
4. Connect to Quick Settings Tile (Priority 6)
5. Integrate audio recording and WebSocket

---

## Summary & Next Actions

### Immediate Actions (This Week)
1.  **Write all missing TDD tests** (Tasks 1A, 1B, 1C) - **2 days**
2. =' **Implement networking tasks** (Tasks 2A, 2B, 2C) - **1 day**
3. < **Implement Wake-on-LAN** (Task 3A) - **0.5 day**

### Critical Path (Next Week)
4. <¤ **Integrate Whisper.cpp** (Task 4A) - **1 day**
5. > **Integrate Claude API** (Task 5A) - **1 day**
6. =ñ **Quick Settings Tile** (Task 6A) - **0.5 day**
7. = **Foreground Service** (Task 7A) - **1 day**

### Estimated Timeline to MVP
- **Phase 2 completion**: 1 day (networking tasks)
- **User Story 4 completion**: 2 days (pairing workflow)
- **User Story 1 completion**: 5 days (WoL + Whisper + Claude + UI)
- **Total**: ~8 working days to functional MVP

### Success Criteria
-  All tests pass (80% coverage)
-  Can wake PC from sleep
-  Can execute Turkish voice command "Chrome'u aç"
-  Quick Settings tile works with screen locked
-  <2 second end-to-end latency
-  Constitution compliance (TDD, security, performance)

---

**CRITICAL REMINDER**: Do not proceed with implementation until tests are written and failing. This is a constitution requirement (Principle II: TDD Non-Negotiable).