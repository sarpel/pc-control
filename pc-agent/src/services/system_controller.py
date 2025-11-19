"""
System Controller Service

Basic system controller for executing voice commands:
- Application launching and management
- Volume control and system settings
- File operations and search
- System information queries
- Process management

Following requirements from spec and test T043.
"""

import asyncio
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Types of system operations."""
    LAUNCH_APPLICATION = "launch_application"
    ADJUST_VOLUME = "adjust_volume"
    FIND_FILES = "find_files"
    DELETE_FILE = "delete_file"
    QUERY_SYSTEM_INFO = "query_system_info"
    OPEN_FILE = "open_file"
    CLOSE_APPLICATION = "close_application"
    # New operations for T073-T079
    QUERY_NETWORK_STATUS = "query_network_status"
    POWER_MANAGEMENT = "power_management"
    CLIPBOARD_OPERATIONS = "clipboard_operations"
    CAPTURE_SCREENSHOT = "capture_screenshot"
    MANAGE_COMMAND_HISTORY = "manage_command_history"
    RETRY_FAILED_OPERATION = "retry_failed_operation"


@dataclass
class SystemCommand:
    """System command to be executed."""
    operation: str
    parameters: Dict[str, Any]
    requires_confirmation: bool = False


@dataclass
class ExecutionResult:
    """Result of system command execution."""
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
    data: Optional[Dict[str, Any]] = None


class SystemController:
    """
    Basic system controller for voice command execution.

    Features:
    - Application launching with common applications
    - Volume control with percentage adjustment
    - Basic file operations (find, delete with confirmation)
    - System information queries
    - Error handling with Turkish messages
    - Execution time tracking
    """

    def __init__(self):
        """Initialize system controller."""
        self.os_type = self._detect_os()
        self.temp_dir = Path.home() / ".pc_control"
        self.temp_dir.mkdir(exist_ok=True)

        # Common applications mapping for Turkish commands
        self.applications = {
            "chrome": "chrome.exe",
            "google chrome": "chrome.exe",
            "firefox": "firefox.exe",
            "mozilla firefox": "firefox.exe",
            "edge": "msedge.exe",
            "microsoft edge": "msedge.exe",
            "notepad": "notepad.exe",
            "not defteri": "notepad.exe",
            "calculator": "calc.exe",
            "hesap makinesi": "calc.exe",
            "explorer": "explorer.exe",
            "dosya gezgini": "explorer.exe",
            "cmd": "cmd.exe",
            "komut istemi": "cmd.exe",
            "powershell": "powershell.exe",
            "task manager": "taskmgr.exe",
            "görev yöneticisi": "taskmgr.exe"
        }

        # System directories (protected)
        self.protected_directories = [
            "C:\\Windows",
            "C:\\Program Files",
            "C:\\Program Files (x86)",
            "C:\\ProgramData"
        ]

        logger.info(f"System controller initialized for {self.os_type}")

    def _detect_os(self) -> str:
        """Detect operating system."""
        import platform
        return platform.system().lower()

    async def execute(self, command: SystemCommand) -> ExecutionResult:
        """
        Execute system command based on operation type.

        Args:
            command: System command to execute

        Returns:
            ExecutionResult with operation details
        """
        start_time = time.time()

        try:
            operation = command.operation.lower()
            parameters = command.parameters or {}

            logger.info(f"Executing system operation: {operation} with params: {parameters}")

            # Route to appropriate handler
            if operation == OperationType.LAUNCH_APPLICATION.value:
                result = await self._launch_application(parameters)
            elif operation == OperationType.ADJUST_VOLUME.value:
                result = await self._adjust_volume(parameters)
            elif operation == OperationType.FIND_FILES.value:
                result = await self._find_files(parameters)
            elif operation == OperationType.DELETE_FILE.value:
                result = await self._delete_file(parameters)
            elif operation == OperationType.QUERY_SYSTEM_INFO.value:
                result = await self._query_system_info(parameters)
            elif operation == OperationType.OPEN_FILE.value:
                result = await self._open_file(parameters)
            elif operation == OperationType.CLOSE_APPLICATION.value:
                result = await self._close_application(parameters)
            elif operation == OperationType.QUERY_NETWORK_STATUS.value:
                result = await self._query_network_status(parameters)
            elif operation == OperationType.POWER_MANAGEMENT.value:
                result = await self._power_management(parameters)
            elif operation == OperationType.CLIPBOARD_OPERATIONS.value:
                result = await self._clipboard_operations(parameters)
            elif operation == OperationType.CAPTURE_SCREENSHOT.value:
                result = await self._capture_screenshot(parameters)
            elif operation == OperationType.MANAGE_COMMAND_HISTORY.value:
                result = await self._manage_command_history(parameters)
            elif operation == OperationType.RETRY_FAILED_OPERATION.value:
                result = await self._retry_failed_operation(parameters)
            else:
                result = ExecutionResult(
                    success=False,
                    error=f"Bilinmeyen işlem: {operation}"
                )

            execution_time = (time.time() - start_time) * 1000
            result.execution_time_ms = execution_time

            logger.info(f"Operation completed: {operation}, success: {result.success}, time: {execution_time:.1f}ms")
            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = f"Sistem hatası: {str(e)}"
            logger.error(f"System operation failed: {error_msg}")

            return ExecutionResult(
                success=False,
                error=error_msg,
                execution_time_ms=execution_time
            )

    async def _launch_application(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Launch application with given parameters.

        Args:
            params: Dictionary with 'application' and optional 'arguments'

        Returns:
            ExecutionResult
        """
        app_name = params.get("application", "").lower()
        arguments = params.get("arguments", [])

        if not app_name:
            return ExecutionResult(
                success=False,
                error="Uygulama adı belirtilmedi"
            )

        # Find executable for application
        executable = self._find_executable(app_name)

        if not executable:
            return ExecutionResult(
                success=False,
                error=f"Uygulama bulunamadı: {app_name}"
            )

        try:
            # Build command
            cmd = [executable] + arguments

            # Launch application
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait briefly to check if it started successfully
            await asyncio.wait_for(
                process.wait(),
                timeout=2.0  # 2 second timeout
            )

            # Process finished quickly - likely an error
            if process.returncode != 0:
                stderr = await process.stderr.read()
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Uygulama başlatılamadı"
                return ExecutionResult(
                    success=False,
                    error=f"Uygulama başlatılamadı: {error_msg}"
                )

            return ExecutionResult(
                success=True,
                result=f"{app_name} başlatıldı"
            )

        except asyncio.TimeoutError:
            # Process is still running - success for GUI apps
            return ExecutionResult(
                success=True,
                result=f"{app_name} başlatıldı"
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Uygulama başlatma hatası: {str(e)}"
            )

    async def _adjust_volume(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Adjust system volume.

        Args:
            params: Dictionary with 'level' (0-100) and optional 'mute'

        Returns:
            ExecutionResult
        """
        try:
            level = params.get("level")
            mute = params.get("mute")

            if mute is not None:
                if self.os_type == "windows":
                    # Windows volume mute/unmute using PowerShell
                    ps_cmd = f"(New-Object -comObject WScript.Shell).SendKeys([char]175)"  # Volume mute key
                    if not mute:
                        ps_cmd = f"(New-Object -comObject WScript.Shell).SendKeys([char]175)"  # Unmute

                    process = await asyncio.create_subprocess_exec(
                        "powershell", "-Command", ps_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await process.wait()

                    action = "ses kapatıldı" if mute else "ses açıldı"
                    return ExecutionResult(success=True, result=action)

            if level is not None:
                if not (0 <= level <= 100):
                    return ExecutionResult(
                        success=False,
                        error="Seviye 0-100 arasında olmalıdır"
                    )

                if self.os_type == "windows":
                    # Windows volume control using PowerShell
                    volume_ps = f"""
                    Add-Type -TypeDefinition '
                    using System;
                    using System.Runtime.InteropServices;
                    public class Audio {{
                        [DllImport("winmm.dll")]
                        public static extern int waveOutSetVolume(IntPtr hwo, uint dwVolume);
                        [DllImport("winmm.dll")]
                        public static extern int waveOutGetVolume(IntPtr hwo, out uint dwVolume);
                        public static void SetVolume(uint volume) {{
                            waveOutSetVolume(IntPtr.Zero, (volume << 16) | volume);
                        }}
                    }}'
                    [Audio]::SetVolume({int(level * 655.35)})
                    """

                    process = await asyncio.create_subprocess_exec(
                        "powershell", "-Command", volume_ps,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    stdout, stderr = await process.communicate()

                    if process.returncode == 0:
                        return ExecutionResult(
                            success=True,
                            result=f"Ses seviyesi %{level} olarak ayarlandı"
                        )
                    else:
                        error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Ses ayarı başarısız"
                        return ExecutionResult(
                            success=False,
                            error=f"Ses ayarı başarısız: {error_msg}"
                        )
                else:
                    # Placeholder for Linux/Mac
                    return ExecutionResult(
                        success=False,
                        error="Ses kontrolü bu işletim sistemi için henüz desteklenmiyor"
                    )

            return ExecutionResult(
                success=False,
                error="Geçerli bir ses seviyesi veya mute parametresi belirtilmedi"
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Ses ayarlama hatası: {str(e)}"
            )

    async def _find_files(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Find files matching search criteria.

        Args:
            params: Dictionary with 'pattern' and optional 'directory'

        Returns:
            ExecutionResult
        """
        try:
            pattern = params.get("pattern", "")
            directory = params.get("directory", str(Path.home()))
            max_results = params.get("max_results", 20)

            if not pattern:
                return ExecutionResult(
                    success=False,
                    error="Arama deseni belirtilmedi"
                )

            search_path = Path(directory)
            if not search_path.exists():
                return ExecutionResult(
                    success=False,
                    error=f"Dizin bulunamadı: {directory}"
                )

            # Find files
            found_files = []
            try:
                for file_path in search_path.rglob(f"*{pattern}*"):
                    if file_path.is_file() and len(found_files) < max_results:
                        found_files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "size": file_path.stat().st_size,
                            "modified": file_path.stat().st_mtime
                        })
            except PermissionError:
                return ExecutionResult(
                    success=False,
                    error=f"Dizin erişim izni reddedildi: {directory}"
                )

            if not found_files:
                return ExecutionResult(
                    success=True,
                    result=f"'{pattern}' deseni için dosya bulunamadı",
                    data={"files": []}
                )

            result_msg = f"{len(found_files)} dosya bulundu"
            return ExecutionResult(
                success=True,
                result=result_msg,
                data={"files": found_files[:max_results]}
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Dosya arama hatası: {str(e)}"
            )

    async def _delete_file(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Delete file with safety checks.

        Args:
            params: Dictionary with 'path' and optional 'force'

        Returns:
            ExecutionResult
        """
        try:
            file_path_str = params.get("path", "")
            force = params.get("force", False)

            if not file_path_str:
                return ExecutionResult(
                    success=False,
                    error="Dosya yolu belirtilmedi"
                )

            file_path = Path(file_path_str)

            # Safety checks
            if not file_path.exists():
                return ExecutionResult(
                    success=False,
                    error=f"Dosya bulunamadı: {file_path_str}"
                )

            # Check if it's in protected directory
            for protected_dir in self.protected_directories:
                if str(file_path).lower().startswith(protected_dir.lower()):
                    return ExecutionResult(
                        success=False,
                        error=f"Korumalı dizindeki dosyalar silinemez: {protected_dir}"
                    )

            # Check if it's a directory (require confirmation)
            if file_path.is_dir():
                return ExecutionResult(
                    success=False,
                    error="Dizin silme işlemi için ek onay gerekli"
                )

            # Delete file
            file_path.unlink()

            return ExecutionResult(
                success=True,
                result=f"Dosya silindi: {file_path.name}"
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Dosya silme hatası: {str(e)}"
            )

    async def _query_system_info(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Query system information.

        Args:
            params: Dictionary with 'info_type'

        Returns:
            ExecutionResult
        """
        try:
            info_type = params.get("info_type", "basic").lower()

            system_info = {}

            if info_type in ["basic", "all"]:
                system_info.update({
                    "os": self.os_type,
                    "python_version": os.sys.version,
                    "current_directory": os.getcwd(),
                    "home_directory": str(Path.home())
                })

            if info_type in ["memory", "all"]:
                try:
                    import psutil
                    memory = psutil.virtual_memory()
                    system_info["memory"] = {
                        "total_gb": round(memory.total / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "used_percent": memory.percent
                    }
                except ImportError:
                    system_info["memory"] = "psutil not available"

            if info_type in ["disk", "all"]:
                try:
                    import psutil
                    disk = psutil.disk_usage('/')
                    system_info["disk"] = {
                        "total_gb": round(disk.total / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "used_percent": round((disk.used / disk.total) * 100, 2)
                    }
                except ImportError:
                    system_info["disk"] = "psutil not available"

            if info_type in ["cpu", "all"]:
                try:
                    import psutil
                    system_info["cpu"] = {
                        "percent": psutil.cpu_percent(interval=1),
                        "count": psutil.cpu_count()
                    }
                except ImportError:
                    system_info["cpu"] = "psutil not available"

            return ExecutionResult(
                success=True,
                result="Sistem bilgileri alındı",
                data=system_info
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Sistem bilgisi alma hatası: {str(e)}"
            )

    async def _open_file(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Open file with default application.

        Args:
            params: Dictionary with 'path'

        Returns:
            ExecutionResult
        """
        try:
            file_path_str = params.get("path", "")

            if not file_path_str:
                return ExecutionResult(
                    success=False,
                    error="Dosya yolu belirtilmedi"
                )

            file_path = Path(file_path_str)

            if not file_path.exists():
                return ExecutionResult(
                    success=False,
                    error=f"Dosya bulunamadı: {file_path_str}"
                )

            if self.os_type == "windows":
                # Windows: use start command
                process = await asyncio.create_subprocess_exec(
                    "cmd", "/c", "start", "", str(file_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()
            else:
                # Linux/Mac: use xdg-open/open
                opener = "xdg-open" if self.os_type == "linux" else "open"
                process = await asyncio.create_subprocess_exec(
                    opener, str(file_path),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.wait()

            return ExecutionResult(
                success=True,
                result=f"Dosya açıldı: {file_path.name}"
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Dosya açma hatası: {str(e)}"
            )

    async def _close_application(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Close running application.

        Args:
            params: Dictionary with 'application' name

        Returns:
            ExecutionResult
        """
        try:
            app_name = params.get("application", "").lower()

            if not app_name:
                return ExecutionResult(
                    success=False,
                    error="Uygulama adı belirtilmedi"
                )

            executable = self._find_executable(app_name)
            if not executable:
                return ExecutionResult(
                    success=False,
                    error=f"Uygulama bulunamadı: {app_name}"
                )

            if self.os_type == "windows":
                # Windows: use taskkill
                process_name = Path(executable).stem
                cmd = ["taskkill", "/F", "/IM", f"{process_name}.exe"]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    return ExecutionResult(
                        success=True,
                        result=f"{app_name} kapatıldı"
                    )
                else:
                    error_output = stderr.decode('utf-8', errors='ignore')
                    if "not found" in error_output.lower():
                        return ExecutionResult(
                            success=False,
                            error=f"{app_name} çalışmıyor"
                        )
                    else:
                        return ExecutionResult(
                            success=False,
                            error=f"{app_name} kapatılamadı: {error_output}"
                        )
            else:
                # Linux/Mac: use pkill
                process = await asyncio.create_subprocess_exec(
                    "pkill", "-f", executable,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                return ExecutionResult(
                    success=True,
                    result=f"{app_name} kapatıldı"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Uygulama kapatma hatası: {str(e)}"
            )

    async def _query_network_status(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Query network configuration and status.

        Args:
            params: Dictionary with optional 'detailed' flag

        Returns:
            ExecutionResult with network information
        """
        try:
            detailed = params.get("detailed", False)
            network_info = {}

            if self.os_type == "windows":
                # Windows network commands
                try:
                    # Get network interfaces
                    process = await asyncio.create_subprocess_exec(
                        "ipconfig", "/all",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    ipconfig_output = stdout.decode('utf-8', errors='ignore')
                    
                    # Parse basic network info
                    import re
                    
                    # Get IP addresses
                    ip_pattern = r'IPv4 Address[^\d]*:\s*([\d.]+)'
                    ips = re.findall(ip_pattern, ipconfig_output)
                    
                    # Get default gateway
                    gateway_pattern = r'Default Gateway[^\d]*:\s*([\d.]+)'
                    gateways = re.findall(gateway_pattern, ipconfig_output)
                    
                    # Get DNS servers
                    dns_pattern = r'DNS Servers[^\d]*:\s*([\d.]+)'
                    dns_servers = re.findall(dns_pattern, ipconfig_output)
                    
                    network_info = {
                        "ip_addresses": ips,
                        "default_gateway": gateways[0] if gateways else None,
                        "dns_servers": dns_servers[:2],  # First 2 DNS servers
                        "interfaces_count": ipconfig_output.count("adapter")
                    }
                    
                    if detailed:
                        network_info["raw_ipconfig"] = ipconfig_output
                        
                except Exception as e:
                    logger.error(f"Network query error: {e}")
                    network_info = {"error": "Ağ bilgileri alınamadı"}

                # Test internet connectivity
                try:
                    process = await asyncio.create_subprocess_exec(
                        "ping", "-n", "1", "8.8.8.8",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        network_info["internet_connected"] = True
                        network_info["dns_working"] = True
                    else:
                        network_info["internet_connected"] = False
                        network_info["dns_working"] = False
                        
                except Exception:
                    network_info["internet_connected"] = False
                    network_info["dns_working"] = False

            return ExecutionResult(
                success=True,
                result="Ağ durumu bilgileri alındı",
                data=network_info
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Ağ durumu sorgulama hatası: {str(e)}"
            )

    async def _power_management(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Power management operations (shutdown, restart, sleep).

        Args:
            params: Dictionary with 'action' and optional 'force' flag

        Returns:
            ExecutionResult
        """
        try:
            action = params.get("action", "").lower()
            force = params.get("force", False)
            delay_seconds = params.get("delay", 0)

            if action not in ["shutdown", "restart", "sleep", "hibernate"]:
                return ExecutionResult(
                    success=False,
                    error=f"Geçersiz güç yönetimi işlemi: {action}"
                )

            if self.os_type == "windows":
                if action == "shutdown":
                    cmd = ["shutdown", "/s"]
                    if force:
                        cmd.append("/f")
                    if delay_seconds > 0:
                        cmd.append(f"/t {delay_seconds}")
                elif action == "restart":
                    cmd = ["shutdown", "/r"]
                    if force:
                        cmd.append("/f")
                    if delay_seconds > 0:
                        cmd.append(f"/t {delay_seconds}")
                elif action == "sleep":
                    cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
                elif action == "hibernate":
                    cmd = ["shutdown", "/h"]

                # Execute power command
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Don't wait for completion as system may shut down
                action_names = {
                    "shutdown": "Bilgisayar kapatılıyor",
                    "restart": "Bilgisayar yeniden başlatılıyor",
                    "sleep": "Bilgisayar uyku moduna geçiyor",
                    "hibernate": "Bilgisayar hibernate moduna geçiyor"
                }

                return ExecutionResult(
                    success=True,
                    result=action_names.get(action, f"İşlem gerçekleştiriliyor: {action}"),
                    data={"action": action, "delay": delay_seconds}
                )

            else:
                # Linux/Mac power commands
                if action == "shutdown":
                    cmd = ["shutdown", "-h", f"+{delay_seconds//60}"] if delay_seconds > 0 else ["shutdown", "-h", "now"]
                elif action == "restart":
                    cmd = ["shutdown", "-r", f"+{delay_seconds//60}"] if delay_seconds > 0 else ["shutdown", "-r", "now"]
                elif action == "sleep":
                    cmd = ["systemctl", "suspend"]
                elif action == "hibernate":
                    cmd = ["systemctl", "hibernate"]

                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                return ExecutionResult(
                    success=True,
                    result=f"İşlem gerçekleştiriliyor: {action}"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Güç yönetimi hatası: {str(e)}"
            )

    async def _clipboard_operations(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Clipboard operations (copy, paste, clear).

        Args:
            params: Dictionary with 'operation' and optional 'text'

        Returns:
            ExecutionResult
        """
        try:
            operation = params.get("operation", "").lower()
            text = params.get("text", "")

            if self.os_type == "windows":
                if operation == "copy":
                    if not text:
                        return ExecutionResult(
                            success=False,
                            error="Kopyalanacak metin belirtilmedi"
                        )
                    
                    # Use PowerShell for clipboard operations
                    ps_script = f'Set-Clipboard -Value "{text}"'
                    process = await asyncio.create_subprocess_exec(
                        "powershell", "-Command", ps_script,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()

                    if process.returncode == 0:
                        return ExecutionResult(
                            success=True,
                            result="Metin panoya kopyalandı"
                        )
                    else:
                        return ExecutionResult(
                            success=False,
                            error="Panoya kopyalama başarısız"
                        )

                elif operation == "paste":
                    ps_script = 'Get-Clipboard'
                    process = await asyncio.create_subprocess_exec(
                        "powershell", "-Command", ps_script,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()

                    if process.returncode == 0:
                        clipboard_content = stdout.decode('utf-8', errors='ignore').strip()
                        return ExecutionResult(
                            success=True,
                            result="Panodan metin alındı",
                            data={"text": clipboard_content}
                        )
                    else:
                        return ExecutionResult(
                            success=False,
                            error="Panodan metin alma başarısız"
                        )

                elif operation == "clear":
                    ps_script = 'Set-Clipboard -Value ""'
                    process = await asyncio.create_subprocess_exec(
                        "powershell", "-Command", ps_script,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()

                    return ExecutionResult(
                        success=True,
                        result="Pano temizlendi"
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        error=f"Geçersiz pano işlemi: {operation}"
                    )
            else:
                # Linux/Mac clipboard operations
                if operation == "copy":
                    if not text:
                        return ExecutionResult(
                            success=False,
                            error="Kopyalanacak metin belirtilmedi"
                        )
                    
                    # Use xclip for Linux, pbcopy for Mac
                    if self.os_type == "linux":
                        process = await asyncio.create_subprocess_exec(
                            "xclip", "-selection", "clipboard",
                            stdin=asyncio.subprocess.PIPE
                        )
                        process.communicate(text.encode())
                    else:  # Mac
                        process = await asyncio.create_subprocess_exec(
                            "pbcopy",
                            stdin=asyncio.subprocess.PIPE
                        )
                        process.communicate(text.encode())

                    return ExecutionResult(
                        success=True,
                        result="Metin panoya kopyalandı"
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        error=f"Pano işlemi bu platformda desteklenmiyor: {operation}"
                    )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Pano işlemi hatası: {str(e)}"
            )

    async def _capture_screenshot(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Capture screenshot.

        Args:
            params: Dictionary with optional 'area' and 'path'

        Returns:
            ExecutionResult with screenshot info
        """
        try:
            area = params.get("area", "full")  # full, window, region
            save_path = params.get("path", "")

            timestamp = int(time.time())
            if not save_path:
                save_path = str(self.temp_dir / f"screenshot_{timestamp}.png")

            if self.os_type == "windows":
                # Use PowerShell to take screenshot
                if area == "full":
                    ps_script = f"""
                    Add-Type -AssemblyName System.Windows.Forms
                    Add-Type -AssemblyName System.Drawing
                    $screen = [System.Windows.Forms.Screen]::PrimaryScreen
                    $bitmap = New-Object System.Drawing.Bitmap $screen.Bounds.Width, $screen.Bounds.Height
                    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                    $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
                    $bitmap.Save('{save_path}', [System.Drawing.Imaging.ImageFormat]::Png)
                    $graphics.Dispose()
                    $bitmap.Dispose()
                    """
                else:
                    # For simplicity, capture full screen for other areas
                    ps_script = f"""
                    Add-Type -AssemblyName System.Windows.Forms
                    Add-Type -AssemblyName System.Drawing
                    $screen = [System.Windows.Forms.Screen]::PrimaryScreen
                    $bitmap = New-Object System.Drawing.Bitmap $screen.Bounds.Width, $screen.Bounds.Height
                    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                    $graphics.CopyFromScreen($screen.Bounds.Location, [System.Drawing.Point]::Empty, $screen.Bounds.Size)
                    $bitmap.Save('{save_path}', [System.Drawing.Imaging.ImageFormat]::Png)
                    $graphics.Dispose()
                    $bitmap.Dispose()
                    """

                process = await asyncio.create_subprocess_exec(
                    "powershell", "-Command", ps_script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    return ExecutionResult(
                        success=True,
                        result=f"Ekran görüntüsü kaydedildi: {save_path}",
                        data={"path": save_path, "area": area}
                    )
                else:
                    return ExecutionResult(
                        success=False,
                        error="Ekran görüntüsü alınamadı"
                    )
            else:
                # Linux/Mac screenshot (using scrot or similar)
                return ExecutionResult(
                    success=False,
                    error="Ekran görüntüsü bu platformda desteklenmiyor"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Ekran görüntüsü hatası: {str(e)}"
            )

    async def _manage_command_history(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Manage command history operations.

        Args:
            params: Dictionary with 'operation' and optional parameters

        Returns:
            ExecutionResult
        """
        try:
            operation = params.get("operation", "").lower()

            if operation == "list":
                # Get command history (simplified for now)
                history_file = self.temp_dir / "command_history.json"
                if history_file.exists():
                    import json
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                    
                    return ExecutionResult(
                        success=True,
                        result="Komut geçmişi alındı",
                        data={"history": history[-10:], "total": len(history)}  # Last 10 commands
                    )
                else:
                    return ExecutionResult(
                        success=True,
                        result="Komut geçmişi bulunamadı",
                        data={"history": [], "total": 0}
                    )
            elif operation == "clear":
                # Clear command history
                history_file = self.temp_dir / "command_history.json"
                if history_file.exists():
                    history_file.unlink()
                
                return ExecutionResult(
                    success=True,
                    result="Komut geçmişi temizlendi"
                )
            else:
                return ExecutionResult(
                    success=False,
                    error=f"Geçersiz komut geçmişi işlemi: {operation}"
                )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Komut geçmişi yönetimi hatası: {str(e)}"
            )

    async def _retry_failed_operation(self, params: Dict[str, Any]) -> ExecutionResult:
        """
        Retry a failed operation with exponential backoff.

        Args:
            params: Dictionary with operation details and retry config

        Returns:
            ExecutionResult
        """
        try:
            operation = params.get("operation", "")
            max_retries = params.get("max_retries", 3)
            base_delay = params.get("base_delay", 1.0)
            operation_params = params.get("parameters", {})

            if not operation:
                return ExecutionResult(
                    success=False,
                    error="Yeniden denenecek işlem belirtilmedi"
                )

            last_result = None
            for attempt in range(max_retries + 1):
                try:
                    # Execute the operation
                    result = await self.execute(SystemCommand(
                        operation=operation,
                        parameters=operation_params
                    ))

                    if result.success:
                        return ExecutionResult(
                            success=True,
                            result=f"İşlem {attempt + 1}. denemede başarılı",
                            data={"attempts": attempt + 1}
                        )
                    else:
                        last_result = result
                        if attempt < max_retries:
                            # Exponential backoff
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)

                except Exception as e:
                    last_result = ExecutionResult(
                        success=False,
                        error=f"Deneme {attempt + 1} başarısız: {str(e)}"
                    )
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)

            return ExecutionResult(
                success=False,
                error=f"İşlem {max_retries + 1} denemede başarısız: {last_result.error if last_result else 'Bilinmeyen hata'}",
                data={"attempts": max_retries + 1, "last_error": last_result.error if last_result else None}
            )

        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Yeniden deneme hatası: {str(e)}"
            )

    def _find_executable(self, app_name: str) -> Optional[str]:
        """
        Find executable for application name.

        Args:
            app_name: Application name (Turkish or English)

        Returns:
            Executable path or None
        """
        # Check direct mappings
        if app_name in self.applications:
            return self.applications[app_name]

        # Check if app_name already looks like an executable
        if app_name.endswith('.exe'):
            return app_name

        # Try to find in PATH
        import shutil
        executable = shutil.which(app_name)
        if executable:
            return executable

        # Try with .exe extension on Windows
        if self.os_type == "windows":
            executable = shutil.which(f"{app_name}.exe")
            if executable:
                return executable

        return None

    def get_supported_operations(self) -> List[str]:
        """
        Get list of supported system operations.

        Returns:
            List of operation names
        """
        return [op.value for op in OperationType]

    def _is_admin(self) -> bool:
        """Check if the process has admin privileges."""
        try:
            if self.os_type == "windows":
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                import os
                return os.geteuid() == 0
        except Exception:
            return False

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on system controller.

        Returns:
            Health check result
        """
        return {
            "os_type": self.os_type,
            "admin_privileges": self._is_admin(),
            "supported_operations": self.get_supported_operations(),
            "applications_mapped": len(self.applications),
            "temp_directory": str(self.temp_dir),
            "protected_directories": self.protected_directories
        }


# Global service instance
system_controller = SystemController()