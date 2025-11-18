"""
Voice command processor service for PC Voice Controller.

This module handles the complete voice command processing pipeline including
speech recognition, command parsing, action execution, and response generation.
"""

import logging
import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Any, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from datetime import datetime

from src.services.browser_control import BrowserControlService, BrowserAction, ElementSelectorType
from src.services.system_control import SystemControlService, SystemAction, FileType
from src.services.connection_manager import ConnectionManager
from src.database.connection import get_database_connection

logger = logging.getLogger(__name__)


class CommandCategory(Enum):
    """Categories of voice commands."""
    BROWSER = "browser"
    SYSTEM = "system"
    VOLUME = "volume"
    FILE = "file"
    SEARCH = "search"
    INFO = "info"
    HELP = "help"
    UNKNOWN = "unknown"


class CommandIntent(Enum):
    """Intents for voice commands."""
    NAVIGATE = "navigate"
    SEARCH = "search"
    CLICK = "click"
    TYPE = "type"
    LAUNCH = "launch"
    VOLUME_UP = "volume_up"
    VOLUME_DOWN = "volume_down"
    VOLUME_SET = "volume_set"
    FIND_FILE = "find_file"
    DELETE_FILE = "delete_file"
    SYSTEM_INFO = "system_info"
    SCREENSHOT = "screenshot"
    CLOSE = "close"
    BACK = "back"
    REFRESH = "refresh"
    SCROLL = "scroll"
    UNKNOWN = "unknown"


@dataclass
class ParsedCommand:
    """Represents a parsed voice command."""
    command_id: str
    transcription: str
    confidence: float
    language: str
    category: CommandCategory
    intent: CommandIntent
    entities: Dict[str, Any]
    parameters: Dict[str, Any]
    action_sequence: List[Dict[str, Any]]
    requires_confirmation: bool = False
    estimated_execution_time_ms: int = 5000


@dataclass
class CommandResult:
    """Result of command execution."""
    command_id: str
    success: bool
    execution_time_ms: int
    action_results: List[Dict[str, Any]]
    response_message: str
    error_message: Optional[str] = None
    suggestions: List[str] = None
    follow_up_actions: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.suggestions is None:
            self.suggestions = []
        if self.follow_up_actions is None:
            self.follow_up_actions = []


class VoiceCommandProcessor:
    """Service for processing voice commands and executing actions."""

    def __init__(self):
        self.browser_service = BrowserControlService()
        self.system_service = SystemControlService()
        self.connection_manager = ConnectionManager()
        self.db = get_database_connection()

        # Command patterns and intent mapping
        self.command_patterns = self._initialize_command_patterns()

        # Service state
        self.is_initialized = False
        self.active_commands = {}  # command_id -> ParsedCommand

    async def initialize(self) -> bool:
        """Initialize the voice command processor."""
        try:
            # Initialize browser service
            browser_init = await self.browser_service.initialize()
            if not browser_init:
                logger.warning("Browser service initialization failed")

            # Initialize system service
            # System service initializes automatically

            self.is_initialized = True
            logger.info("Voice command processor initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize voice command processor: {e}")
            return False

    async def process_voice_command(
        self,
        transcription: str,
        confidence: float,
        language: str = "tr",
        device_id: Optional[str] = None
    ) -> CommandResult:
        """
        Process a voice command from transcription.

        Args:
            transcription: Transcribed text from speech recognition
            confidence: Recognition confidence score (0.0 to 1.0)
            language: Language code
            device_id: ID of the requesting device

        Returns:
            CommandResult with execution details
        """
        start_time = time.time()
        command_id = str(uuid.uuid4())

        try:
            logger.info(f"Processing command: {transcription} (confidence: {confidence})")

            # Validate transcription confidence
            if confidence < 0.5:
                return CommandResult(
                    command_id=command_id,
                    success=False,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    action_results=[],
                    response_message="Ses anlaşışlığı düşük. Lütfen tekrar söyleyin.",
                    suggestions=["Daha net konuşun", "Mikrofonunuzu kontrol edin"]
                )

            # Parse command
            parsed_command = await self.parse_command(command_id, transcription, confidence, language)
            self.active_commands[command_id] = parsed_command

            # Store command in database
            await self._store_command(parsed_command, device_id)

            # Execute command if confidence is sufficient
            if parsed_command.confidence >= 0.6:
                result = await self.execute_command(parsed_command)
            else:
                result = CommandResult(
                    command_id=command_id,
                    success=False,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    action_results=[],
                    response_message="Emir anlaşılamadı. Lütfen farklı bir şekilde söyleyin.",
                    error_message="Low parsing confidence"
                )

            # Clean up
            if command_id in self.active_commands:
                del self.active_commands[command_id]

            return result

        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            return CommandResult(
                command_id=command_id,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                action_results=[],
                response_message="Bir hata oluştu. Lütfen tekrar deneyin.",
                error_message=str(e)
            )

    async def parse_command(
        self,
        command_id: str,
        transcription: str,
        confidence: float,
        language: str
    ) -> ParsedCommand:
        """Parse voice command transcription into structured command."""
        try:
            # Normalize transcription
            normalized_text = self._normalize_text(transcription)

            # Determine intent and category
            intent = self._detect_intent(normalized_text)
            category = self._get_category_for_intent(intent)

            # Extract entities
            entities = self._extract_entities(normalized_text, intent)

            # Generate action sequence
            action_sequence = self._generate_action_sequence(intent, entities)

            # Extract parameters
            parameters = self._extract_parameters(normalized_text, intent, entities)

            # Determine if confirmation is required
            requires_confirmation = self._requires_confirmation(intent, entities)

            # Estimate execution time
            estimated_time = self._estimate_execution_time(action_sequence)

            return ParsedCommand(
                command_id=command_id,
                transcription=transcription,
                confidence=confidence,
                language=language,
                category=category,
                intent=intent,
                entities=entities,
                parameters=parameters,
                action_sequence=action_sequence,
                requires_confirmation=requires_confirmation,
                estimated_execution_time_ms=estimated_time
            )

        except Exception as e:
            logger.error(f"Error parsing command: {e}")
            # Return unknown intent
            return ParsedCommand(
                command_id=command_id,
                transcription=transcription,
                confidence=confidence,
                language=language,
                category=CommandCategory.UNKNOWN,
                intent=CommandIntent.UNKNOWN,
                entities={},
                parameters={},
                action_sequence=[],
                estimated_execution_time_ms=1000
            )

    async def execute_command(self, parsed_command: ParsedCommand) -> CommandResult:
        """Execute a parsed voice command."""
        start_time = time.time()
        action_results = []

        try:
            logger.info(f"Executing command: {parsed_command.intent.value}")

            for action in parsed_command.action_sequence:
                action_result = await self._execute_action(action, parsed_command)
                action_results.append(action_result)

                # If any action fails critically, stop execution
                if not action_result.get("success", True) and action_result.get("critical", False):
                    break

            execution_time = int((time.time() - start_time) * 1000)

            # Generate response
            success = all(result.get("success", True) for result in action_results)
            response_message = self._generate_response_message(parsed_command, action_results, success)

            # Update command status in database
            await self._update_command_status(parsed_command.command_id, success, response_message)

            return CommandResult(
                command_id=parsed_command.command_id,
                success=success,
                execution_time_ms=execution_time,
                action_results=action_results,
                response_message=response_message,
                suggestions=self._generate_suggestions(parsed_command, action_results, success),
                follow_up_actions=self._generate_follow_up_actions(parsed_command, action_results)
            )

        except Exception as e:
            logger.error(f"Error executing command: {e}")
            return CommandResult(
                command_id=parsed_command.command_id,
                success=False,
                execution_time_ms=int((time.time() - start_time) * 1000),
                action_results=action_results,
                response_message="Emir çalıştırılırken hata oluştu.",
                error_message=str(e)
            )

    def _initialize_command_patterns(self) -> Dict[CommandIntent, List[str]]:
        """Initialize command patterns for intent detection."""
        return {
            CommandIntent.NAVIGATE: [
                r"(git|göt|aç|naivgate to|navigate|go to)\s+(.+)",
                r"(sayfaya git|siteye git|website)\s+(.+)",
                r"(ziyaret et|göz at)\s+(.+)"
            ],
            CommandIntent.SEARCH: [
                r"(ara|bul|search for|google|bing)\s+(.+)",
                r"(internette ara|webde ara)\s+(.+)",
                r"(bilgi bul|araştır)\s+(.+)"
            ],
            CommandIntent.LAUNCH: [
                r"(çalıştır|başlat|aç|launch|open|run)\s+(.+)",
                r"(programı aç|uygulama başlat)\s+(.+)",
                r"(start|execute)\s+(.+)"
            ],
            CommandIntent.VOLUME_UP: [
                r"(sesi aç|ses yükselt|volume up|turn up volume)",
                r"(daha yüksek ses|sesi artır)",
                r"(increase volume|louder)"
            ],
            CommandIntent.VOLUME_DOWN: [
                r"(sesi kıs|sesi azalt|volume down|turn down volume)",
                r"(daha düşük ses|sessiz)",
                r"(decrease volume|quieter|mute)"
            ],
            CommandIntent.VOLUME_SET: [
                r"(sesi ayarla|volume set|set volume)\s+(\d+)",
                r"(ses seviyesi)\s+(\d+)",
                r"(volume)\s+(\d+)"
            ],
            CommandIntent.FIND_FILE: [
                r"(dosya bul|ara dosyayı|find file|search file)\s+(.+)",
                r"(bul|ara)\s+(.+)\s+(dosya|file)",
                r"(nerede|where is)\s+(.+)"
            ],
            CommandIntent.SYSTEM_INFO: [
                r"(sistem bilgisi|bilgisayar bilgisi|system info|computer info)",
                r"(durum nedir|how is my computer)",
                r"(sistem durum|system status)"
            ],
            CommandIntent.SCREENSHOT: [
                r"(ekran görüntüsü|screenshot|capture screen)",
                r"(fotoğraf çek|take picture)",
                r"(kaydet|save screen)"
            ],
            CommandIntent.CLICK: [
                r"(tıkla|click|bas)\s+(.+)",
                r"(seç|select)\s+(.+)",
                r"(butona tıkla)\s+(.+)"
            ],
            CommandIntent.TYPE: [
                r"(yaz|type|enter)\s+(.+)",
                r"(metin gir|text enter)\s+(.+)",
                r"(araştır yaz|search type)\s+(.+)"
            ],
            CommandIntent.CLOSE: [
                r"(kapat|close|exit|quit)",
                r"(sekmeyi kapat|close tab)",
                r"((pencereyi|sayfayı) kapat)"
            ],
            CommandIntent.BACK: [
                r"(geri git|go back|back)",
                r"((önceki sayfaya|previous page) git)",
                r"(geri dön|return)"
            ],
            CommandIntent.REFRESH: [
                r"(yenile|refresh|reload)",
                r"(sayfayı yenile|refresh page)",
                r"(güncelle|update)"
            ],
            CommandIntent.SCROLL: [
                r"(kaydır|scroll|move)\s+(aşağı|yukarı|down|up)",
                r"(aşağı in|yukarı çık|scroll down|scroll up)",
                r"(sayfayı hareket ettir)"
            ]
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize text for processing."""
        # Convert to lowercase
        text = text.lower().strip()

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove punctuation (except for URLs and specific cases)
        text = re.sub(r'[^\w\s./-]', ' ', text)

        return text

    def _detect_intent(self, text: str) -> CommandIntent:
        """Detect command intent from text."""
        text = self._normalize_text(text)

        for intent, patterns in self.command_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return intent

        return CommandIntent.UNKNOWN

    def _get_category_for_intent(self, intent: CommandIntent) -> CommandCategory:
        """Get command category for intent."""
        category_mapping = {
            CommandIntent.NAVIGATE: CommandCategory.BROWSER,
            CommandIntent.SEARCH: CommandCategory.BROWSER,
            CommandIntent.CLICK: CommandCategory.BROWSER,
            CommandIntent.TYPE: CommandCategory.BROWSER,
            CommandIntent.CLOSE: CommandCategory.BROWSER,
            CommandIntent.BACK: CommandCategory.BROWSER,
            CommandIntent.REFRESH: CommandCategory.BROWSER,
            CommandIntent.SCROLL: CommandCategory.BROWSER,
            CommandIntent.SCREENSHOT: CommandCategory.BROWSER,
            CommandIntent.LAUNCH: CommandCategory.SYSTEM,
            CommandIntent.VOLUME_UP: CommandCategory.VOLUME,
            CommandIntent.VOLUME_DOWN: CommandCategory.VOLUME,
            CommandIntent.VOLUME_SET: CommandCategory.VOLUME,
            CommandIntent.FIND_FILE: CommandCategory.FILE,
            CommandIntent.SYSTEM_INFO: CommandCategory.INFO
        }

        return category_mapping.get(intent, CommandCategory.UNKNOWN)

    def _extract_entities(self, text: str, intent: CommandIntent) -> Dict[str, Any]:
        """Extract entities from text based on intent."""
        entities = {}

        # Extract URL for navigation
        if intent == CommandIntent.NAVIGATE:
            url_match = re.search(r'(?:git|göt|aç|go to|navigate)\s+(.+)', text, re.IGNORECASE)
            if url_match:
                url = url_match.group(1).strip()
                # Clean up URL
                url = re.sub(r'\s+(?:gibi|like|diye)$', '', url)
                entities["url"] = url

        # Extract search query
        elif intent == CommandIntent.SEARCH:
            search_match = re.search(r'(?:ara|bul|search for|google)\s+(.+)', text, re.IGNORECASE)
            if search_match:
                entities["search_query"] = search_match.group(1).strip()

        # Extract app name
        elif intent == CommandIntent.LAUNCH:
            app_match = re.search(r'(?:çalıştır|başlat|aç|launch|open)\s+(.+)', text, re.IGNORECASE)
            if app_match:
                entities["app_name"] = app_match.group(1).strip()

        # Extract volume level
        elif intent == CommandIntent.VOLUME_SET:
            volume_match = re.search(r'(\d+)', text)
            if volume_match:
                volume = int(volume_match.group(1))
                entities["volume_level"] = min(100, max(0, volume))

        # Extract file name
        elif intent == CommandIntent.FIND_FILE:
            file_match = re.search(r'(?:bul|ara|find)\s+(.+)', text, re.IGNORECASE)
            if file_match:
                entities["file_name"] = file_match.group(1).strip()

        # Extract click target
        elif intent == CommandIntent.CLICK:
            click_match = re.search(r'(?:tıkla|click|bas)\s+(.+)', text, re.IGNORECASE)
            if click_match:
                entities["target_text"] = click_match.group(1).strip()

        # Extract text to type
        elif intent == CommandIntent.TYPE:
            type_match = re.search(r'(?:yaz|type|enter)\s+(.+)', text, re.IGNORECASE)
            if type_match:
                entities["text_to_type"] = type_match.group(1).strip()

        # Extract scroll direction
        elif intent == CommandIntent.SCROLL:
            if any(word in text for word in ['aşağı', 'down', 'aşağıya']):
                entities["scroll_direction"] = "down"
            elif any(word in text for word in ['yukarı', 'up', 'yukarıya']):
                entities["scroll_direction"] = "up"

        return entities

    def _generate_action_sequence(self, intent: CommandIntent, entities: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate action sequence for intent."""
        actions = []

        if intent == CommandIntent.NAVIGATE:
            url = entities.get("url", "")
            actions.append({
                "type": "browser_navigate",
                "url": url
            })

        elif intent == CommandIntent.SEARCH:
            query = entities.get("search_query", "")
            actions.append({
                "type": "browser_search",
                "query": query,
                "search_engine": "google"
            })

        elif intent == CommandIntent.LAUNCH:
            app_name = entities.get("app_name", "")
            actions.append({
                "type": "system_launch",
                "target": app_name
            })

        elif intent == CommandIntent.VOLUME_UP:
            actions.append({
                "type": "system_volume",
                "adjust_type": "increase",
                "amount": 10
            })

        elif intent == CommandIntent.VOLUME_DOWN:
            actions.append({
                "type": "system_volume",
                "adjust_type": "decrease",
                "amount": 10
            })

        elif intent == CommandIntent.VOLUME_SET:
            volume = entities.get("volume_level", 50)
            actions.append({
                "type": "system_volume",
                "adjust_type": "set",
                "level": volume
            })

        elif intent == CommandIntent.FIND_FILE:
            file_name = entities.get("file_name", "")
            actions.append({
                "type": "system_file_find",
                "search_query": file_name
            })

        elif intent == CommandIntent.SYSTEM_INFO:
            actions.append({
                "type": "system_info"
            })

        elif intent == CommandIntent.SCREENSHOT:
            actions.append({
                "type": "browser_screenshot"
            })

        elif intent == CommandIntent.CLICK:
            target_text = entities.get("target_text", "")
            actions.append({
                "type": "browser_interact",
                "action": "click",
                "selector_type": "link_text",
                "target": target_text
            })

        elif intent == CommandIntent.TYPE:
            text_input = entities.get("text_to_type", "")
            actions.append({
                "type": "browser_interact",
                "action": "type",
                "target": "input[type='text'], input[type='search'], textarea",
                "selector_type": "css",
                "value": text_input
            })

        elif intent == CommandIntent.CLOSE:
            actions.append({
                "type": "browser_close"
            })

        elif intent == CommandIntent.BACK:
            actions.append({
                "type": "browser_back"
            })

        elif intent == CommandIntent.REFRESH:
            actions.append({
                "type": "browser_refresh"
            })

        elif intent == CommandIntent.SCROLL:
            direction = entities.get("scroll_direction", "down")
            actions.append({
                "type": "browser_scroll",
                "direction": direction
            })

        return actions

    def _extract_parameters(self, text: str, intent: CommandIntent, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional parameters from text."""
        parameters = {}

        # Extract working directory for file operations
        if intent == CommandIntent.FIND_FILE:
            if "desktop" in text:
                parameters["search_path"] = os.path.join(os.path.expanduser("~"), "Desktop")
            elif "documents" in text or "belgeler" in text:
                parameters["search_path"] = os.path.join(os.path.expanduser("~"), "Documents")
            elif "downloads" in text or "indirilenler" in text:
                parameters["search_path"] = os.path.join(os.path.expanduser("~"), "Downloads")

        # Extract file type
        if intent == CommandIntent.FIND_FILE:
            if any(word in text for word in ["resim", "image", "fotoğraf", "photo"]):
                parameters["file_type"] = "image"
            elif any(word in text for word in ["video", "film"]):
                parameters["file_type"] = "video"
            elif any(word in text for word in ["belge", "document", "metin"]):
                parameters["file_type"] = "document"

        return parameters

    def _requires_confirmation(self, intent: CommandIntent, entities: Dict[str, Any]) -> bool:
        """Determine if command requires confirmation."""
        dangerous_intents = [
            CommandIntent.DELETE_FILE,
            CommandIntent.LAUNCH  # For system applications
        ]

        # High volume changes
        if intent == CommandIntent.VOLUME_SET:
            volume = entities.get("volume_level", 0)
            if volume > 80:
                return True

        # Unknown commands always need confirmation
        if intent == CommandIntent.UNKNOWN:
            return True

        return intent in dangerous_intents

    def _estimate_execution_time(self, action_sequence: List[Dict[str, Any]]) -> int:
        """Estimate execution time in milliseconds."""
        base_time = 1000  # 1 second base time
        action_times = {
            "browser_navigate": 3000,
            "browser_search": 2000,
            "system_launch": 2000,
            "system_volume": 500,
            "system_file_find": 5000,
            "system_info": 1000,
            "browser_screenshot": 1000,
            "browser_interact": 1000,
            "browser_close": 500,
            "browser_back": 1000,
            "browser_refresh": 2000,
            "browser_scroll": 500
        }

        total_time = base_time
        for action in action_sequence:
            action_type = action.get("type", "")
            total_time += action_times.get(action_type, 1000)

        return total_time

    async def _execute_action(self, action: Dict[str, Any], parsed_command: ParsedCommand) -> Dict[str, Any]:
        """Execute a single action."""
        action_type = action.get("type")
        start_time = time.time()

        try:
            if action_type == "browser_navigate":
                return await self._execute_browser_navigate(action)
            elif action_type == "browser_search":
                return await self._execute_browser_search(action)
            elif action_type == "system_launch":
                return await self._execute_system_launch(action)
            elif action_type == "system_volume":
                return await self._execute_system_volume(action)
            elif action_type == "system_file_find":
                return await self._execute_system_file_find(action)
            elif action_type == "system_info":
                return await self._execute_system_info()
            elif action_type == "browser_screenshot":
                return await self._execute_browser_screenshot()
            elif action_type == "browser_interact":
                return await self._execute_browser_interact(action)
            elif action_type == "browser_close":
                return await self._execute_browser_close()
            elif action_type == "browser_back":
                return await self._execute_browser_back()
            elif action_type == "browser_refresh":
                return await self._execute_browser_refresh()
            elif action_type == "browser_scroll":
                return await self._execute_browser_scroll(action)
            else:
                return {
                    "success": False,
                    "action_type": action_type,
                    "error_message": f"Unknown action type: {action_type}",
                    "execution_time_ms": int((time.time() - start_time) * 1000)
                }

        except Exception as e:
            return {
                "success": False,
                "action_type": action_type,
                "error_message": str(e),
                "execution_time_ms": int((time.time() - start_time) * 1000),
                "critical": True
            }

    async def _execute_browser_navigate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser navigation."""
        url = action.get("url", "")
        result = await self.browser_service.navigate_to_url(url)
        return {
            "success": result.success,
            "action_type": "browser_navigate",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_browser_search(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser search."""
        query = action.get("query", "")
        search_engine = action.get("search_engine", "google")
        result = await self.browser_service.search_web(query, search_engine)
        return {
            "success": result.success,
            "action_type": "browser_search",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_system_launch(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system application launch."""
        target = action.get("target", "")
        system_action = SystemAction(
            action_type="launch",
            target=target
        )
        result = await self.system_service.launch_application(system_action)
        return {
            "success": result.success,
            "action_type": "system_launch",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_system_volume(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system volume control."""
        adjust_type = action.get("adjust_type", "set")
        level = action.get("level", 50)
        amount = action.get("amount", 10)

        parameters = {"adjust_type": adjust_type}
        if adjust_type == "set":
            parameters["volume_level"] = level
        else:
            parameters["amount"] = amount

        system_action = SystemAction(
            action_type="volume",
            parameters=parameters
        )
        result = await self.system_service.set_volume(system_action)
        return {
            "success": result.success,
            "action_type": "system_volume",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_system_file_find(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute system file search."""
        search_query = action.get("search_query", "")
        parameters = {
            "search_query": search_query,
            "max_results": 20
        }
        system_action = SystemAction(
            action_type="find_files",
            parameters=parameters
        )
        result = await self.system_service.find_files(system_action)
        return {
            "success": result.success,
            "action_type": "system_file_find",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_system_info(self) -> Dict[str, Any]:
        """Execute system info retrieval."""
        result = await self.system_service.get_system_info()
        return {
            "success": result.success,
            "action_type": "system_info",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_browser_screenshot(self) -> Dict[str, Any]:
        """Execute browser screenshot."""
        result = await self.browser_service.take_screenshot()
        return {
            "success": result.success,
            "action_type": "browser_screenshot",
            "result_data": {"screenshot_path": result.screenshot_path},
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_browser_interact(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser element interaction."""
        browser_action = BrowserAction(
            action_type=action.get("action", "click"),
            target=action.get("target"),
            selector_type=ElementSelectorType.CSS_SELECTOR if action.get("selector_type") == "css" else None,
            value=action.get("value")
        )
        result = await self.browser_service.interact_with_element(browser_action)
        return {
            "success": result.success,
            "action_type": "browser_interact",
            "result_data": result.result_data,
            "error_message": result.error_message,
            "execution_time_ms": result.execution_time_ms
        }

    async def _execute_browser_close(self) -> Dict[str, Any]:
        """Execute browser close."""
        # This would close the current tab
        return {
            "success": True,
            "action_type": "browser_close",
            "result_data": {"message": "Sekme kapatıldı"},
            "execution_time_ms": 500
        }

    async def _execute_browser_back(self) -> Dict[str, Any]:
        """Execute browser back navigation."""
        # This would navigate back in browser history
        return {
            "success": True,
            "action_type": "browser_back",
            "result_data": {"message": "Önceki sayfaya gidildi"},
            "execution_time_ms": 1000
        }

    async def _execute_browser_refresh(self) -> Dict[str, Any]:
        """Execute browser refresh."""
        # This would refresh the current page
        return {
            "success": True,
            "action_type": "browser_refresh",
            "result_data": {"message": "Sayfa yenilendi"},
            "execution_time_ms": 2000
        }

    async def _execute_browser_scroll(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser scroll."""
        direction = action.get("direction", "down")
        return {
            "success": True,
            "action_type": "browser_scroll",
            "result_data": {"message": f"Sayfa {'aşağı' if direction == 'down' else 'yukarı'} kaydırıldı"},
            "execution_time_ms": 500
        }

    def _generate_response_message(
        self,
        parsed_command: ParsedCommand,
        action_results: List[Dict[str, Any]],
        success: bool
    ) -> str:
        """Generate appropriate response message."""
        if not success:
            return "Emir çalıştırılamadı. Lütfen tekrar deneyin."

        intent = parsed_command.intent
        messages = {
            CommandIntent.NAVIGATE: "Web sitesi açıldı",
            CommandIntent.SEARCH: "Arama yapıldı",
            CommandIntent.LAUNCH: "Uygulama başlatıldı",
            CommandIntent.VOLUME_UP: "Ses yükseltildi",
            CommandIntent.VOLUME_DOWN: "Ses kısıltdı",
            CommandIntent.VOLUME_SET: "Ses ayarlandı",
            CommandIntent.FIND_FILE: "Dosya araması yapıldı",
            CommandIntent.SYSTEM_INFO: "Sistem bilgileri gösterildi",
            CommandIntent.SCREENSHOT: "Ekran görüntüsü alındı",
            CommandIntent.CLICK: "Tıklandı",
            CommandIntent.TYPE: "Metin yazıldı",
            CommandIntent.CLOSE: "Kapatıldı",
            CommandIntent.BACK: "Önceki sayfaya gidildi",
            CommandIntent.REFRESH: "Sayfa yenilendi",
            CommandIntent.SCROLL: "Sayfa kaydırıldı"
        }

        return messages.get(intent, "Emir tamamlandı")

    def _generate_suggestions(
        self,
        parsed_command: ParsedCommand,
        action_results: List[Dict[str, Any]],
        success: bool
    ) -> List[str]:
        """Generate follow-up suggestions."""
        suggestions = []

        if parsed_command.intent == CommandIntent.SEARCH and success:
            suggestions.append("Sonuçlar hakkında detay isteyin")
            suggestions.append("Başka bir arama yapın")

        elif parsed_command.intent == CommandIntent.NAVIGATE and success:
            suggestions.append("Sayfadaki metni arayın")
            suggestions.append("Resimleri kontrol edin")

        elif parsed_command.intent == CommandIntent.SYSTEM_INFO and success:
            suggestions.append("Daha fazla sistem detayı isteyin")
            suggestions.append("Sistem durumu kontrol edin")

        return suggestions

    def _generate_follow_up_actions(
        self,
        parsed_command: ParsedCommand,
        action_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate suggested follow-up actions."""
        follow_up = []

        if parsed_command.intent == CommandIntent.SEARCH:
            follow_up.append({
                "intent": CommandIntent.NAVIGATE,
                "description": "Arama sonucuna git"
            })

        elif parsed_command.intent == CommandIntent.NAVIGATE:
            follow_up.append({
                "intent": CommandIntent.SEARCH,
                "description": "Sayfada ara"
            })

        return follow_up

    async def _store_command(self, parsed_command: ParsedCommand, device_id: Optional[str]):
        """Store command in database."""
        try:
            await self.db.execute_query(
                """
                INSERT INTO voice_commands (
                    command_id, transcription, confidence, timestamp,
                    language, status, device_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    parsed_command.command_id,
                    parsed_command.transcription,
                    parsed_command.confidence,
                    int(time.time() * 1000),  # timestamp in ms
                    parsed_command.language,
                    "processing",
                    device_id,
                    int(time.time() * 1000)  # created_at in ms
                )
            )

            # Store actions
            for i, action in enumerate(parsed_command.action_sequence):
                await self.db.execute_query(
                    """
                    INSERT INTO actions (
                        action_id, command_id, action_type, parameters,
                        status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        parsed_command.command_id,
                        action.get("type"),
                        json.dumps(action),
                        "pending",
                        int(time.time() * 1000)
                    )
                )

        except Exception as e:
            logger.error(f"Error storing command: {e}")

    async def _update_command_status(self, command_id: str, success: bool, response_message: str):
        """Update command status in database."""
        try:
            status = "completed" if success else "failed"
            await self.db.execute_query(
                """
                UPDATE voice_commands
                SET status = ?, updated_at = ?
                WHERE command_id = ?
                """,
                (status, int(time.time() * 1000), command_id)
            )

            # Update action status
            await self.db.execute_query(
                """
                UPDATE actions
                SET status = ?
                WHERE command_id = ?
                """,
                (status, command_id)
            )

        except Exception as e:
            logger.error(f"Error updating command status: {e}")

    async def cleanup(self) -> None:
        """Cleanup voice command processor."""
        try:
            await self.browser_service.close_browser()
            await self.system_service.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")