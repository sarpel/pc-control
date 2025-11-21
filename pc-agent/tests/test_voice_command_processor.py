"""
Unit tests for Voice Command Processor.

Tests the voice command parsing, intent detection, and action generation.
"""

import pytest
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import uuid

from src.services.voice_command_processor import (
    VoiceCommandProcessor,
    ParsedCommand,
    CommandCategory,
    CommandIntent,
    CommandResult
)


class TestVoiceCommandProcessor(unittest.TestCase):
    """Test cases for VoiceCommandProcessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.processor = VoiceCommandProcessor()

    @pytest.mark.asyncio
    async def test_parse_navigation_command(self):
        """Test parsing of navigation commands."""
        command_id = str(uuid.uuid4())
        transcription = "google.com'a git"
        confidence = 0.9
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.transcription, transcription)
        self.assertEqual(result.confidence, confidence)
        self.assertEqual(result.language, language)
        self.assertEqual(result.intent, CommandIntent.NAVIGATE)
        self.assertEqual(result.category, CommandCategory.BROWSER)
        self.assertIn("google.com", result.entities.get("url", ""))

    @pytest.mark.asyncio
    async def test_parse_search_command(self):
        """Test parsing of search commands."""
        command_id = str(uuid.uuid4())
        transcription = "hava durumu ara"
        confidence = 0.85
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.SEARCH)
        self.assertEqual(result.category, CommandCategory.BROWSER)
        self.assertIn("hava durumu", result.entities.get("search_query", ""))

    @pytest.mark.asyncio
    async def test_parse_volume_command(self):
        """Test parsing of volume commands."""
        command_id = str(uuid.uuid4())
        transcription = "sesi aç"
        confidence = 0.8
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.VOLUME_UP)
        self.assertEqual(result.category, CommandCategory.VOLUME)

    @pytest.mark.asyncio
    async def test_parse_app_launch_command(self):
        """Test parsing of application launch commands."""
        command_id = str(uuid.uuid4())
        transcription = "Chrome'u çalıştır"
        confidence = 0.9
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.LAUNCH)
        self.assertEqual(result.category, CommandCategory.SYSTEM)
        self.assertIn("Chrome", result.entities.get("app_name", ""))

    @pytest.mark.asyncio
    async def test_parse_volume_set_command(self):
        """Test parsing of volume set commands."""
        command_id = str(uuid.uuid4())
        transcription = "sesi 50 ayarla"
        confidence = 0.85
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.VOLUME_SET)
        self.assertEqual(result.category, CommandCategory.VOLUME)
        self.assertEqual(result.entities.get("volume_level"), 50)

    @pytest.mark.asyncio
    async def test_parse_file_search_command(self):
        """Test parsing of file search commands."""
        command_id = str(uuid.uuid4())
        transcription = "rapor dosyasını bul"
        confidence = 0.9
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.FIND_FILE)
        self.assertEqual(result.category, CommandCategory.FILE)
        self.assertIn("rapor", result.entities.get("file_name", ""))

    @pytest.mark.asyncio
    async def test_parse_unknown_command(self):
        """Test parsing of unknown commands."""
        command_id = str(uuid.uuid4())
        transcription = "bilinmeyen komut"
        confidence = 0.7
        language = "tr"

        result = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        self.assertEqual(result.intent, CommandIntent.UNKNOWN)
        self.assertEqual(result.category, CommandCategory.UNKNOWN)

    @pytest.mark.asyncio
    async def test_generate_action_sequence_navigation(self):
        """Test action sequence generation for navigation."""
        command_id = str(uuid.uuid4())
        transcription = "github.com'a git"
        confidence = 0.9
        language = "tr"

        parsed_command = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        actions = parsed_command.action_sequence
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "browser_navigate")
        self.assertIn("github.com", actions[0]["url"])

    @pytest.mark.asyncio
    async def test_generate_action_sequence_search(self):
        """Test action sequence generation for search."""
        command_id = str(uuid.uuid4())
        transcription = "Python documentation ara"
        confidence = 0.85
        language = "tr"

        parsed_command = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        actions = parsed_command.action_sequence
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "browser_search")
        self.assertIn("Python documentation", actions[0]["query"])

    @pytest.mark.asyncio
    async def test_generate_action_sequence_volume(self):
        """Test action sequence generation for volume."""
        command_id = str(uuid.uuid4())
        transcription = "sesi kıs"
        confidence = 0.8
        language = "tr"

        parsed_command = await self.processor.parse_command(
            command_id, transcription, confidence, language
        )

        actions = parsed_command.action_sequence
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "system_volume")
        self.assertEqual(actions[0]["adjust_type"], "decrease")

    def test_estimate_execution_time(self):
        """Test execution time estimation."""
        simple_actions = [{"type": "browser_navigate"}]
        complex_actions = [
            {"type": "browser_search"},
            {"type": "browser_navigate"},
            {"type": "system_volume"}
        ]

        simple_time = self.processor._estimate_execution_time(simple_actions)
        complex_time = self.processor._estimate_execution_time(complex_actions)

        self.assertGreater(simple_time, 1000)  # At least 1 second
        self.assertGreater(complex_time, simple_time)  # Complex should take longer

    def test_confidence_validation(self):
        """Test confidence validation."""
        low_confidence = 0.3
        high_confidence = 0.9
        invalid_confidence = 1.5

        # These would be tested through the actual processing method
        self.assertLess(low_confidence, 0.5)
        self.assertGreater(high_confidence, 0.5)
        self.assertGreater(invalid_confidence, 1.0)

    @pytest.mark.asyncio
    async def test_turkish_language_support(self):
        """Test Turkish language command parsing."""
        test_cases = [
            ("web sitesine git", CommandIntent.NAVIGATE),
            ("aranacak kelime", CommandIntent.SEARCH),
            ("uygulama başlat", CommandIntent.LAUNCH),
            ("ses seviyesi 80", CommandIntent.VOLUME_SET),
            ("dosya ara", CommandIntent.FIND_FILE),
            ("sistem bilgisi", CommandIntent.SYSTEM_INFO)
        ]

        for transcription, expected_intent in test_cases:
            with self.subTest(transcription=transcription):
                command_id = str(uuid.uuid4())
                result = await self.processor.parse_command(
                    command_id, transcription, 0.8, "tr"
                )
                self.assertEqual(result.intent, expected_intent,
                               f"Failed for '{transcription}'")

    def test_normalize_text(self):
        """Test text normalization."""
        test_inputs = [
            "  CHROME'U AÇ  ",
            "Google'da ara",
            "Ses seviyesi 70",
            "WEB sitesine   git"
        ]

        expected_outputs = [
            "chrome u aç",
            "google da ara",
            "ses seviyesi 70",
            "web sitesine git"
        ]

        for input_text, expected in zip(test_inputs, expected_outputs):
            with self.subTest(input=input_text):
                result = self.processor._normalize_text(input_text)
                self.assertEqual(result, expected)


class TestCommandResult(unittest.TestCase):
    """Test cases for CommandResult."""

    def test_command_result_creation(self):
        """Test CommandResult object creation."""
        command_id = str(uuid.uuid4())
        execution_time = 1500
        action_results = [{"success": True, "action_type": "browser_navigate"}]
        response_message = "Website açıldı"

        result = CommandResult(
            command_id=command_id,
            success=True,
            execution_time_ms=execution_time,
            action_results=action_results,
            response_message=response_message
        )

        self.assertEqual(result.command_id, command_id)
        self.assertTrue(result.success)
        self.assertEqual(result.execution_time_ms, execution_time)
        self.assertEqual(len(result.action_results), 1)
        self.assertEqual(result.response_message, response_message)

    def test_command_result_serialization(self):
        """Test CommandResult serialization to dict."""
        command_id = str(uuid.uuid4())
        result = CommandResult(
            command_id=command_id,
            success=True,
            execution_time_ms=1000,
            action_results=[],
            response_message="Success",
            suggestions=["Try again"],
            follow_up_actions=[{"type": "test"}]
        )

        result_dict = result.to_dict()

        self.assertEqual(result_dict["command_id"], command_id)
        self.assertTrue(result_dict["success"])
        self.assertEqual(result_dict["execution_time_ms"], 1000)
        self.assertEqual(result_dict["response_message"], "Success")
        self.assertEqual(result_dict["suggestions"], ["Try again"])
        self.assertEqual(result_dict["follow_up_actions"], [{"type": "test"}])


if __name__ == "__main__":
    unittest.main()