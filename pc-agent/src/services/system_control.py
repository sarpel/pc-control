"""
System control service for PC Voice Controller.

This module provides comprehensive system control capabilities including
application launching, volume control, file operations, and system
information retrieval.
"""

import logging
import asyncio
import subprocess
import os
import sys
import platform
import ctypes
import psutil
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import json
import time
from src.models.action import Action, ActionType as ModelActionType

# Import CommandAction from command interpreter for proper integration
try:
    from services.command_interpreter import CommandAction, ActionType
except ImportError:
    # Fallback definitions if command interpreter not available
    class ActionType(Enum):
        SYSTEM = "system"
        BROWSER = "browser"
        QUERY = "query"
        UNKNOWN = "unknown"

    @dataclass
    class CommandAction:
        action_type: ActionType
        operation: str
        parameters: Dict[str, Any]
        requires_confirmation: bool = False
        confirmation_message: Optional[str] = None
        confidence: float = 0.0
        context_used: Optional[Dict[str, Any]] = None

logger = logging.getLogger(__name__)


class OperatingSystem(Enum):
    """Supported operating systems."""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"


class FileType(Enum):
    """Common file types for operations."""
    EXECUTABLE = "executable"
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    ARCHIVE = "archive"
    FOLDER = "folder"


@dataclass
class SystemAction:
    """Represents a system action to be executed."""
    action_type: str
    target: Optional[str] = None
    parameters: Dict[str, Any] = None
    working_directory: Optional[str] = None
    timeout_seconds: int = 30
    run_as_admin: bool = False

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class SystemActionResult:
    """Result of a system action execution."""
    success: bool
    action_type: str
    execution_time_ms: int
    result_data: Any = None
    return_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def data(self) -> Any:
        """Alias for result_data to match Action model expectations."""
        return self.result_data

    @property
    def error(self) -> Optional[str]:
        """Alias for error_message (if we had one) or construct from stderr."""
        if self.error_message:
            return self.error_message
        return self.stderr if self.stderr else ("Unknown error" if not self.success else None)
    error_message: Optional[str] = None


class SystemControlService:
    """Service for controlling system operations through voice commands."""

    def __init__(self):
        self.os_type = self._detect_os()
        self.admin_privileges = self._check_admin_privileges()
        self.temp_dir = Path(os.path.join(os.path.expanduser("~"), "temp", "pc_control"))
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _detect_os(self) -> OperatingSystem:
        """Detect the current operating system."""
        system = platform.system().lower()
        if system == "windows":
            return OperatingSystem.WINDOWS
        elif system == "linux":
            return OperatingSystem.LINUX
        elif system == "darwin":
            return OperatingSystem.MACOS
        else:
            return OperatingSystem.WINDOWS  # Default assumption

    def _check_admin_privileges(self) -> bool:
        """Check if running with administrator privileges."""
        try:
            if self.os_type == OperatingSystem.WINDOWS:
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False

    async def launch_application(self, action: SystemAction) -> SystemActionResult:
        """
        Launch an application or executable.

        Args:
            action: SystemAction containing application details

        Returns:
            SystemActionResult with execution details
        """
        start_time = time.time()

        try:
            if not action.target:
                return SystemActionResult(
                    success=False,
                    action_type="launch",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="No application target specified"
                )

            # Determine launch method based on OS
            if self.os_type == OperatingSystem.WINDOWS:
                result = await self._launch_windows_app(action)
            elif self.os_type == OperatingSystem.LINUX:
                result = await self._launch_linux_app(action)
            elif self.os_type == OperatingSystem.MACOS:
                result = await self._launch_macos_app(action)
            else:
                result = SystemActionResult(
                    success=False,
                    action_type="launch",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Unsupported OS: {self.os_type}"
                )

            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="launch",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Launch error: {str(e)}"
            )

    async def _launch_windows_app(self, action: SystemAction) -> SystemActionResult:
        """Launch application on Windows."""
        try:
            # Prepare command
            if action.target.endswith(('.exe', '.bat', '.cmd', '.ps1')):
                # Direct executable
                cmd = [action.target]
            else:
                # Try to find application by name
                app_path = await self._find_windows_application(action.target)
                if not app_path:
                    return SystemActionResult(
                        success=False,
                        action_type="launch",
                        execution_time_ms=0,
                        error_message=f"Application not found: {action.target}"
                    )
                cmd = [app_path]

            # Add arguments
            if action.parameters and "arguments" in action.parameters:
                args = action.parameters["arguments"]
                if isinstance(args, list):
                    cmd.extend(args)
                elif isinstance(args, str):
                    cmd.append(args)

            # Handle administrator privileges
            if action.run_as_admin and not self.admin_privileges:
                cmd = ["runas", "/user:Administrator"] + cmd

            # Execute
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=action.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=process.returncode == 0,
                action_type="launch",
                execution_time_ms=0,
                return_code=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else None,
                stderr=stderr.decode('utf-8') if stderr else None,
                result_data={
                    "application": action.target,
                    "pid": process.pid,
                    "command": " ".join(cmd)
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="launch",
                execution_time_ms=0,
                error_message=f"Windows launch error: {str(e)}"
            )

    async def _launch_linux_app(self, action: SystemAction) -> SystemActionResult:
        """Launch application on Linux."""
        try:
            # Try different launch methods
            cmd = []

            # Check if it's a direct path
            if os.path.exists(action.target):
                cmd = [action.target]
            else:
                # Try to find in PATH or common locations
                app_path = await self._find_linux_application(action.target)
                if not app_path:
                    return SystemActionResult(
                        success=False,
                        action_type="launch",
                        execution_time_ms=0,
                        error_message=f"Application not found: {action.target}"
                    )
                cmd = [app_path]

            # Add arguments
            if action.parameters and "arguments" in action.parameters:
                args = action.parameters["arguments"]
                if isinstance(args, list):
                    cmd.extend(args)
                elif isinstance(args, str):
                    cmd.append(args)

            # Execute with sudo if needed
            if action.run_as_admin and not self.admin_privileges:
                cmd = ["sudo"] + cmd

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=action.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=process.returncode == 0,
                action_type="launch",
                execution_time_ms=0,
                return_code=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else None,
                stderr=stderr.decode('utf-8') if stderr else None,
                result_data={
                    "application": action.target,
                    "pid": process.pid,
                    "command": " ".join(cmd)
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="launch",
                execution_time_ms=0,
                error_message=f"Linux launch error: {str(e)}"
            )

    async def _launch_macos_app(self, action: SystemAction) -> SystemActionResult:
        """Launch application on macOS."""
        try:
            # Use open command for macOS applications
            if action.target.endswith('.app'):
                cmd = ['open', action.target]
            else:
                # Try to find application
                app_path = await self._find_macos_application(action.target)
                if app_path:
                    cmd = ['open', app_path]
                else:
                    # Try as direct executable
                    cmd = [action.target]

            # Add arguments
            if action.parameters and "arguments" in action.parameters:
                args = action.parameters["arguments"]
                if isinstance(args, list):
                    cmd.extend(['--args'] + args)
                elif isinstance(args, str):
                    cmd.extend(['--args', args])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=action.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=process.returncode == 0,
                action_type="launch",
                execution_time_ms=0,
                return_code=process.returncode,
                stdout=stdout.decode('utf-8') if stdout else None,
                stderr=stderr.decode('utf-8') if stderr else None,
                result_data={
                    "application": action.target,
                    "command": " ".join(cmd)
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="launch",
                execution_time_ms=0,
                error_message=f"macOS launch error: {str(e)}"
            )

    async def set_volume(self, action: SystemAction) -> SystemActionResult:
        """
        Set system volume level.

        Args:
            action: SystemAction with volume parameters

        Returns:
            SystemActionResult with operation details
        """
        start_time = time.time()

        try:
            volume_level = action.parameters.get("volume_level", 50)
            adjust_type = action.parameters.get("adjust_type", "set")  # set, increase, decrease

            if not isinstance(volume_level, (int, float)) or not (0 <= volume_level <= 100):
                return SystemActionResult(
                    success=False,
                    action_type="volume",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Volume level must be between 0 and 100"
                )

            if self.os_type == OperatingSystem.WINDOWS:
                result = await self._set_windows_volume(volume_level, adjust_type)
            elif self.os_type == OperatingSystem.LINUX:
                result = await self._set_linux_volume(volume_level, adjust_type)
            elif self.os_type == OperatingSystem.MACOS:
                result = await self._set_macos_volume(volume_level, adjust_type)
            else:
                result = SystemActionResult(
                    success=False,
                    action_type="volume",
                    execution_time_ms=0,
                    error_message=f"Volume control not supported on {self.os_type}"
                )

            result.execution_time_ms = int((time.time() - start_time) * 1000)
            return result

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="volume",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Volume control error: {str(e)}"
            )

    async def _set_windows_volume(self, volume_level: float, adjust_type: str) -> SystemActionResult:
        """Set volume on Windows."""
        try:
            # Use PowerShell to control volume
            if adjust_type == "set":
                ps_script = f"(New-Object -comObject WScript.Shell).SendKeys([char]175)"
                # This is a simplified approach - in reality, you'd want more precise control
                cmd = ["powershell", "-Command", ps_script]
            else:
                # For increase/decrease, use volume keys
                if adjust_type == "increase":
                    key_code = "175"
                else:
                    key_code = "174"

                cmd = ["powershell", "-Command", f"(New-Object -comObject WScript.Shell).SendKeys([char]{key_code})"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=True,
                action_type="volume",
                execution_time_ms=0,
                result_data={
                    "adjust_type": adjust_type,
                    "volume_level": volume_level
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="volume",
                execution_time_ms=0,
                error_message=f"Windows volume error: {str(e)}"
            )

    async def _set_linux_volume(self, volume_level: float, adjust_type: str) -> SystemActionResult:
        """Set volume on Linux."""
        try:
            # Try different volume control methods
            cmd = []

            # Try amixer first (most common)
            try:
                if adjust_type == "set":
                    cmd = ["amixer", "set", "Master", f"{int(volume_level)}%"]
                elif adjust_type == "increase":
                    cmd = ["amixer", "set", "Master", "10%+"]
                else:
                    cmd = ["amixer", "set", "Master", "10%-"]
            except Exception:
                # Try pactl as fallback
                if adjust_type == "set":
                    cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{int(volume_level)}%"]
                elif adjust_type == "increase":
                    cmd = ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "+10%"]
                else:
                    cmd = ["pactl", "set-sink-volume", "@DEFAULT_SUILTIN_SINK@", "-10%"]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=process.returncode == 0,
                action_type="volume",
                execution_time_ms=0,
                return_code=process.returncode,
                stderr=stderr.decode('utf-8') if stderr else None,
                result_data={
                    "adjust_type": adjust_type,
                    "volume_level": volume_level,
                    "command": " ".join(cmd)
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="volume",
                execution_time_ms=0,
                error_message=f"Linux volume error: {str(e)}"
            )

    async def _set_macos_volume(self, volume_level: float, adjust_type: str) -> SystemActionResult:
        """Set volume on macOS."""
        try:
            # Use osascript to control volume
            if adjust_type == "set":
                script = f'set volume output volume {int(volume_level)}'
            elif adjust_type == "increase":
                script = 'set volume output volume (output volume of (get volume settings) + 10)'
            else:
                script = 'set volume output volume (output volume of (get volume settings) - 10)'

            cmd = ["osascript", "-e", script]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            return SystemActionResult(
                success=process.returncode == 0,
                action_type="volume",
                execution_time_ms=0,
                return_code=process.returncode,
                result_data={
                    "adjust_type": adjust_type,
                    "volume_level": volume_level
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="volume",
                execution_time_ms=0,
                error_message=f"macOS volume error: {str(e)}"
            )

    async def find_files(self, action: SystemAction) -> SystemActionResult:
        """
        Find files on the system.

        Args:
            action: SystemAction with search parameters

        Returns:
            SystemActionResult with found files
        """
        start_time = time.time()

        try:
            search_query = action.parameters.get("search_query", "")
            search_path = action.parameters.get("search_path", os.path.expanduser("~"))
            file_type = action.parameters.get("file_type", None)
            max_results = action.parameters.get("max_results", 50)

            if not search_query:
                return SystemActionResult(
                    success=False,
                    action_type="find_files",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Search query not specified"
                )

            if self.os_type == OperatingSystem.WINDOWS:
                results = await self._find_files_windows(search_query, search_path, file_type, max_results)
            elif self.os_type == OperatingSystem.LINUX:
                results = await self._find_files_linux(search_query, search_path, file_type, max_results)
            elif self.os_type == OperatingSystem.MACOS:
                results = await self._find_files_macos(search_query, search_path, file_type, max_results)
            else:
                results = []

            return SystemActionResult(
                success=True,
                action_type="find_files",
                execution_time_ms=int((time.time() - start_time) * 1000),
                result_data={
                    "search_query": search_query,
                    "search_path": search_path,
                    "file_type": file_type,
                    "results": results,
                    "count": len(results)
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="find_files",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"File search error: {str(e)}"
            )

    async def _find_files_windows(self, query: str, path: str, file_type: Optional[str], max_results: int) -> List[Dict[str, Any]]:
        """Find files on Windows."""
        try:
            # Use PowerShell for file search
            ps_script = f"""
            Get-ChildItem -Path "{path}" -Recurse -File |
            Where-Object {{ $_.Name -like "*{query}*" }} |
            Select-Object FullName, Name, Length, LastWriteTime |
            Select-Object -First {max_results} |
            ConvertTo-Json
            """

            cmd = ["powershell", "-Command", ps_script]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                try:
                    files_data = json.loads(stdout.decode('utf-8'))
                    if isinstance(files_data, list):
                        return files_data
                    elif isinstance(files_data, dict):
                        return [files_data]
                except json.JSONDecodeError:
                    pass

            return []

        except Exception as e:
            logger.error(f"Windows file search error: {e}")
            return []

    async def _find_files_linux(self, query: str, path: str, file_type: Optional[str], max_results: int) -> List[Dict[str, Any]]:
        """Find files on Linux."""
        try:
            # Use find command
            cmd = ["find", path, "-type", "f", "-iname", f"*{query}*"]

            if file_type:
                cmd.extend(["-name", f"*{file_type}*"])

            cmd.extend(["-head", str(max_results)])

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                files = stdout.decode('utf-8').strip().split('\n')
                results = []
                for file_path in files:
                    if file_path.strip():
                        try:
                            stat = os.stat(file_path)
                            results.append({
                                "FullName": file_path,
                                "Name": os.path.basename(file_path),
                                "Length": stat.st_size,
                                "LastWriteTime": stat.st_mtime
                            })
                        except OSError:
                            continue
                return results

            return []

        except Exception as e:
            logger.error(f"Linux file search error: {e}")
            return []

    async def _find_files_macos(self, query: str, path: str, file_type: Optional[str], max_results: int) -> List[Dict[str, Any]]:
        """Find files on macOS."""
        try:
            # Use mdfind (Spotlight)
            cmd = ["mdfind", "-name", query, "-onlyin", path]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                files = stdout.decode('utf-8').strip().split('\n')
                results = []
                for file_path in files[:max_results]:
                    if file_path.strip():
                        try:
                            stat = os.stat(file_path)
                            results.append({
                                "FullName": file_path,
                                "Name": os.path.basename(file_path),
                                "Length": stat.st_size,
                                "LastWriteTime": stat.st_mtime
                            })
                        except OSError:
                            continue
                return results

            return []

        except Exception as e:
            logger.error(f"macOS file search error: {e}")
            return []

    async def get_system_info(self, action: SystemAction = None) -> SystemActionResult:
        """
        Get system information.

        Args:
            action: SystemAction (optional)

        Returns:
            SystemActionResult with system information
        """
        start_time = time.time()

        try:
            # Gather system information
            info = {
                "os": {
                    "name": platform.system(),
                    "version": platform.version(),
                    "release": platform.release(),
                    "machine": platform.machine()
                },
                "processor": {
                    "name": platform.processor(),
                    "architecture": platform.architecture()[0],
                    "cores": psutil.cpu_count(),
                    "usage_percent": psutil.cpu_percent(interval=1)
                },
                "memory": {
                    "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                    "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                    "usage_percent": psutil.virtual_memory().percent
                },
                "disk": {
                    "total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                    "free_gb": round(psutil.disk_usage('/').free / (1024**3), 2),
                    "usage_percent": psutil.disk_usage('/').percent
                },
                "network": {},
                "user": {
                    "current_user": os.getlogin(),
                    "admin_privileges": self.admin_privileges
                }
            }

            # Add network information
            try:
                network_info = psutil.net_if_addrs()
                info["network"]["interfaces"] = list(network_info.keys())

                # Get primary IP
                for interface, addresses in network_info.items():
                    for addr in addresses:
                        if addr.family.name == 'AF_INET' and not addr.address.startswith('127.'):
                            info["network"]["primary_ip"] = addr.address
                            info["network"]["primary_interface"] = interface
                            break
                    if "primary_ip" in info["network"]:
                        break
            except Exception:
                pass

            return SystemActionResult(
                success=True,
                action_type="system_info",
                execution_time_ms=int((time.time() - start_time) * 1000),
                result_data=info
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="system_info",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"System info error: {str(e)}"
            )

    async def _find_windows_application(self, app_name: str) -> Optional[str]:
        """Find Windows application by name."""
        try:
            # Search in common locations
            search_paths = [
                os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files")),
                os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
                os.path.join(os.environ.get("APPDATA", ""), "Microsoft\\Windows\\Start Menu\\Programs")
            ]

            for search_path in search_paths:
                if os.path.exists(search_path):
                    for root, dirs, files in os.walk(search_path):
                        for file in files:
                            if file.lower().endswith('.exe') and app_name.lower() in file.lower():
                                return os.path.join(root, file)

            return None

        except Exception:
            return None

    async def _find_linux_application(self, app_name: str) -> Optional[str]:
        """Find Linux application by name."""
        try:
            # Use 'which' command to find in PATH
            process = await asyncio.create_subprocess_exec(
                "which", app_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and stdout:
                return stdout.decode('utf-8').strip()

            # Search in common application directories
            search_paths = [
                "/usr/bin",
                "/usr/local/bin",
                "/snap/bin",
                "/opt"
            ]

            for search_path in search_paths:
                if os.path.exists(search_path):
                    for file in os.listdir(search_path):
                        if app_name.lower() in file.lower():
                            return os.path.join(search_path, file)

            return None

        except Exception:
            return None

    async def _find_macos_application(self, app_name: str) -> Optional[str]:
        """Find macOS application by name."""
        try:
            # Search in Applications folder
            search_paths = [
                "/Applications",
                os.path.expanduser("~/Applications")
            ]

            for search_path in search_paths:
                if os.path.exists(search_path):
                    for file in os.listdir(search_path):
                        if file.endswith('.app') and app_name.lower() in file.lower():
                            return os.path.join(search_path, file)

            return None

        except Exception:
            return None

    async def execute_action(self, action: Action) -> SystemActionResult:
        """
        Execute an Action from the new data model.
        Adapts to internal SystemAction/CommandAction logic.
        """
        if action.action_type == ModelActionType.SYSTEM_FILE_FIND:
            pattern = action.parameters.get("pattern", "*")
            path = action.parameters.get("path", ".")
            file_type = action.parameters.get("file_type")
            max_results = action.parameters.get("max_results", 100)
            
            sys_action = SystemAction(
                action_type="find_files",
                parameters={
                    "search_query": pattern,
                    "search_path": path,
                    "file_type": file_type,
                    "max_results": max_results
                }
            )
            return await self.find_files(sys_action)

        elif action.action_type == ModelActionType.SYSTEM_FILE_DELETE:
            file_path = action.parameters.get("file_path")
            confirmed = action.parameters.get("confirmed", False)
            
            sys_action = SystemAction(
                action_type="delete_file",
                target=file_path,
                parameters={
                    "path": file_path,
                    "force": confirmed
                }
            )
            return await self.delete_file(sys_action)

        elif action.action_type == ModelActionType.SYSTEM_INFO:
            sys_action = SystemAction(
                action_type="query_system_info",
                parameters={}
            )
            return await self.get_system_info(sys_action)
            
        else:
            return SystemActionResult(
                success=False,
                action_type=str(action.action_type),
                execution_time_ms=0,
                stderr=f"Unsupported action type: {action.action_type}"
            )

    async def execute(self, action: CommandAction) -> Dict[str, Any]:
        """
        Execute a command action based on MCP tool routing.

        Args:
            action: CommandAction with operation and parameters

        Returns:
            Dictionary with execution result
        """
        try:
            start_time = time.time()

            # Convert CommandAction to SystemAction
            system_action = SystemAction(
                action_type=action.action_type.value,
                target=action.operation,
                parameters=action.parameters,
                timeout_seconds=30
            )

            # Route to appropriate handler based on action type
            if action.action_type == ActionType.SYSTEM:
                if action.operation == "launch_application":
                    result = await self.launch_application(system_action)
                elif action.operation == "adjust_volume":
                    result = await self.set_volume(system_action)
                elif action.operation == "find_files":
                    result = await self.find_files(system_action)
                elif action.operation == "delete_file":
                    result = await self.delete_file(system_action)
                elif action.operation == "query_system_info":
                    result = await self.get_system_info(system_action)
                else:
                    result = SystemActionResult(
                        success=False,
                        action_type="system",
                        execution_time_ms=0,
                        error_message=f"Bilinmeyen sistem işlemi: {action.operation}"
                    )

            elif action.action_type == ActionType.BROWSER:
                # Browser actions will be handled by browser controller
                result = SystemActionResult(
                    success=False,
                    action_type="browser",
                    execution_time_ms=0,
                    error_message="Tarayıcı işlemleri tarayıcı denetleyicisi tarafından işlenir"
                )

            elif action.action_type == ActionType.QUERY:
                # Query actions
                result = SystemActionResult(
                    success=False,
                    action_type="query",
                    execution_time_ms=0,
                    error_message="Sorgu işlemleri henüz desteklenmiyor"
                )

            else:
                result = SystemActionResult(
                    success=False,
                    action_type="unknown",
                    execution_time_ms=0,
                    error_message=f"Bilinmeyen eylem türü: {action.action_type}"
                )

            # Convert SystemActionResult to expected format
            execution_time = (time.time() - start_time) * 1000

            return {
                "success": result.success,
                "result": result.result_data if result.success else None,
                "error": result.error_message if not result.success else None,
                "execution_time_ms": result.execution_time_ms or execution_time,
                "return_code": result.return_code,
                "stdout": result.stdout,
                "stderr": result.stderr
            }

        except Exception as e:
            logger.error(f"Error executing system action: {e}", exc_info=True)
            execution_time = (time.time() - start_time) * 1000

            return {
                "success": False,
                "result": None,
                "error": f"Sistem işlemi hatası: {str(e)}",
                "execution_time_ms": execution_time
            }

    async def delete_file(self, action: SystemAction) -> SystemActionResult:
        """
        Delete a file with confirmation logic.

        Args:
            action: SystemAction with file deletion parameters

        Returns:
            SystemActionResult with deletion details
        """
        start_time = time.time()

        try:
            file_path = action.parameters.get("path", "")
            force = action.parameters.get("force", False)

            if not file_path:
                return SystemActionResult(
                    success=False,
                    action_type="delete_file",
                    execution_time_ms=0,
                    error_message="Dosya yolu belirtilmedi"
                )

            if not os.path.exists(file_path):
                return SystemActionResult(
                    success=False,
                    action_type="delete_file",
                    execution_time_ms=0,
                    error_message=f"Dosya bulunamadı: {file_path}"
                )

            # Check if it's a protected directory
            protected_dirs = [
                os.path.expanduser("~\\Desktop"),
                os.path.expanduser("~\\Documents"),
                os.path.expanduser("~\\Pictures"),
                "C:\\Windows",
                "C:\\Program Files",
                "C:\\Program Files (x86)"
            ]

            is_protected = any(
                os.path.abspath(file_path).startswith(os.path.abspath(prot_dir))
                for prot_dir in protected_dirs
            )

            if is_protected and not force:
                return SystemActionResult(
                    success=False,
                    action_type="delete_file",
                    execution_time_ms=0,
                    error_message="Korumalı dizindeki dosya silinemez. force=true ile zorlayabilirsiniz."
                )

            # Delete the file
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)

            return SystemActionResult(
                success=True,
                action_type="delete_file",
                execution_time_ms=int((time.time() - start_time) * 1000),
                result_data={
                    "deleted_path": file_path,
                    "protected": is_protected
                }
            )

        except Exception as e:
            return SystemActionResult(
                success=False,
                action_type="delete_file",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Dosya silme hatası: {str(e)}"
            )

    async def cleanup(self) -> None:
        """Cleanup system control service."""
        try:
            # Clean up temporary files
            import shutil
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")


# Global service instance
system_controller = SystemControlService()