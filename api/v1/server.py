"""
server.py

Server Management Endpoints
- Start/Stop llama.cpp und MCP Server
- Modell-Wechsel
- Status Abfrage
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

# Global server manager instance (wird in main.py initialisiert)
server_manager = None


class ServerStartRequest(BaseModel):
    model_name: Optional[str] = None


class ServerSwitchRequest(BaseModel):
    model_name: str


class ServerStatusResponse(BaseModel):
    llama_running: bool
    mcp_running: bool
    current_model: Optional[str]


@router.post("/start")
async def start_servers(request: ServerStartRequest):
    """Startet llama.cpp und MCP Server"""
    if server_manager is None:
        raise HTTPException(status_code=500, detail="Server manager not initialized")

    try:
        success = server_manager.start_all_servers(request.model_name)
        if success:
            return {"message": "Servers started successfully", "model": server_manager.current_model}
        else:
            raise HTTPException(status_code=500, detail="Failed to start servers")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_servers():
    """Stoppt llama.cpp und MCP Server"""
    if server_manager is None:
        raise HTTPException(status_code=500, detail="Server manager not initialized")

    try:
        server_manager.stop_all_servers()
        return {"message": "Servers stopped successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/switch-model")
async def switch_model(request: ServerSwitchRequest):
    """Wechselt Modell durch Server-Neustart"""
    if server_manager is None:
        raise HTTPException(status_code=500, detail="Server manager not initialized")

    try:
        success = server_manager.switch_model(request.model_name)
        if success:
            return {"message": f"Switched to model: {request.model_name}", "model": request.model_name}
        else:
            raise HTTPException(status_code=500, detail="Failed to switch model")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=ServerStatusResponse)
async def get_server_status():
    """Gibt aktuellen Server-Status zurück"""
    if server_manager is None:
        raise HTTPException(status_code=500, detail="Server manager not initialized")

    try:
        status = server_manager.get_status()
        return ServerStatusResponse(**status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
