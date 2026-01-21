"""
mcp.py

MCP (Model Context Protocol) Admin Endpoints
Verwaltet Web-Context Cache und Context-Sets
"""

import logging
from fastapi import APIRouter, HTTPException
from pathlib import Path
from typing import Dict

from backend.mcp import clear_cache, get_cache_stats, ContextManager
from backend.mcp.web_context_service import url_to_cache_file

logger = logging.getLogger(__name__)

router = APIRouter()

# Context Manager Instanz
_context_manager = None


def get_context_manager() -> ContextManager:
    """Get or create ContextManager singleton"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager()
    return _context_manager


@router.get("/cache/stats")
async def get_cache_statistics():
    """
    Gibt Cache-Statistiken zurück
    
    Returns:
        Dict mit file_count, total_size_bytes, oldest_file_age_hours, newest_file_age_hours
    """
    try:
        stats = await get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")


@router.delete("/cache")
async def clear_all_cache():
    """
    Löscht gesamten Cache (alle gecachten Web-Inhalte)
    
    Returns:
        Anzahl gelöschter Dateien
    """
    try:
        count = await clear_cache()
        logger.info(f"Cleared {count} cache files")
        return {
            "status": "success",
            "message": f"Cleared {count} cache files",
            "deleted_count": count
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@router.delete("/cache/{context_set}")
async def clear_context_set_cache(context_set: str):
    """
    Löscht Cache-Dateien für ein spezifisches Context-Set
    
    Args:
        context_set: Name des Context-Sets (z.B. "gastronomie", "bar")
    
    Returns:
        Anzahl gelöschter Dateien
    """
    try:
        cm = get_context_manager()
        
        # Check if context set exists
        if context_set not in cm.get_available_sets():
            raise HTTPException(
                status_code=404,
                detail=f"Context set '{context_set}' not found. Available sets: {cm.get_available_sets()}"
            )
        
        # Get all URLs for this set
        urls = cm.get_set_urls(context_set)
        
        # Delete cache files for these URLs
        deleted_count = 0
        for url in urls:
            cache_file = url_to_cache_file(url)
            if cache_file.exists():
                cache_file.unlink()
                deleted_count += 1
                logger.debug(f"Deleted cache file for {url}")
        
        logger.info(f"Cleared {deleted_count} cache files for context set '{context_set}'")
        
        return {
            "status": "success",
            "message": f"Cleared cache for context set '{context_set}'",
            "deleted_count": deleted_count,
            "url_count": len(urls)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error clearing context set cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")


@router.get("/context-sets")
async def list_context_sets():
    """
    Listet alle verfügbaren Context-Sets auf
    
    Returns:
        Liste von Context-Set Namen und deren URL-Anzahl
    """
    try:
        cm = get_context_manager()
        sets = cm.get_available_sets()
        
        set_info = []
        for set_name in sets:
            urls = cm.get_set_urls(set_name)
            set_info.append({
                "name": set_name,
                "url_count": len(urls),
                "urls": urls
            })
        
        return {
            "status": "success",
            "context_sets": set_info,
            "total": len(sets)
        }
    except Exception as e:
        logger.error(f"Error listing context sets: {e}")
        raise HTTPException(status_code=500, detail=f"Error listing context sets: {str(e)}")


@router.post("/context-sets/reload")
async def reload_context_sets():
    """
    Lädt Context-Sets neu aus JSON-Konfiguration
    
    Nützlich nach manuellen Änderungen an context_sets_kiff.json
    """
    try:
        cm = get_context_manager()
        cm.reload_context_sets()
        
        sets = cm.get_available_sets()
        
        logger.info(f"Reloaded {len(sets)} context sets")
        
        return {
            "status": "success",
            "message": "Context sets reloaded",
            "context_sets": sets,
            "total": len(sets)
        }
    except Exception as e:
        logger.error(f"Error reloading context sets: {e}")
        raise HTTPException(status_code=500, detail=f"Error reloading context sets: {str(e)}")


@router.get("/health")
async def mcp_health():
    """
    Health check für MCP Service
    """
    try:
        cm = get_context_manager()
        sets = cm.get_available_sets()
        stats = await get_cache_stats()
        
        return {
            "status": "healthy",
            "context_sets_loaded": len(sets),
            "cache_files": stats["file_count"],
            "cache_size_mb": round(stats["total_size_bytes"] / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"MCP health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
