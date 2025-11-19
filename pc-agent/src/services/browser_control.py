"""
Browser control service for PC Voice Controller.

This module provides comprehensive browser automation capabilities including
web page navigation, element interaction, information extraction, and
content search using Selenium WebDriver.
"""

import logging
import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from urllib.parse import urlparse, urljoin
from enum import Enum
import time

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.common.exceptions import (
        WebDriverException, TimeoutException, NoSuchElementException,
        StaleElementReferenceException, ElementNotInteractableException
    )
    from selenium.webdriver.support.ui import Select
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium not available. Browser control features will be limited.")

from config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class BrowserType(Enum):
    """Supported browser types."""
    CHROME = "chrome"
    FIREFOX = "firefox"
    EDGE = "edge"


class ElementSelectorType(Enum):
    """Types of element selectors."""
    CSS_SELECTOR = "css"
    XPATH = "xpath"
    ID = "id"
    CLASS_NAME = "class"
    TAG_NAME = "tag"
    NAME = "name"
    LINK_TEXT = "link_text"
    PARTIAL_LINK_TEXT = "partial_link_text"


@dataclass
class BrowserAction:
    """Represents a browser action to be executed."""
    action_type: str
    target: Optional[str] = None
    selector_type: Optional[ElementSelectorType] = None
    value: Optional[str] = None
    coordinates: Optional[tuple] = None
    wait_for_element: bool = True
    timeout_seconds: int = 10
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


@dataclass
class BrowserActionResult:
    """Result of a browser action execution."""
    success: bool
    action_type: str
    execution_time_ms: int
    result_data: Any = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    page_info: Optional[Dict[str, Any]] = None


class BrowserControlService:
    """Service for controlling web browsers through voice commands."""

    def __init__(self):
        self.driver: Optional[webdriver.Remote] = None
        self.browser_type = BrowserType.CHROME
        self.is_initialized = False
        self.current_url: Optional[str] = None
        self.page_title: Optional[str] = None

    async def initialize(self, browser_type: BrowserType = BrowserType.CHROME) -> bool:
        """
        Initialize the browser WebDriver.

        Args:
            browser_type: Type of browser to control

        Returns:
            True if initialization successful, False otherwise
        """
        if not SELENIUM_AVAILABLE:
            logger.error("Selenium WebDriver not available")
            return False

        try:
            if self.is_initialized and self.driver:
                await self.close_browser()

            self.browser_type = browser_type

            # Setup browser options
            if browser_type == BrowserType.CHROME:
                options = ChromeOptions()
                options.add_argument("--headless")  # Run in headless mode
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

                if settings.debug_mode:
                    options.add_argument("--remote-debugging-port=9222")

                self.driver = webdriver.Chrome(options=options)

            elif browser_type == BrowserType.FIREFOX:
                options = FirefoxOptions()
                options.add_argument("--headless")
                options.add_argument("--width=1920")
                options.add_argument("--height=1080")

                self.driver = webdriver.Firefox(options=options)

            else:
                logger.error(f"Unsupported browser type: {browser_type}")
                return False

            # Set implicit wait
            self.driver.implicitly_wait(5)

            # Set page load timeout
            self.driver.set_page_load_timeout(30)

            self.is_initialized = True
            logger.info(f"Browser initialized successfully: {browser_type.value}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return False

    async def navigate_to_url(self, url: str, wait_for_load: bool = True) -> BrowserActionResult:
        """
        Navigate to a specific URL.

        Args:
            url: URL to navigate to
            wait_for_load: Whether to wait for page to fully load

        Returns:
            BrowserActionResult with execution details
        """
        start_time = time.time()

        try:
            if not self.is_initialized or not self.driver:
                return BrowserActionResult(
                    success=False,
                    action_type="navigate",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Browser not initialized"
                )

            # Validate and format URL
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            logger.info(f"Navigating to: {url}")

            if wait_for_load:
                self.driver.get(url)
                # Wait for page to load
                WebDriverWait(self.driver, 30).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            else:
                self.driver.get(url)

            # Update current page info
            self.current_url = self.driver.current_url
            self.page_title = self.driver.title

            execution_time = int((time.time() - start_time) * 1000)

            return BrowserActionResult(
                success=True,
                action_type="navigate",
                execution_time_ms=execution_time,
                result_data={
                    "url": self.current_url,
                    "title": self.page_title
                },
                page_info=await self.get_page_info()
            )

        except TimeoutException:
            return BrowserActionResult(
                success=False,
                action_type="navigate",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message="Page load timeout"
            )
        except WebDriverException as e:
            return BrowserActionResult(
                success=False,
                action_type="navigate",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Navigation error: {str(e)}"
            )

    async def search_web(self, query: str, search_engine: str = "google") -> BrowserActionResult:
        """
        Perform web search using specified search engine.

        Args:
            query: Search query
            search_engine: Search engine to use (google, bing, duckduckgo)

        Returns:
            BrowserActionResult with search results
        """
        start_time = time.time()

        try:
            if not self.is_initialized or not self.driver:
                return BrowserActionResult(
                    success=False,
                    action_type="search",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Browser not initialized"
                )

            # Construct search URL
            search_urls = {
                "google": f"https://www.google.com/search?q={query}",
                "bing": f"https://www.bing.com/search?q={query}",
                "duckduckgo": f"https://www.duckduckgo.com/?q={query}"
            }

            if search_engine not in search_urls:
                return BrowserActionResult(
                    success=False,
                    action_type="search",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Unsupported search engine: {search_engine}"
                )

            search_url = search_urls[search_engine]

            # Navigate to search results
            result = await self.navigate_to_url(search_url)
            if not result.success:
                return result

            # Wait for search results to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-ved], .b_result, .result"))
                )
            except TimeoutException:
                logger.warning("Search results didn't load in time")

            execution_time = int((time.time() - start_time) * 1000)

            # Extract search results
            search_results = await self.extract_search_results()

            return BrowserActionResult(
                success=True,
                action_type="search",
                execution_time_ms=execution_time,
                result_data={
                    "query": query,
                    "search_engine": search_engine,
                    "results_count": len(search_results),
                    "results": search_results[:10]  # Limit to first 10 results
                }
            )

        except Exception as e:
            return BrowserActionResult(
                success=False,
                action_type="search",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Search error: {str(e)}"
            )

    async def extract_page_content(self, extraction_type: str = "text") -> BrowserActionResult:
        """
        Extract content from the current page.

        Args:
            extraction_type: Type of extraction (text, links, images, forms, tables)

        Returns:
            BrowserActionResult with extracted content
        """
        start_time = time.time()

        try:
            if not self.is_initialized or not self.driver:
                return BrowserActionResult(
                    success=False,
                    action_type="extract",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Browser not initialized"
                )

            content = {}

            if extraction_type in ("text", "all"):
                content["text"] = await self.extract_text_content()

            if extraction_type in ("links", "all"):
                content["links"] = await self.extract_links()

            if extraction_type in ("images", "all"):
                content["images"] = await self.extract_images()

            if extraction_type in ("forms", "all"):
                content["forms"] = await self.extract_forms()

            if extraction_type in ("tables", "all"):
                content["tables"] = await self.extract_tables()

            execution_time = int((time.time() - start_time) * 1000)

            return BrowserActionResult(
                success=True,
                action_type="extract",
                execution_time_ms=execution_time,
                result_data={
                    "extraction_type": extraction_type,
                    "content": content
                }
            )

        except Exception as e:
            return BrowserActionResult(
                success=False,
                action_type="extract",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Extraction error: {str(e)}"
            )

    async def interact_with_element(self, action: BrowserAction) -> BrowserActionResult:
        """
        Interact with a web page element.

        Args:
            action: BrowserAction describing the interaction

        Returns:
            BrowserActionResult with interaction details
        """
        start_time = time.time()

        try:
            if not self.is_initialized or not self.driver:
                return BrowserActionResult(
                    success=False,
                    action_type=action.action_type,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Browser not initialized"
                )

            element = await self.find_element(action)
            if not element:
                return BrowserActionResult(
                    success=False,
                    action_type=action.action_type,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Element not found: {action.target}"
                )

            # Perform the interaction
            if action.action_type == "click":
                element.click()
            elif action.action_type == "double_click":
                ActionChains(self.driver).double_click(element).perform()
            elif action.action_type == "right_click":
                ActionChains(self.driver).context_click(element).perform()
            elif action.action_type == "type":
                element.clear()
                element.send_keys(action.value or "")
            elif action.action_type == "submit":
                element.submit()
            elif action.action_type == "scroll_to":
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
            elif action.action_type == "hover":
                ActionChains(self.driver).move_to_element(element).perform()
            elif action.action_type == "select":
                select = Select(element)
                if action.value:
                    select.select_by_visible_text(action.value)
            else:
                return BrowserActionResult(
                    success=False,
                    action_type=action.action_type,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message=f"Unsupported action type: {action.action_type}"
                )

            execution_time = int((time.time() - start_time) * 1000)

            return BrowserActionResult(
                success=True,
                action_type=action.action_type,
                execution_time_ms=execution_time,
                result_data={
                    "element": action.target,
                    "selector_type": action.selector_type.value if action.selector_type else None
                }
            )

        except ElementNotInteractableException as e:
            return BrowserActionResult(
                success=False,
                action_type=action.action_type,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Element not interactable: {str(e)}"
            )
        except Exception as e:
            return BrowserActionResult(
                success=False,
                action_type=action.action_type,
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Interaction error: {str(e)}"
            )

    async def take_screenshot(self, filename: Optional[str] = None) -> BrowserActionResult:
        """
        Take a screenshot of the current page.

        Args:
            filename: Optional filename for the screenshot

        Returns:
            BrowserActionResult with screenshot path
        """
        start_time = time.time()

        try:
            if not self.is_initialized or not self.driver:
                return BrowserActionResult(
                    success=False,
                    action_type="screenshot",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    error_message="Browser not initialized"
                )

            if not filename:
                timestamp = int(time.time())
                filename = f"screenshot_{timestamp}.png"

            screenshot_path = f"screenshots/{filename}"

            # Create screenshots directory if it doesn't exist
            import os
            os.makedirs("screenshots", exist_ok=True)

            self.driver.save_screenshot(screenshot_path)

            execution_time = int((time.time() - start_time) * 1000)

            return BrowserActionResult(
                success=True,
                action_type="screenshot",
                execution_time_ms=execution_time,
                screenshot_path=screenshot_path,
                result_data={"filename": filename, "path": screenshot_path}
            )

        except Exception as e:
            return BrowserActionResult(
                success=False,
                action_type="screenshot",
                execution_time_ms=int((time.time() - start_time) * 1000),
                error_message=f"Screenshot error: {str(e)}"
            )

    async def get_page_info(self) -> Dict[str, Any]:
        """Get information about the current page."""
        if not self.is_initialized or not self.driver:
            return {}

        try:
            return {
                "url": self.driver.current_url,
                "title": self.driver.title,
                "window_size": self.driver.get_window_size(),
                "current_url": self.current_url,
                "page_title": self.page_title
            }
        except Exception as e:
            logger.error(f"Error getting page info: {e}")
            return {}

    async def find_element(self, action: BrowserAction):
        """Find a web page element based on the action specifications."""
        if not action.target or not action.selector_type:
            return None

        try:
            if action.wait_for_element:
                wait = WebDriverWait(self.driver, action.timeout_seconds)

                by_mapping = {
                    ElementSelectorType.CSS_SELECTOR: By.CSS_SELECTOR,
                    ElementSelectorType.XPATH: By.XPATH,
                    ElementSelectorType.ID: By.ID,
                    ElementSelectorType.CLASS_NAME: By.CLASS_NAME,
                    ElementSelectorType.TAG_NAME: By.TAG_NAME,
                    ElementSelectorType.NAME: By.NAME,
                    ElementSelectorType.LINK_TEXT: By.LINK_TEXT,
                    ElementSelectorType.PARTIAL_LINK_TEXT: By.PARTIAL_LINK_TEXT
                }

                by_type = by_mapping.get(action.selector_type, By.CSS_SELECTOR)
                return wait.until(EC.presence_of_element_located((by_type, action.target)))
            else:
                by_mapping = {
                    ElementSelectorType.CSS_SELECTOR: By.CSS_SELECTOR,
                    ElementSelectorType.XPATH: By.XPATH,
                    ElementSelectorType.ID: By.ID,
                    ElementSelectorType.CLASS_NAME: By.CLASS_NAME,
                    ElementSelectorType.TAG_NAME: By.TAG_NAME,
                    ElementSelectorType.NAME: By.NAME,
                    ElementSelectorType.LINK_TEXT: By.LINK_TEXT,
                    ElementSelectorType.PARTIAL_LINK_TEXT: By.PARTIAL_LINK_TEXT
                }

                by_type = by_mapping.get(action.selector_type, By.CSS_SELECTOR)
                return self.driver.find_element(by_type, action.target)

        except (TimeoutException, NoSuchElementException):
            return None

    async def extract_text_content(self) -> str:
        """Extract visible text content from the page."""
        try:
            # Get body text
            body = self.driver.find_element(By.TAG_NAME, "body")
            text = body.text

            # Clean up text
            text = re.sub(r'\s+', ' ', text).strip()
            return text
        except Exception:
            return ""

    async def extract_links(self) -> List[Dict[str, str]]:
        """Extract all links from the page."""
        links = []
        try:
            elements = self.driver.find_elements(By.TAG_NAME, "a")
            for element in elements:
                try:
                    href = element.get_attribute("href")
                    text = element.text.strip()
                    if href:
                        links.append({"href": href, "text": text})
                except Exception:
                    continue
        except Exception:
            pass
        return links

    async def extract_images(self) -> List[Dict[str, str]]:
        """Extract all images from the page."""
        images = []
        try:
            elements = self.driver.find_elements(By.TAG_NAME, "img")
            for element in elements:
                try:
                    src = element.get_attribute("src")
                    alt = element.get_attribute("alt") or ""
                    if src:
                        images.append({"src": src, "alt": alt})
                except Exception:
                    continue
        except Exception:
            pass
        return images

    async def extract_forms(self) -> List[Dict[str, Any]]:
        """Extract all forms from the page."""
        forms = []
        try:
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            for form in form_elements:
                try:
                    form_data = {
                        "action": form.get_attribute("action") or "",
                        "method": form.get_attribute("method") or "GET",
                        "inputs": []
                    }

                    inputs = form.find_elements(By.TAG_NAME, "input")
                    for input_elem in inputs:
                        input_data = {
                            "name": input_elem.get_attribute("name") or "",
                            "type": input_elem.get_attribute("type") or "text",
                            "placeholder": input_elem.get_attribute("placeholder") or ""
                        }
                        form_data["inputs"].append(input_data)

                    forms.append(form_data)
                except Exception:
                    continue
        except Exception:
            pass
        return forms

    async def extract_tables(self) -> List[Dict[str, Any]]:
        """Extract all tables from the page."""
        tables = []
        try:
            table_elements = self.driver.find_elements(By.TAG_NAME, "table")
            for table in table_elements:
                try:
                    table_data = {"headers": [], "rows": []}

                    # Extract headers
                    headers = table.find_elements(By.TAG_NAME, "th")
                    for header in headers:
                        table_data["headers"].append(header.text.strip())

                    # Extract rows
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        row_data = [cell.text.strip() for cell in cells]
                        if row_data:
                            table_data["rows"].append(row_data)

                    tables.append(table_data)
                except Exception:
                    continue
        except Exception:
            pass
        return tables

    async def extract_search_results(self) -> List[Dict[str, str]]:
        """Extract search results from the current page."""
        results = []
        try:
            # Try different selectors for search results
            selectors = [
                "[data-ved]",  # Google
                ".b_result",    # Bing
                ".result",      # DuckDuckGo
                ".g",           # Google results
                ".search-result"  # Generic
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        try:
                            # Try to find title and link
                            title_elem = element.find_element(By.TAG_NAME, "a") or element.find_element(By.TAG_NAME, "h3")
                            title = title_elem.text.strip()
                            link = title_elem.get_attribute("href")

                            if title and link:
                                results.append({"title": title, "url": link})
                        except Exception:
                            continue

                    if results:
                        break
                except Exception:
                    continue

        except Exception:
            pass

        return results

    async def close_browser(self) -> bool:
        """Close the browser and clean up resources."""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None

            self.is_initialized = False
            self.current_url = None
            self.page_title = None

            logger.info("Browser closed successfully")
            return True

        except Exception as e:
            logger.error(f"Error closing browser: {e}")
            return False

    async def cleanup(self) -> None:
        """Cleanup browser control service."""
        await self.close_browser()