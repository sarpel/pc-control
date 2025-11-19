"""
MCP Tools Router - Connects all MCP tools with the command interpreter.

This module provides the main interface for all MCP tools:
- System operations (file, process, volume control)
- Browser automation via Chrome DevTools
- Tool registration and routing
- Error handling and validation
- Performance monitoring

Following requirements from spec and tasks T058-T067.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

from .chrome_devtools import chrome_mcp_server, BrowserResult
from ..services.system_controller import SystemController
from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Categories of MCP tools."""
    SYSTEM = "system"
    BROWSER = "browser"


@dataclass
class ToolRequest:
    """Request for MCP tool execution."""
    tool_name: str
    category: ToolCategory
    parameters: Dict[str, Any]
    timeout_ms: Optional[int] = None


@dataclass
class ToolResponse:
    """Response from MCP tool execution."""
    success: bool
    tool_name: str
    category: ToolCategory
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None
    error: Optional[str] = None


class MCPToolsRouter:
    """
    Main MCP tools router that coordinates all available tools.

    Features:
    - Tool registration and discovery
    - Parameter validation
    - Execution routing
    - Performance monitoring
    - Error handling with Turkish messages
    - Security constraints enforcement
    """

    def __init__(self):
        self.system_controller = SystemController()
        self.tools_registry = self._build_tools_registry()
        self.settings = get_settings()

    def _build_tools_registry(self) -> Dict[str, Dict[str, Any]]:
        """Build registry of all available tools with metadata."""
        return {
            # System tools
            "launch_application": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_launch_application,
                "required_params": ["appName"],
                "optional_params": ["args", "workingDirectory"],
                "timeout_ms": 5000
            },
            "adjust_volume": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_adjust_volume,
                "required_params": ["level"],
                "optional_params": ["relative"],
                "timeout_ms": 1000
            },
            "find_files": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_find_files,
                "required_params": ["query"],
                "optional_params": ["locations", "maxResults"],
                "timeout_ms": 10000
            },
            "delete_file": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_delete_file,
                "required_params": ["path"],
                "optional_params": ["confirmed"],
                "timeout_ms": 2000,
                "security_constraint": True
            },
            "query_system_info": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_query_system_info,
                "required_params": ["infoType"],
                "optional_params": [],
                "timeout_ms": 3000
            },
            # New advanced system operations (T073-T079)
            "query_network_status": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_query_network_status,
                "required_params": [],
                "optional_params": ["detailed"],
                "timeout_ms": 10000
            },
            "power_management": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_power_management,
                "required_params": ["action"],
                "optional_params": ["force", "delay"],
                "timeout_ms": 5000,
                "security_constraint": True
            },
            "clipboard_operations": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_clipboard_operations,
                "required_params": ["operation"],
                "optional_params": ["text"],
                "timeout_ms": 3000
            },
            "capture_screenshot": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_capture_screenshot,
                "required_params": [],
                "optional_params": ["area", "path"],
                "timeout_ms": 8000
            },
            "manage_command_history": {
                "category": ToolCategory.SYSTEM,
                "handler": self._handle_manage_command_history,
                "required_params": ["operation"],
                "optional_params": [],
                "timeout_ms": 2000
            },

            # Browser tools
            "browser_navigate": {
                "category": ToolCategory.BROWSER,
                "handler": self._handle_browser_navigate,
                "required_params": ["url"],
                "optional_params": ["newTab"],
                "timeout_ms": 15000
            },
            "browser_search": {
                "category": ToolCategory.BROWSER,
                "handler": self._handle_browser_search,
                "required_params": ["query"],
                "optional_params": ["searchEngine"],
                "timeout_ms": 15000
            },
            "browser_extract_content": {
                "category": ToolCategory.BROWSER,
                "handler": self._handle_browser_extract_content,
                "required_params": [],
                "optional_params": ["summaryLength"],
                "timeout_ms": 10000
            },
            "browser_interact": {
                "category": ToolCategory.BROWSER,
                "handler": self._handle_browser_interact,
                "required_params": ["action"],
                "optional_params": ["selector", "value"],
                "timeout_ms": 5000
            }
        }

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> ToolResponse:
        """
        Execute an MCP tool with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            ToolResponse with execution result
        """
        import time
        start_time = time.time()

        try:
            # Check if tool exists
            if tool_name not in self.tools_registry:
                return ToolResponse(
                    success=False,
                    tool_name=tool_name,
                    category=ToolCategory.SYSTEM,
                    message=f"Bilinmeyen araç: {tool_name}",
                    error=f"Tool '{tool_name}' not found in registry"
                )

            tool_info = self.tools_registry[tool_name]

            # Validate parameters
            validation_result = self._validate_parameters(tool_name, parameters, tool_info)
            if not validation_result.valid:
                return ToolResponse(
                    success=False,
                    tool_name=tool_name,
                    category=tool_info["category"],
                    message=f"Parametre hatası: {validation_result.message}",
                    error=validation_result.message
                )

            # Check security constraints
            if tool_info.get("security_constraint"):
                security_result = await self._check_security_constraints(tool_name, parameters)
                if not security_result.allowed:
                    return ToolResponse(
                        success=False,
                        tool_name=tool_name,
                        category=tool_info["category"],
                        message=f"Güvenlik kısıtı: {security_result.message}",
                        error=security_result.message
                    )

            # Execute tool with timeout
            timeout_ms = parameters.get("timeout", tool_info.get("timeout_ms", 5000))
            handler = tool_info["handler"]

            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await asyncio.wait_for(
                        handler(parameters),
                        timeout=timeout_ms / 1000.0
                    )
                else:
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, handler, parameters
                    )
            except asyncio.TimeoutError:
                return ToolResponse(
                    success=False,
                    tool_name=tool_name,
                    category=tool_info["category"],
                    message=f"İşlem zaman aşımına uğradı ({timeout_ms}ms)",
                    error=f"Tool execution timed out after {timeout_ms}ms"
                )

            execution_time = (time.time() - start_time) * 1000

            # Convert result to ToolResponse
            if isinstance(result, BrowserResult):
                return ToolResponse(
                    success=result.success,
                    tool_name=tool_name,
                    category=tool_info["category"],
                    message=result.message,
                    data=result.data,
                    execution_time_ms=execution_time,
                    error=None if result.success else result.message
                )
            elif isinstance(result, dict):
                return ToolResponse(
                    success=result.get("success", False),
                    tool_name=tool_name,
                    category=tool_info["category"],
                    message=result.get("message", ""),
                    data=result.get("data"),
                    execution_time_ms=execution_time,
                    error=None if result.get("success", False) else result.get("message")
                )
            else:
                return ToolResponse(
                    success=True,
                    tool_name=tool_name,
                    category=tool_info["category"],
                    message="İşlem başarıyla tamamlandı",
                    data={"result": result} if result else None,
                    execution_time_ms=execution_time
                )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Tool execution failed for {tool_name}: {e}")

            return ToolResponse(
                success=False,
                tool_name=tool_name,
                category=ToolCategory.SYSTEM,
                message=f"Açıklayıcı hata: {str(e)}",
                error=str(e),
                execution_time_ms=execution_time
            )

    def _validate_parameters(self, tool_name: str, parameters: Dict[str, Any], tool_info: Dict[str, Any]) -> 'ValidationResult':
        """Validate tool parameters against schema."""
        required_params = tool_info.get("required_params", [])
        optional_params = tool_info.get("optional_params", [])

        # Check for missing required parameters
        for param in required_params:
            if param not in parameters:
                return ValidationResult(False, f"Gerekli parametre eksik: {param}")

        # Check for unknown parameters
        for param in parameters.keys():
            if param not in required_params + optional_params and param != "timeout":
                return ValidationResult(False, f"Bilinmeyen parametre: {param}")

        return ValidationResult(True, "Parametreler geçerli")

    async def _check_security_constraints(self, tool_name: str, parameters: Dict[str, Any]) -> 'SecurityResult':
        """Check security constraints for sensitive operations."""
        if tool_name == "delete_file":
            path = parameters.get("path", "")

            # Check if path is in system directory
            system_paths = ["C:\\Windows", "C:\\Program Files"]
            if any(path.lower().startswith(sys_path.lower()) for sys_path in system_paths):
                return SecurityResult(False, f"Sistem dizinindeki dosyalar silinemez: {path}")

            # Check if path is allowed
            allowed_paths = ["C:\\Users", "D:\\", "E:\\"]
            if not any(path.lower().startswith(allowed_path.lower()) for allowed_path in allowed_paths):
                return SecurityResult(False, f"Bu dizindeki dosyalar silinemez: {path}")

        return SecurityResult(True, "Güvenlik denetimi geçti")

    async def _handle_launch_application(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle application launch command."""
        try:
            result = await self.system_controller.launch_application(
                app_name=parameters["appName"],
                args=parameters.get("args", []),
                working_directory=parameters.get("workingDirectory")
            )
            return {
                "success": result.success,
                "message": result.message,
                "data": {"processId": result.process_id} if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Uygulama başlatılamadı: {str(e)}"}

    async def _handle_adjust_volume(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle volume adjustment command."""
        try:
            level = parameters["level"]
            relative = parameters.get("relative", False)

            result = await self.system_controller.adjust_volume(level, relative)
            return {
                "success": result.success,
                "message": result.message,
                "data": {"currentLevel": result.current_level} if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Ses ayarlanamadı: {str(e)}"}

    async def _handle_find_files(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file search command."""
        try:
            query = parameters["query"]
            locations = parameters.get("locations", [])
            max_results = parameters.get("maxResults", 10)

            result = await self.system_controller.find_files(query, locations, max_results)
            return {
                "success": result.success,
                "message": result.message,
                "data": {"files": result.files} if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Dosya arama başarısız: {str(e)}"}

    async def _handle_delete_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file deletion command."""
        try:
            path = parameters["path"]
            confirmed = parameters.get("confirmed", False)

            result = await self.system_controller.delete_file(path, confirmed)
            return {
                "success": result.success,
                "message": result.message,
                "data": {"requiresConfirmation": result.requires_confirmation} if not result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Dosya silinemedi: {str(e)}"}

    async def _handle_query_system_info(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle system info query command."""
        try:
            info_type = parameters["infoType"]

            result = await self.system_controller.get_system_info(info_type)
            return {
                "success": result.success,
                "message": result.message,
                "data": {"info": result.info} if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Sistem bilgisi alınamadı: {str(e)}"}

    async def _handle_browser_navigate(self, parameters: Dict[str, Any]) -> BrowserResult:
        """Handle browser navigation command."""
        url = parameters["url"]
        new_tab = parameters.get("newTab", False)

        return await chrome_mcp_server.browser_navigate(url, new_tab)

    async def _handle_browser_search(self, parameters: Dict[str, Any]) -> BrowserResult:
        """Handle browser search command."""
        query = parameters["query"]
        search_engine = parameters.get("searchEngine", "google")

        return await chrome_mcp_server.browser_search(query, search_engine)

    async def _handle_browser_extract_content(self, parameters: Dict[str, Any]) -> BrowserResult:
        """Handle content extraction command."""
        summary_length = parameters.get("summaryLength", "brief")

        return await chrome_mcp_server.browser_extract_content(summary_length)

    async def _handle_browser_interact(self, parameters: Dict[str, Any]) -> BrowserResult:
        """Handle browser interaction command."""
        action = parameters["action"]
        selector = parameters.get("selector", "")
        value = parameters.get("value", "")

        return await chrome_mcp_server.browser_interact(action, selector, value)

    # Advanced system operations handlers (T073-T079)
    async def _handle_query_network_status(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle network status query command."""
        try:
            from services.system_controller import SystemCommand, OperationType
            
            detailed = parameters.get("detailed", False)
            result = await self.system_controller.execute(SystemCommand(
                operation=OperationType.QUERY_NETWORK_STATUS.value,
                parameters={"detailed": detailed}
            ))
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Ağ durumu sorgulanamadı: {str(e)}"}

    async def _handle_power_management(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle power management command."""
        try:
            from services.system_controller import SystemCommand, OperationType
            
            action = parameters["action"]
            force = parameters.get("force", False)
            delay = parameters.get("delay", 0)
            
            result = await self.system_controller.execute(SystemCommand(
                operation=OperationType.POWER_MANAGEMENT.value,
                parameters={"action": action, "force": force, "delay": delay}
            ))
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Güç yönetimi işlemi başarısız: {str(e)}"}

    async def _handle_clipboard_operations(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle clipboard operations command."""
        try:
            from services.system_controller import SystemCommand, OperationType
            
            operation = parameters["operation"]
            text = parameters.get("text", "")
            
            result = await self.system_controller.execute(SystemCommand(
                operation=OperationType.CLIPBOARD_OPERATIONS.value,
                parameters={"operation": operation, "text": text}
            ))
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Pano işlemi başarısız: {str(e)}"}

    async def _handle_capture_screenshot(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle screenshot capture command."""
        try:
            from services.system_controller import SystemCommand, OperationType
            
            area = parameters.get("area", "full")
            path = parameters.get("path", "")
            
            result = await self.system_controller.execute(SystemCommand(
                operation=OperationType.CAPTURE_SCREENSHOT.value,
                parameters={"area": area, "path": path}
            ))
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Ekran görüntüsü alınamadı: {str(e)}"}

    async def _handle_manage_command_history(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Handle command history management command."""
        try:
            from services.system_controller import SystemCommand, OperationType
            
            operation = parameters["operation"]
            
            result = await self.system_controller.execute(SystemCommand(
                operation=OperationType.MANAGE_COMMAND_HISTORY.value,
                parameters={"operation": operation}
            ))
            
            return {
                "success": result.success,
                "message": result.message,
                "data": result.data if result.success else None
            }
        except Exception as e:
            return {"success": False, "message": f"Komut geçmişi yönetimi başarısız: {str(e)}"}

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools with metadata."""
        tools = []
        for tool_name, tool_info in self.tools_registry.items():
            tools.append({
                "name": tool_name,
                "category": tool_info["category"].value,
                "description": tool_info.get("description", ""),
                "required_params": tool_info.get("required_params", []),
                "optional_params": tool_info.get("optional_params", []),
                "timeout_ms": tool_info.get("timeout_ms", 5000)
            })
        return tools

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await chrome_mcp_server.cleanup()
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


# Helper classes for validation
@dataclass
class ValidationResult:
    valid: bool
    message: str


@dataclass
class SecurityResult:
    allowed: bool
    message: str


# Global tools router instance
tools_router = MCPToolsRouter()