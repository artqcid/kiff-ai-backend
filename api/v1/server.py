"""
server.py

Server Management Endpoints (Simplified for native Ollama)
- Ollama läuft nativ; keine Start/Stop-Steuerung mehr nötig
- Status-Check prüft Ollama-Erreichbarkeit
"""

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class ServerStartRequest(BaseModel):
    model_name: Optional[str] = None


class ServerSwitchRequest(BaseModel):
    model_name: str


class ServerStatusResponse(BaseModel):
    llama_running: bool
    mcp_running: bool
    current_model: Optional[str]


def _check_ollama_health() -> bool:
    """Check if Ollama is reachable"""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
    except:
        return False


@router.post("/start")
async def start_servers(request: ServerStartRequest):
    """Stub: Ollama läuft nativ (kein Start nötig)"""
    if _check_ollama_health():
        return {"message": "Ollama is already running", "model": request.model_name or "mistral-7b"}
    else:
        raise HTTPException(status_code=503, detail="Ollama not reachable. Start 'ollama serve' manually or via task.")


@router.post("/stop")
async def stop_servers():
    """Stub: Ollama läuft nativ (kein Stop über API)"""
    return {"message": "Ollama runs natively; use 'Stop: All Services' task or kill process manually."}


@router.post("/switch-model")
async def switch_model(request: ServerSwitchRequest):
    """Model switching happens per request via profile selection"""
    if _check_ollama_health():
        return {"message": f"Model switching happens via profile selection. Choose profile to use {request.model_name}.", "model": request.model_name}
    else:
        raise HTTPException(status_code=503, detail="Ollama not reachable")


@router.get("/status", response_model=ServerStatusResponse)
async def get_server_status():
    """Gibt aktuellen Server-Status zurück"""
    llama_running = _check_ollama_health()
    return ServerStatusResponse(
        llama_running=llama_running,
        mcp_running=False,  # MCP optional, nicht implementiert
        current_model="mistral-7b" if llama_running else None
    )
