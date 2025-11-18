"""
Chrome DevTools MCP Server for Browser Automation

This module implements MCP tools for controlling Chrome browser via DevTools protocol:
- Navigate to URLs and perform searches
- Extract page content and summaries
- Interact with page elements (click, type, scroll)
- Page status monitoring and error handling
- Turkish language support for browser operations

Following requirements from spec and tasks T060-T067.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import aiohttp
import websockets
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)


class BrowserAction(Enum):
    """Browser interaction actions."""
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"


class SearchEngine(Enum):
    """Supported search engines."""
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"


@dataclass
class BrowserState:
    """Current browser state information."""
    is_connected: bool = False
    current_url: str = ""
    page_title: str = ""
    is_loading: bool = False
    websocket_url: str = ""
    session_id: str = ""


@dataclass
class BrowserResult:
    """Result of a browser operation."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time_ms: Optional[float] = None


class ChromeDevToolsMCP:
    """
    Chrome DevTools MCP server implementation.

    Features:
    - WebSocket connection to Chrome DevTools protocol
    - Page navigation and search functionality
    - Content extraction and summarization
    - Element interaction (click, type, scroll)
    - Error handling with Turkish messages
    - Performance monitoring
    """

    def __init__(self):
        self.state = BrowserState()
        self.chrome_debug_port = 9222  # Default Chrome debug port
        self.timeout_ms = 15000  # Default timeout
        self.session = None
        self.websocket = None

    async def initialize(self) -> bool:
        """
        Initialize Chrome DevTools connection.

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Check if Chrome is running with remote debugging
            if not await self._check_chrome_availability():
                logger.warning("Chrome not running with remote debugging")
                return False

            # Get list of available tabs
            tabs = await self._get_tabs()
            if not tabs:
                logger.warning("No Chrome tabs available")
                return False

            # Connect to first tab or create new one
            target_tab = tabs[0] if tabs else await self._create_new_tab()
            if not target_tab:
                return False

            # Connect to target tab via WebSocket
            websocket_url = target_tab.get("webSocketDebuggerUrl")
            if not websocket_url:
                return False

            self.websocket = await websockets.connect(websocket_url)
            self.state.websocket_url = websocket_url
            self.state.is_connected = True

            # Enable necessary domains
            await self._enable_domains()

            # Get current page info
            await self._update_page_info()

            logger.info("Chrome DevTools connection established")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Chrome DevTools: {e}")
            return False

    async def browser_navigate(self, url: str, new_tab: bool = False) -> BrowserResult:
        """
        Navigate Chrome browser to specified URL.

        Args:
            url: URL to navigate to
            new_tab: Whether to open in new tab

        Returns:
            BrowserResult with navigation status
        """
        start_time = time.time()

        try:
            if not self.state.is_connected:
                await self.initialize()

            if not self.state.is_connected:
                return BrowserResult(
                    success=False,
                    message="Chrome tarayıcısına bağlanılamadı. Chrome uzaktan hata ayıklama modunda çalıştığınızdan emin olun."
                )

            # Validate URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            # Navigate to URL
            await self._send_command("Page.navigate", {"url": url})

            # Wait for page to load
            await self._wait_for_page_load()

            # Get page information
            await self._update_page_info()

            execution_time = (time.time() - start_time) * 1000

            return BrowserResult(
                success=True,
                message=f"Sayfa başarıyla yüklendi: {self.state.page_title}",
                data={
                    "url": self.state.current_url,
                    "pageTitle": self.state.page_title,
                    "loadTimeMs": execution_time
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Browser navigation failed: {e}")

            return BrowserResult(
                success=False,
                message=f"Sayfa yüklenemedi: {str(e)}",
                execution_time_ms=execution_time
            )

    async def browser_search(self, query: str, search_engine: str = "google") -> BrowserResult:
        """
        Perform web search in Chrome.

        Args:
            query: Search query
            search_engine: Search engine to use (google, bing, duckduckgo)

        Returns:
            BrowserResult with search status
        """
        start_time = time.time()

        try:
            if not self.state.is_connected:
                await self.initialize()

            # Build search URL based on search engine
            search_urls = {
                "google": f"https://www.google.com/search?q={quote(query)}",
                "bing": f"https://www.bing.com/search?q={quote(query)}",
                "duckduckgo": f"https://duckduckgo.com/?q={quote(query)}"
            }

            search_url = search_urls.get(search_engine.lower(), search_urls["google"])

            # Navigate to search results
            result = await self.browser_navigate(search_url)

            execution_time = (time.time() - start_time) * 1000

            if result.success:
                return BrowserResult(
                    success=True,
                    message=f"'{query}' için arama sonuçları gösteriliyor",
                    data={
                        "resultsUrl": search_url,
                        "searchEngine": search_engine,
                        "pageTitle": self.state.page_title
                    },
                    execution_time_ms=execution_time
                )
            else:
                return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Browser search failed: {e}")

            return BrowserResult(
                success=False,
                message=f"Arama başarısız oldu: {str(e)}",
                execution_time_ms=execution_time
            )

    async def browser_extract_content(self, summary_length: str = "brief") -> BrowserResult:
        """
        Extract and summarize current page content.

        Args:
            summary_length: Length of content summary ("brief" or "detailed")

        Returns:
            BrowserResult with extracted content
        """
        start_time = time.time()

        try:
            if not self.state.is_connected:
                return BrowserResult(
                    success=False,
                    message="Tarayıcıya bağlı değil. Önce bir sayfa yükleyin."
                )

            # Get page content
            content_result = await self._send_command("Runtime.evaluate", {
                "expression": """
                    (function() {
                        // Extract main content from page
                        const title = document.title;
                        const url = window.location.href;

                        // Get text content from main content areas
                        const contentSelectors = [
                            'main', 'article', '.content', '.post-content',
                            '#content', '.entry-content', 'body'
                        ];

                        let textContent = '';
                        for (const selector of contentSelectors) {
                            const element = document.querySelector(selector);
                            if (element) {
                                textContent = element.innerText || element.textContent || '';
                                break;
                            }
                        }

                        // Fallback to body if no content found
                        if (!textContent) {
                            textContent = document.body.innerText || document.body.textContent || '';
                        }

                        // Clean up text
                        textContent = textContent
                            .replace(/\\s+/g, ' ')
                            .replace(/\\n{3,}/g, '\\n\\n')
                            .trim();

                        // Create summary based on requested length
                        let summary;
                        if (summary_length === 'brief') {
                            summary = textContent.substring(0, 500) + (textContent.length > 500 ? '...' : '');
                        } else {
                            summary = textContent.substring(0, 2000) + (textContent.length > 2000 ? '...' : '');
                        }

                        return {
                            title: title,
                            url: url,
                            summary: summary,
                            fullTextLength: textContent.length
                        };
                    })()
                """
            })

            if not content_result.get("success", False):
                raise Exception(f"Content extraction failed: {content_result}")

            content_data = content_result.get("result", {}).get("value", {})
            execution_time = (time.time() - start_time) * 1000

            return BrowserResult(
                success=True,
                message="Sayfa içeriği başarıyla çıkarıldı",
                data={
                    "title": content_data.get("title", ""),
                    "url": content_data.get("url", ""),
                    "summary": content_data.get("summary", ""),
                    "fullTextLength": content_data.get("fullTextLength", 0)
                },
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Content extraction failed: {e}")

            return BrowserResult(
                success=False,
                message=f"İçerik çıkarılamadı: {str(e)}",
                execution_time_ms=execution_time
            )

    async def browser_interact(self, action: str, selector: str = "", value: str = "") -> BrowserResult:
        """
        Interact with page elements.

        Args:
            action: Interaction type ("click", "type", "scroll")
            selector: CSS selector for target element
            value: Value for "type" action or scroll direction

        Returns:
            BrowserResult with interaction status
        """
        start_time = time.time()

        try:
            if not self.state.is_connected:
                return BrowserResult(
                    success=False,
                    message="Tarayıcıya bağlı değil. Önce bir sayfa yükleyin."
                )

            # Validate action
            if action not in ["click", "type", "scroll"]:
                raise ValueError(f"Geçersiz etkileşim türü: {action}")

            if action in ["click", "type"] and not selector:
                raise Exception(f"'{action}' işlemi için CSS seçici gereklidir")

            # Execute interaction based on action type
            if action == "click":
                result = await self._click_element(selector)
            elif action == "type":
                result = await self._type_text(selector, value)
            elif action == "scroll":
                result = await self._scroll_page(value or "down")

            execution_time = (time.time() - start_time) * 1000

            return BrowserResult(
                success=result["success"],
                message=result["message"],
                execution_time_ms=execution_time
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Browser interaction failed: {e}")

            return BrowserResult(
                success=False,
                message=f"Etkileşim başarısız: {str(e)}",
                execution_time_ms=execution_time
            )

    async def _check_chrome_availability(self) -> bool:
        """Check if Chrome is running with remote debugging."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{self.chrome_debug_port}/json") as response:
                    if response.status == 200:
                        return True
        except Exception:
            pass
        return False

    async def _get_tabs(self) -> List[Dict[str, Any]]:
        """Get list of available Chrome tabs."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://localhost:{self.chrome_debug_port}/json") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            logger.error(f"Failed to get Chrome tabs: {e}")
        return []

    async def _create_new_tab(self) -> Optional[Dict[str, Any]]:
        """Create new Chrome tab."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://localhost:{self.chrome_debug_port}/json/new") as response:
                    if response.status == 200:
                        return await response.json()
        except Exception as e:
            logger.error(f"Failed to create new tab: {e}")
        return None

    async def _enable_domains(self) -> None:
        """Enable necessary DevTools domains."""
        domains = ["Page", "Runtime", "Network", "DOM"]
        for domain in domains:
            await self._send_command(f"{domain}.enable")

    async def _send_command(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send command to Chrome DevTools."""
        if not self.websocket:
            raise Exception("Chrome DevTools WebSocket not connected")

        command = {
            "id": int(time.time() * 1000),
            "method": method,
            "params": params or {}
        }

        await self.websocket.send(json.dumps(command))
        response = await self.websocket.recv()
        return json.loads(response)

    async def _wait_for_page_load(self, timeout: float = 15.0) -> None:
        """Wait for page to finish loading."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = await self._send_command("Runtime.evaluate", {
                    "expression": "document.readyState"
                })
                if result.get("result", {}).get("value") == "complete":
                    break
                await asyncio.sleep(0.5)
            except Exception:
                break

    async def _update_page_info(self) -> None:
        """Update current page information."""
        try:
            # Get URL and title
            result = await self._send_command("Runtime.evaluate", {
                "expression": "({url: window.location.href, title: document.title})"
            })
            page_info = result.get("result", {}).get("value", {})

            self.state.current_url = page_info.get("url", "")
            self.state.page_title = page_info.get("title", "")
        except Exception as e:
            logger.error(f"Failed to update page info: {e}")

    async def _click_element(self, selector: str) -> Dict[str, Any]:
        """Click element matching CSS selector."""
        try:
            result = await self._send_command("Runtime.evaluate", {
                "expression": f"""
                    (function() {{
                        const element = document.querySelector('{selector}');
                        if (!element) {{
                            return {{success: false, message: 'Seçici ile eşleşen öğe bulunamadı: {selector}'}};
                        }}
                        element.click();
                        return {{success: true, message: 'Öğe başarıyla tıklandı'}};
                    }})()
                """
            })

            return result.get("result", {}).get("value", {"success": False, "message": "Bilinmeyen hata"})
        except Exception as e:
            return {"success": False, "message": f"Tıklama başarısız: {str(e)}"}

    async def _type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """Type text into element matching CSS selector."""
        try:
            result = await self._send_command("Runtime.evaluate", {
                "expression": f"""
                    (function() {{
                        const element = document.querySelector('{selector}');
                        if (!element) {{
                            return {{success: false, message: 'Seçici ile eşleşen öğe bulunamadı: {selector}'}};
                        }}
                        element.focus();
                        element.value = '{text}';
                        element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return {{success: true, message: 'Metin başarıyla yazıldı'}};
                    }})()
                """
            })

            return result.get("result", {}).get("value", {"success": False, "message": "Bilinmeyen hata"})
        except Exception as e:
            return {"success": False, "message": f"Yazma başarısız: {str(e)}"}

    async def _scroll_page(self, direction: str = "down") -> Dict[str, Any]:
        """Scroll page in specified direction."""
        try:
            scroll_amount = "window.innerHeight" if direction in ["down", "up"] else "window.innerWidth"
            scroll_direction = "1" if direction in ["down", "right"] else "-1"

            result = await self._send_command("Runtime.evaluate", {
                "expression": f"""
                    window.scrollBy(0, {scroll_direction} * {scroll_amount});
                    {{success: true, message: 'Sayfa başarıyla kaydırıldı'}};
                """
            })

            return {"success": True, "message": f"Sayfa {direction} yönünde kaydırıldı"}
        except Exception as e:
            return {"success": False, "message": f"Kaydırma başarısız: {str(e)}"}

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.websocket:
                await self.websocket.close()
            self.state.is_connected = False
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")


# Global MCP server instance
chrome_mcp_server = ChromeDevToolsMCP()