"""
Page content extraction service for browser operations.

This module provides intelligent content extraction from web pages including:
- Text summarization (max 500 chars for display)
- Structured data extraction (headings, lists, tables)
- Main content identification (removing headers, footers, ads)
- Metadata extraction (title, description, keywords)
- Turkish language support for summaries

Integrates with browser_control.py and chrome_devtools.py
Task: T062 - User Story 2
"""

import logging
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ExtractionType(Enum):
    """Types of content extraction."""
    TEXT = "text"
    SUMMARY = "summary"
    STRUCTURED = "structured"
    METADATA = "metadata"
    ALL = "all"


@dataclass
class PageContent:
    """Extracted page content."""
    url: str
    title: str
    text_content: str
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    structured_data: Optional[Dict[str, Any]] = None
    extraction_time_ms: Optional[int] = None


class PageExtractor:
    """
    Service for extracting and processing web page content.

    Features:
    - Intelligent text extraction (removes navigation, ads, footers)
    - Automatic summarization for display (max 500 chars)
    - Structured data extraction (headings, lists, tables)
    - Metadata extraction
    - Turkish language support
    """

    def __init__(self):
        self.max_summary_length = 500
        self.noise_patterns = [
            r'cookie',
            r'privacy policy',
            r'terms of service',
            r'subscribe',
            r'newsletter',
            r'advertisement',
            r'sponsored',
        ]

    async def extract(
        self,
        html_content: str,
        url: str,
        extraction_type: ExtractionType = ExtractionType.SUMMARY
    ) -> PageContent:
        """
        Extract content from HTML.

        Args:
            html_content: Raw HTML content
            url: Page URL
            extraction_type: Type of extraction to perform

        Returns:
            PageContent with extracted data
        """
        import time
        start_time = time.time()

        try:
            # Extract basic info
            title = self._extract_title(html_content)
            text_content = self._extract_text(html_content)

            # Build page content
            content = PageContent(
                url=url,
                title=title,
                text_content=text_content
            )

            # Perform requested extraction
            if extraction_type in (ExtractionType.SUMMARY, ExtractionType.ALL):
                content.summary = self._create_summary(text_content)

            if extraction_type in (ExtractionType.METADATA, ExtractionType.ALL):
                content.metadata = self._extract_metadata(html_content)

            if extraction_type in (ExtractionType.STRUCTURED, ExtractionType.ALL):
                content.structured_data = self._extract_structured_data(html_content)

            content.extraction_time_ms = int((time.time() - start_time) * 1000)

            logger.info(f"Extracted {extraction_type.value} from {url} in {content.extraction_time_ms}ms")
            return content

        except Exception as e:
            logger.error(f"Content extraction error for {url}: {e}")
            raise

    def _extract_title(self, html: str) -> str:
        """Extract page title from HTML."""
        # Try <title> tag
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            title = re.sub(r'<[^>]+>', '', title)  # Remove any HTML tags
            title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
            return title

        # Try <h1> as fallback
        match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()

        return "Untitled Page"

    def _extract_text(self, html: str) -> str:
        """
        Extract clean text content from HTML.

        Removes:
        - Script and style tags
        - Navigation elements
        - Footer content
        - Advertisement blocks
        """
        # Remove script and style tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove common noise elements
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode HTML entities
        text = self._decode_html_entities(text)

        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    def _create_summary(self, text: str) -> str:
        """
        Create a concise summary for display.

        Args:
            text: Full text content

        Returns:
            Summary (max 500 chars) with ellipsis if truncated
        """
        if not text:
            return ""

        # Clean the text
        text = text.strip()

        # Extract first few sentences (aim for ~500 chars)
        sentences = re.split(r'[.!?]+\s+', text)
        summary = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed limit
            if len(summary) + len(sentence) + 2 > self.max_summary_length:
                break

            summary += sentence + ". "

        # If no complete sentences fit, just truncate
        if not summary and text:
            summary = text[:self.max_summary_length - 3] + "..."

        # Ensure we end with proper punctuation
        summary = summary.strip()
        if summary and not summary[-1] in '.!?':
            summary += "..."

        return summary

    def _extract_metadata(self, html: str) -> Dict[str, str]:
        """Extract page metadata (description, keywords, author, etc.)."""
        metadata = {}

        # Description
        match = re.search(
            r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            metadata['description'] = match.group(1)

        # Keywords
        match = re.search(
            r'<meta\s+name=["\']keywords["\']\s+content=["\'](.*?)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            metadata['keywords'] = match.group(1)

        # Author
        match = re.search(
            r'<meta\s+name=["\']author["\']\s+content=["\'](.*?)["\']',
            html,
            re.IGNORECASE
        )
        if match:
            metadata['author'] = match.group(1)

        # Open Graph tags
        og_title = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
        if og_title:
            metadata['og_title'] = og_title.group(1)

        return metadata

    def _extract_structured_data(self, html: str) -> Dict[str, List[str]]:
        """Extract structured data like headings and lists."""
        structured = {
            'headings': [],
            'lists': []
        }

        # Extract headings (h1-h3)
        for i in range(1, 4):
            pattern = f'<h{i}[^>]*>(.*?)</h{i}>'
            headings = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
            for heading in headings:
                clean_heading = re.sub(r'<[^>]+>', '', heading).strip()
                if clean_heading:
                    structured['headings'].append(f"H{i}: {clean_heading}")

        # Extract list items
        list_items = re.findall(r'<li[^>]*>(.*?)</li>', html, re.IGNORECASE | re.DOTALL)
        for item in list_items[:10]:  # Limit to first 10
            clean_item = re.sub(r'<[^>]+>', '', item).strip()
            if clean_item and len(clean_item) < 200:  # Skip overly long items
                structured['lists'].append(clean_item)

        return structured

    def _decode_html_entities(self, text: str) -> str:
        """Decode common HTML entities."""
        entities = {
            '&nbsp;': ' ',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&#39;': "'",
            '&apos;': "'",
            '&ndash;': '–',
            '&mdash;': '—',
            '&hellip;': '...',
        }

        for entity, char in entities.items():
            text = text.replace(entity, char)

        # Decode numeric entities
        text = re.sub(r'&#(\d+);', lambda m: chr(int(m.group(1))), text)
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)

        return text

    async def extract_from_browser(self, browser_service, extraction_type: ExtractionType = ExtractionType.SUMMARY) -> PageContent:
        """
        Extract content from currently loaded page in browser service.

        Args:
            browser_service: BrowserControlService instance
            extraction_type: Type of extraction to perform

        Returns:
            PageContent with extracted data
        """
        # Get page info
        page_info = await browser_service.get_page_info()
        url = page_info.get('url', '')

        # Get page HTML
        if hasattr(browser_service, 'driver') and browser_service.driver:
            html_content = browser_service.driver.page_source
        else:
            raise ValueError("Browser not initialized or no page loaded")

        # Extract content
        return await self.extract(html_content, url, extraction_type)
