"""
main.py

FastAPI Application for KIFF LangChain Agent
Provides REST API with OpenAPI/Swagger documentation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import sys
import subprocess
import platform
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.api.v1 import chat, config, health, documents, server, mcp
from backend.core.server_manager import ServerManager
from backend.core.model_registry import ModelRegistry
from backend.core.llm_client import LLMClient
from backend.core.profile_agent import ProfileAgent

# Global instances
_server_manager = None
_model_registry = None
_llm_client = None
_profile_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app"""
    global _server_manager, _model_registry, _llm_client, _profile_agent
    
    # Startup
    print("🚀 Starting KIFF API Server...")
    
    # Auto-start Ollama if not running
    try:
        print("🔍 Checking Ollama status...")
        _llm_client = LLMClient()
        if not _llm_client.is_healthy():
            print("⚙️ Ollama not running, attempting to start...")
            if platform.system() == "Windows":
                # Windows: Start Ollama app in background
                subprocess.Popen(["ollama", "serve"], 
                               creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                # Linux/Mac: Start Ollama service
                subprocess.Popen(["ollama", "serve"],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            
            # Wait a moment for Ollama to start
            import time
            for i in range(10):
                time.sleep(1)
                if _llm_client.is_healthy():
                    print("✅ Ollama started successfully")
                    break
            else:
                print("⚠️ Ollama did not start within timeout, continuing anyway...")
        else:
            print("✅ Ollama is already running")
    except Exception as e:
        print(f"⚠️ Could not auto-start Ollama: {e}")
        print("   Please start Ollama manually: 'ollama serve'")
    
    # Initialize components
    try:
        _model_registry = ModelRegistry()
        if not _llm_client:
            _llm_client = LLMClient()
        _profile_agent = ProfileAgent(_llm_client)
        _server_manager = ServerManager()
        
        # Inject instances into modules
        import backend.api.v1.server as server_module
        import backend.api.v1.chat as chat_module
        import backend.api.v1.config as config_module
        import backend.api.v1.health as health_module
        
        server_module.server_manager = _server_manager
        chat_module.profile_agent = _profile_agent
        config_module.model_registry = _model_registry
        config_module.profile_agent = _profile_agent
        config_module.server_manager = _server_manager
        health_module.server_manager = _server_manager
        health_module.llm_client = _llm_client
        
        print("✅ All components initialized successfully")
    except Exception as e:
        print(f"⚠️ Warning: Some components failed to initialize: {e}")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down KIFF API Server...")
    if _server_manager:
        _server_manager.stop_all_servers()


# Initialize FastAPI app
app = FastAPI(
    title="KIFF LangChain Agent API",
    description="REST API for KIFF LangChain Agent with LLM, RAG, and MCP capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vue dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(server.router, prefix="/api/v1/server", tags=["Server Management"])
app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(mcp.router, prefix="/api/v1/mcp", tags=["MCP"])


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "KIFF LangChain Agent API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/api/v1/openapi.json",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": str(exc),
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
