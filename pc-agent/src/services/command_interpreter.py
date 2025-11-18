"""
Command Interpretation Service using Claude API with MCP Tool Routing

This service handles:
- Natural language command interpretation using Claude API
- Mixed Turkish/English technical term processing
- MCP tool routing for system and browser automation
- Context awareness from command history
- Action type classification and parameter extraction
- Error handling and fallback strategies

Following requirements from spec and test T043.
"""

import asyncio
import logging
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import aiohttp
import anthropic

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of actions that can be performed."""
    SYSTEM = "system"
    BROWSER = "browser"
    QUERY = "query"
    UNKNOWN = "unknown"


class InterpretationStatus(Enum):
    """Status of command interpretation."""
    SUCCESS = "success"
    NEEDS_CLARIFICATION = "needs_clarification"
    FAILED = "failed"
    QUEUED = "queued"


@dataclass
class CommandAction:
    """Represents an action to be performed based on voice command."""
    action_type: ActionType
    operation: str
    parameters: Dict[str, Any]
    requires_confirmation: bool = False
    confirmation_message: Optional[str] = None
    confidence: float = 0.0
    context_used: Optional[Dict[str, Any]] = None


@dataclass
class CommandContext:
    """Context information for command interpretation."""
    previous_commands: List[Dict[str, Any]] = field(default_factory=list)
    active_applications: List[str] = field(default_factory=list)
    current_directory: str = ""
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class InterpretationResult:
    """Result of command interpretation."""
    status: InterpretationStatus
    action: Optional[CommandAction]
    confidence: float
    processing_time_ms: float
    clarification_question: Optional[str] = None
    clarification_options: Optional[List[str]] = None
    error: Optional[str] = None
    fallback_suggestion: Optional[str] = None


class CommandInterpreter:
    """
    Command interpretation service using Claude API with MCP tool routing.

    Features:
    - Turkish language understanding with English technical terms
    - MCP tool routing for system and browser operations
    - Context awareness from previous commands
    - Action classification and parameter extraction
    - Confidence scoring and validation
    - Error handling with Turkish messages
    - Queue-and-retry for API unavailability
    """

    def __init__(self, claude_api_key: str, max_context_commands: int = 5):
        """
        Initialize command interpreter.

        Args:
            claude_api_key: Claude API key for authentication
            max_context_commands: Maximum number of previous commands to use as context
        """
        self.claude_api_key = claude_api_key
        self.max_context_commands = max_context_commands
        self.client = anthropic.AsyncAnthropic(api_key=claude_api_key)

        # Command queue for retry logic
        self.command_queue: List[Dict[str, Any]] = []
        self.queue_lock = asyncio.Lock()

        # MCP tool configurations
        self.mcp_tools = self._initialize_mcp_tools()

        # Turkish command patterns
        self.command_patterns = self._initialize_turkish_patterns()

        # Metrics
        self.total_interpretations = 0
        self.successful_interpretations = 0
        self.queued_interpretations = 0

        logger.info("Command interpreter initialized with Claude API")

    def _initialize_mcp_tools(self) -> Dict[str, Dict[str, Any]]:
        """Initialize MCP tool definitions."""
        return {
            "system": {
                "launch_application": {
                    "description": "Launch an application on Windows",
                    "parameters": {
                        "application": {"type": "string", "description": "Application name or path"},
                        "arguments": {"type": "array", "description": "Command line arguments", "items": {"type": "string"}}
                    }
                },
                "adjust_volume": {
                    "description": "Adjust system volume",
                    "parameters": {
                        "level": {"type": "integer", "min": 0, "max": 100, "description": "Volume level (0-100)"},
                        "direction": {"type": "string", "enum": ["up", "down", "mute", "unmute"], "description": "Volume adjustment direction"}
                    }
                },
                "find_files": {
                    "description": "Search for files on the system",
                    "parameters": {
                        "pattern": {"type": "string", "description": "File search pattern"},
                        "directory": {"type": "string", "description": "Search directory (optional)"},
                        "recursive": {"type": "boolean", "description": "Search recursively", "default": false}
                    }
                },
                "delete_file": {
                    "description": "Delete a file (requires confirmation)",
                    "parameters": {
                        "path": {"type": "string", "description": "File path to delete"},
                        "force": {"type": "boolean", "description": "Force deletion without confirmation", "default": false}
                    }
                },
                "query_system_info": {
                    "description": "Get system information",
                    "parameters": {
                        "category": {"type": "string", "enum": ["general", "hardware", "software", "network"], "description": "Information category"}
                    }
                }
            },
            "browser": {
                "browser_navigate": {
                    "description": "Navigate browser to a URL",
                    "parameters": {
                        "url": {"type": "string", "description": "URL to navigate to"},
                        "new_tab": {"type": "boolean", "description": "Open in new tab", "default": False}
                    }
                },
                "browser_search": {
                    "description": "Search on the web",
                    "parameters": {
                        "query": {"type": "string", "description": "Search query"},
                        "engine": {"type": "string", "enum": ["google", "bing", "duckduckgo"], "description": "Search engine", "default": "google"}
                    }
                },
                "browser_extract_content": {
                    "description": "Extract content from current web page",
                    "parameters": {
                        "content_type": {"type": "string", "enum": ["text", "links", "images"], "description": "Type of content to extract"}
                    }
                },
                "browser_interact": {
                    "description": "Interact with web page elements",
                    "parameters": {
                        "action": {"type": "string", "enum": ["click", "type", "scroll"], "description": "Interaction type"},
                        "selector": {"type": "string", "description": "CSS selector for element"},
                        "text": {"type": "string", "description": "Text to type (for 'type' action)"}
                    }
                }
            }
        }

    def _initialize_turkish_patterns(self) -> Dict[str, List[str]]:
        """Initialize Turkish command patterns with synonyms."""
        return {
            "launch": [
                "aç", "başlat", "çalıştır", " çalıştır",
                "uygulama aç", "program aç", "uygulama başlat"
            ],
            "close": [
                "kapat", "çık", "kapat", "sonlandır",
                "pencereyi kapat", "sekme kapat"
            ],
            "search": [
                "ara", "bul", "ara", "yaz ara",
                "internetten ara", "google'da ara"
            ],
            "navigate": [
                "git", "git", "aç", "ulaş",
                "siteye git", "sayfaya git"
            ],
            "volume_up": [
                "sesi artır", "ses yükselt", "ses aç",
                "sesi yükselt", "sesi aç"
            ],
            "volume_down": [
                "sesi azalt", "ses kıs", "ses kıs",
                "sesi düşür", "sesi azalt"
            ],
            "mute": [
                "sessize al", "sesi kapat", "sessiz",
                "sesi kapat", "sessize al"
            ],
            "find": [
                "bul", "ara", "bul", "ara",
                "dosya bul", "klasör bul", "araştır"
            ],
            "delete": [
                "sil", "kaldır", "sil", "imha et",
                "dosya sil", "kalıcı sil"
            ],
            "info": [
                "bilgilerini göster", "durumu göster", "bilgi ver",
                "hakkında bilgi", "özelliklerini göster"
            ]
        }

    async def interpret_command(
        self,
        text: str,
        context: Optional[CommandContext] = None
    ) -> InterpretationResult:
        """
        Interpret voice command text into actionable commands.

        Args:
            text: Transcribed voice command text
            context: Command context from previous interactions

        Returns:
            InterpretationResult with action to perform
        """
        start_time = asyncio.get_event_loop().time()
        self.total_interpretations += 1

        try:
            # Clean and validate input
            if not text or not text.strip():
                return InterpretationResult(
                    status=InterpretationStatus.FAILED,
                    action=None,
                    confidence=0.0,
                    processing_time_ms=0.0,
                    error="Boş komut metni"
                )

            text = text.strip()

            # Prepare context
            if context is None:
                context = CommandContext()

            # Try pattern-based interpretation first (faster, more reliable for common commands)
            pattern_result = await self._interpret_with_patterns(text, context)
            if pattern_result and pattern_result.confidence > 0.7:
                processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
                pattern_result.processing_time_ms = processing_time
                self.successful_interpretations += 1
                return pattern_result

            # Use Claude API for complex commands
            claude_result = await self._interpret_with_claude(text, context)
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000
            claude_result.processing_time_ms = processing_time

            if claude_result.status == InterpretationStatus.SUCCESS:
                self.successful_interpretations += 1

            return claude_result

        except Exception as e:
            logger.error(f"Error interpreting command '{text}': {e}", exc_info=True)
            processing_time = (asyncio.get_event_loop().time() - start_time) * 1000

            # Try to queue command for retry if API unavailable
            if "api" in str(e).lower() or "network" in str(e).lower():
                queued_result = await self._queue_command_for_retry(text, context, processing_time)
                if queued_result:
                    return queued_result

            return InterpretationResult(
                status=InterpretationStatus.FAILED,
                action=None,
                confidence=0.0,
                processing_time_ms=processing_time,
                error=f"Komut yorumlama hatası: {str(e)}"
            )

    async def _interpret_with_patterns(
        self,
        text: str,
        context: CommandContext
    ) -> Optional[InterpretationResult]:
        """
        Interpret command using pattern matching.

        Args:
            text: Command text
            context: Command context

        Returns:
            InterpretationResult or None if no pattern matches
        """
        text_lower = text.lower()

        # Check for launch patterns
        for pattern in self.command_patterns["launch"]:
            if pattern in text_lower:
                app_name = self._extract_application_name(text, pattern)
                if app_name:
                    return InterpretationResult(
                        status=InterpretationStatus.SUCCESS,
                        action=CommandAction(
                            action_type=ActionType.SYSTEM,
                            operation="launch_application",
                            parameters={"application": app_name, "arguments": []},
                            confidence=0.9
                        ),
                        confidence=0.9,
                        processing_time_ms=0.0
                    )

        # Check for browser search patterns
        for pattern in self.command_patterns["search"]:
            if pattern in text_lower:
                search_query = self._extract_search_query(text, pattern)
                if search_query:
                    return InterpretationResult(
                        status=InterpretationStatus.SUCCESS,
                        action=CommandAction(
                            action_type=ActionType.BROWSER,
                            operation="browser_search",
                            parameters={"query": search_query, "engine": "google"},
                            confidence=0.85
                        ),
                        confidence=0.85,
                        processing_time_ms=0.0
                    )

        # Check for volume adjustment patterns
        for pattern in self.command_patterns["volume_up"]:
            if pattern in text_lower:
                return InterpretationResult(
                    status=InterpretationStatus.SUCCESS,
                    action=CommandAction(
                        action_type=ActionType.SYSTEM,
                        operation="adjust_volume",
                        parameters={"direction": "up", "level": None},
                        confidence=0.9
                    ),
                    confidence=0.9,
                    processing_time_ms=0.0
                )

        for pattern in self.command_patterns["volume_down"]:
            if pattern in text_lower:
                return InterpretationResult(
                    status=InterpretationStatus.SUCCESS,
                    action=CommandAction(
                        action_type=ActionType.SYSTEM,
                        operation="adjust_volume",
                        parameters={"direction": "down", "level": None},
                        confidence=0.9
                    ),
                    confidence=0.9,
                    processing_time_ms=0.0
                )

        # Check for mute patterns
        for pattern in self.command_patterns["mute"]:
            if pattern in text_lower:
                return InterpretationResult(
                    status=InterpretationStatus.SUCCESS,
                    action=CommandAction(
                        action_type=ActionType.SYSTEM,
                        operation="adjust_volume",
                        parameters={"direction": "mute", "level": 0},
                        confidence=0.9
                    ),
                    confidence=0.9,
                    processing_time_ms=0.0
                )

        return None  # No pattern matched

    async def _interpret_with_claude(
        self,
        text: str,
        context: CommandContext
    ) -> InterpretationResult:
        """
        Interpret command using Claude API with MCP tool definitions.

        Args:
            text: Command text
            context: Command context

        Returns:
            InterpretationResult
        """
        try:
            # Build prompt with context and MCP tools
            prompt = self._build_claude_prompt(text, context)

            # Create system message with MCP tools
            system_message = self._build_system_message()

            response = await self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                system=system_message,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse Claude's response
            return self._parse_claude_response(response.content[0].text, context)

        except anthropic.RateLimitError:
            logger.warning("Claude API rate limit exceeded")
            raise Exception("API rate limit exceeded")
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise Exception(f"Claude API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}", exc_info=True)
            raise Exception(f"API çağrı hatası: {str(e)}")

    def _build_claude_prompt(self, text: str, context: CommandContext) -> str:
        """Build prompt for Claude with context information."""
        prompt = f"""
Bu komutu Türkçe olarak yorumla ve uygun MCP araçlarını kullanarak eylem planı oluştur:

Komut: "{text}"

Dil: Türkçe (İngilizce teknik terimler korunmalı)

Kontext Bilgisi:
- Önceki komutlar: {len(context.previous_commands)} adet
- Aktif uygulamalar: {context.active_applications}
- Tarih: {context.timestamp.strftime('%d.%m.%Y %H:%M')}

Önceki Komutlar (en son {self.max_context_commands}):
"""
        # Add recent commands for context
        for i, cmd in enumerate(context.previous_commands[-self.max_context_commands:]):
            prompt += f"\n{i+1}. {cmd.get('text', '')} -> {cmd.get('result', 'processed')}"

        prompt += """

Kurallar:
1. Türkçe komutları anla ve İngilizce teknik terimleri koru (örn: "Chrome'u aç", "Windows'a geç")
2. Belirsiz komutlar için netleştirme sorusu sor
3. Tehlikeli işlemler (dosya silme, sistem değişikliği) için onay iste
4. JSON formatında cevap ver

JSON Formatı:
{
  "action_type": "system|browser|query",
  "operation": "MCP operation name",
  "parameters": {},
  "requires_confirmation": false,
  "confirmation_message": "Onay mesajı (gerekirse)",
  "clarification_needed": false,
  "clarification_question": "Netleştirme sorusu (gerekirse)",
  "clarification_options": ["seçenek1", "seçenek2"],
  "confidence": 0.0-1.0,
  "context_used": {"previous_command": "..."},
  "fallback_suggestion": "Alternatif öneri (gerekirse)"
}
"""

        return prompt

    def _build_system_message(self) -> str:
        """Build system message with MCP tool definitions."""
        tools_json = json.dumps(self.mcp_tools, indent=2, ensure_ascii=False)

        return f"""
Sen bir PC sesli komut asistanısın. Kullanıcı Türkçe konuşuyor ama İngilizce teknik terimler kullanabilir.

MCP Araçları:
{tools_json}

Görevlerin:
1. Kullanıcının niyetini anla
2. Uygun MCP aracını seç
3. Parametreleri doğru çıkar
4. Türkçe hata mesajları ver
5. Güvenli olmayan işlemler için onay iste

Örnekler:
- "Chrome'u aç" → system/launch_application
- "hava durumu ara" → browser/browser_search
- "sesi artır" → system/adjust_volume
- "belgeler klasörünü aç" → system/launch_application

Her zaman JSON formatında yanıt ver. Netleştirme gereken durumlar için clarification_needed true yap.
"""

    def _parse_claude_response(
        self,
        response_text: str,
        context: CommandContext
    ) -> InterpretationResult:
        """Parse Claude's JSON response."""
        try:
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")

            json_str = json_match.group()
            response_data = json.loads(json_str)

            # Validate required fields
            if "action_type" not in response_data or "operation" not in response_data:
                raise ValueError("Missing required fields in response")

            # Create action
            action = CommandAction(
                action_type=ActionType(response_data["action_type"]),
                operation=response_data["operation"],
                parameters=response_data.get("parameters", {}),
                requires_confirmation=response_data.get("requires_confirmation", False),
                confirmation_message=response_data.get("confirmation_message"),
                confidence=response_data.get("confidence", 0.5),
                context_used=response_data.get("context_used")
            )

            # Check if clarification is needed
            if response_data.get("clarification_needed", False):
                return InterpretationResult(
                    status=InterpretationStatus.NEEDS_CLARIFICATION,
                    action=action,
                    confidence=response_data.get("confidence", 0.3),
                    processing_time_ms=0.0,
                    clarification_question=response_data.get("clarification_question"),
                    clarification_options=response_data.get("clarification_options", [])
                )

            return InterpretationResult(
                status=InterpretationStatus.SUCCESS,
                action=action,
                confidence=response_data.get("confidence", 0.5),
                processing_time_ms=0.0,
                fallback_suggestion=response_data.get("fallback_suggestion")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude JSON response: {e}")
            return InterpretationResult(
                status=InterpretationStatus.FAILED,
                action=None,
                confidence=0.0,
                processing_time_ms=0.0,
                error="Claude yanıtı ayrıştırılamadı"
            )
        except Exception as e:
            logger.error(f"Error parsing Claude response: {e}", exc_info=True)
            return InterpretationResult(
                status=InterpretationStatus.FAILED,
                action=None,
                confidence=0.0,
                processing_time_ms=0.0,
                error=f"Yanıt ayrıştırma hatası: {str(e)}"
            )

    def _extract_application_name(self, text: str, pattern: str) -> Optional[str]:
        """Extract application name from launch command."""
        # Remove the pattern and common prefixes/suffixes
        clean_text = text.lower().replace(pattern, "").strip()

        # Common application mappings
        app_mappings = {
            "chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "edge": "msedge.exe",
            "word": "winword.exe",
            "excel": "excel.exe",
            "powerpoint": "powerpnt.exe",
            "notepad": "notepad.exe",
            "calc": "calc.exe",
            "paint": "mspaint.exe"
        }

        # Check for exact matches
        for key, value in app_mappings.items():
            if key in clean_text:
                return value

        # Return the clean text as potential app name
        return clean_text if clean_text else None

    def _extract_search_query(self, text: str, pattern: str) -> Optional[str]:
        """Extract search query from search command."""
        # Remove the pattern and clean up
        clean_text = text.replace(pattern, "").strip()

        # Remove common prefixes like "google'da" -> "google'da"
        if "google" in clean_text.lower():
            clean_text = re.sub(r'google[\'"][^\s]*\s*', '', clean_text, flags=re.IGNORECASE)

        return clean_text.strip() if clean_text.strip() else None

    async def _queue_command_for_retry(
        self,
        text: str,
        context: CommandContext,
        processing_time: float
    ) -> Optional[InterpretationResult]:
        """Queue command for retry when API is unavailable."""
        async with self.queue_lock:
            if len(self.command_queue) >= 30:  # Max queue size
                logger.warning("Command queue full, dropping command")
                return None

            queued_command = {
                "text": text,
                "context": context,
                "timestamp": datetime.now(),
                "retry_count": 0
            }

            self.command_queue.append(queued_command)
            self.queued_interpretations += 1

            logger.info(f"Command queued for retry: {text[:50]}...")

            return InterpretationResult(
                status=InterpretationStatus.QUEUED,
                action=None,
                confidence=0.0,
                processing_time_ms=processing_time,
                fallback_suggestion="İnternet bağlantısı kontrol ediliyor, lütfen bekleyin..."
            )

    async def process_queued_commands(self) -> List[InterpretationResult]:
        """
        Process queued commands when API becomes available.

        Returns:
            List of interpretation results
        """
        results = []

        async with self.queue_lock:
            if not self.command_queue:
                return results

            # Make a copy of queued commands
            queued_commands = self.command_queue.copy()
            self.command_queue.clear()

        for command in queued_commands:
            # Check if command is not too old (5 minutes)
            if datetime.now() - command["timestamp"] > timedelta(minutes=5):
                continue

            # Check retry count
            if command["retry_count"] >= 3:
                logger.warning(f"Command exceeded retry limit: {command['text'][:50]}...")
                continue

            command["retry_count"] += 1

            try:
                # Re-interpret the command
                result = await self.interpret_command(
                    command["text"],
                    command["context"]
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Error retrying queued command: {e}")
                # Re-queue if possible
                if command["retry_count"] < 3:
                    async with self.queue_lock:
                        if len(self.command_queue) < 30:
                            self.command_queue.append(command)

        return results

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queue_size": len(self.command_queue),
            "max_queue_size": 30,
            "total_queued": self.queued_interpretations,
            "oldest_command_age": None if not self.command_queue else (
                datetime.now() - self.command_queue[0]["timestamp"]
            ).total_seconds()
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get interpretation metrics."""
        return {
            "total_interpretations": self.total_interpretations,
            "successful_interpretations": self.successful_interpretations,
            "queued_interpretations": self.queued_interpretations,
            "success_rate": (
                self.successful_interpretations / max(1, self.total_interpretations) * 100
            ),
            "queue_status": self.get_queue_status()
        }

    def reset_metrics(self):
        """Reset interpretation metrics."""
        self.total_interpretations = 0
        self.successful_interpretations = 0
        self.queued_interpretations = 0
        logger.info("Command interpreter metrics reset")


# Global service instance (will be initialized with API key)
command_interpreter = None


def initialize_command_interpreter(claude_api_key: str) -> CommandInterpreter:
    """Initialize global command interpreter instance."""
    global command_interpreter
    command_interpreter = CommandInterpreter(claude_api_key)
    return command_interpreter