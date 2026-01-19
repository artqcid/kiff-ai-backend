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
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.api.v1 import chat, config, health, documents


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app"""
    # Startup
    print("🚀 Starting KIFF API Server...")
    yield
    # Shutdown
    print("🛑 Shutting down KIFF API Server...")


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
app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])


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
