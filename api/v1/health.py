"""
health.py

Health check and status endpoints
"""

from fastapi import APIRouter
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import HealthResponse, StatusResponse, ServiceStatus
from src.server_manager_kiff import ServerManager

router = APIRouter()

# Global server manager instance
_server_manager = None


def get_server_manager():
    """Get or create server manager instance"""
    global _server_manager
    if _server_manager is None:
        _server_manager = ServerManager()
    return _server_manager


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint
    Returns overall API health status
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        services=[
            ServiceStatus(
                name="api",
                status="healthy",
                message="API is running"
            )
        ]
    )


@router.get("/status", response_model=StatusResponse)
async def detailed_status():
    """
    Detailed status endpoint
    Returns status of all services (API, LLM, MCP)
    """
    server_manager = get_server_manager()
    
    # Check LLM server status
    llm_healthy = server_manager.is_healthy()
    
    services = [
        ServiceStatus(
            name="api",
            status="healthy",
            message="API server is running",
            details={"version": "1.0.0"}
        ),
        ServiceStatus(
            name="llm_server",
            status="healthy" if llm_healthy else "unhealthy",
            message="LLM server is running" if llm_healthy else "LLM server is not responding",
            details={"url": "http://localhost:8080"}
        ),
        ServiceStatus(
            name="mcp_server",
            status="unknown",
            message="MCP server status check not implemented yet",
            details={"url": "http://localhost:3000"}
        )
    ]
    
    return StatusResponse(
        api_version="1.0.0",
        backend_running=True,
        llm_server_running=llm_healthy,
        mcp_server_running=False,  # TODO: implement actual check
        services=services
    )
