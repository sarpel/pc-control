from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
import logging

from src.services.browser_control import BrowserControlService
from src.api.dependencies import verify_auth

router = APIRouter(prefix="/api/v1/browser", tags=["browser"], dependencies=[Depends(verify_auth)])
logger = logging.getLogger(__name__)

# Service instance
browser_service = BrowserControlService()

class NavigateRequest(BaseModel):
    url: str
    wait_until: str = "load"

class SearchRequest(BaseModel):
    query: str
    search_engine: str = "google"

class ExtractRequest(BaseModel):
    url: Optional[str] = None
    extract_type: str = "text"

@router.post("/navigate")
async def navigate(request: NavigateRequest):
    try:
        if not request.url:
             raise HTTPException(status_code=400, detail="URL is required")
        
        # Basic validation
        if not str(request.url).startswith(("http://", "https://")):
             raise HTTPException(status_code=400, detail="Invalid URL format")

        result = await browser_service.navigate_to_url(request.url)
        if not result.success:
             raise HTTPException(status_code=500, detail=result.error_message or "Navigation failed")
        
        return {
            "status": "success",
            "navigation_id": "nav_123", # Placeholder
            "url": request.url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Navigation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def search(request: SearchRequest):
    if not request.query:
        raise HTTPException(status_code=400, detail="Query is required")
        
    try:
        result = await browser_service.search_web(request.query, request.search_engine)
        if not result.success:
             raise HTTPException(status_code=500, detail=result.error_message or "Search failed")

        return {
            "status": "success",
            "search_url": f"https://www.google.com/search?q={request.query}", # Placeholder
            "results": result.result_data.get("results", []) if result.result_data else []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract")
async def extract_content(request: ExtractRequest):
    try:
        # Simulate timeout for test
        # await asyncio.sleep(0.1) 
        result = await browser_service.extract_page_content(request.extract_type)
        if not result.success:
             raise HTTPException(status_code=500, detail=result.error_message or "Extraction failed")

        return {
            "status": "success",
            "content": result.result_data.get("content", {}),
            "metadata": {}
        }
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
