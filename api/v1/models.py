"""
models.py

Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatMessage(BaseModel):
    """Single chat message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(None, description="ISO timestamp")


class ChatRequest(BaseModel):
    """Request for chat completion"""
    message: Optional[str] = Field(None, description="User message (deprecated, use messages)")
    messages: Optional[List[ChatMessage]] = Field(None, description="Chat messages array")
    session_id: Optional[str] = Field(None, description="Chat session ID")
    profile: Optional[str] = Field(None, description="Agent profile to use")
    model: Optional[str] = Field(None, description="Model override")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature override")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens override")


class ChatResponse(BaseModel):
    """Response from chat completion"""
    response: str = Field(..., description="Assistant response")
    message: Optional[str] = Field(None, description="Deprecated, use response")
    session_id: str = Field(..., description="Chat session ID")
    model: str = Field(..., description="Model used")
    profile: str = Field(..., description="Profile used")
    timestamp: str = Field(..., description="Response timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ChatSession(BaseModel):
    """Chat session information"""
    session_id: str = Field(..., description="Session ID")
    messages: List[ChatMessage] = Field(default_factory=list, description="Message history")
    created_at: str = Field(..., description="Session creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class ChatSessionList(BaseModel):
    """List of chat sessions"""
    sessions: List[ChatSession] = Field(default_factory=list, description="Available sessions")
    total: int = Field(..., description="Total number of sessions")


# ============================================================================
# CONFIG MODELS
# ============================================================================

class ModelInfo(BaseModel):
    """Model information"""
    name: str = Field(..., description="Model name")
    display_name: str = Field(..., description="Display name")
    path: str = Field(..., description="Model file path")
    context_length: int = Field(..., description="Context length")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Model parameters")


class ProfileInfo(BaseModel):
    """Agent profile information"""
    name: str = Field(..., description="Profile name")
    display_name: str = Field(..., description="Display name")
    description: Optional[str] = Field(None, description="Profile description")
    system_prompt: Optional[str] = Field(None, description="System prompt")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Profile parameters")


class ServerConfig(BaseModel):
    """Server configuration"""
    llama_server_url: str = Field(..., description="Llama server URL")
    mcp_server_url: Optional[str] = Field(None, description="MCP server URL")
    timeout: int = Field(..., description="Request timeout in seconds")


class CurrentConfig(BaseModel):
    """Current active configuration"""
    model: str = Field(..., description="Current model")
    profile: str = Field(..., description="Current profile")
    server: ServerConfig = Field(..., description="Server configuration")


# ============================================================================
# HEALTH MODELS
# ============================================================================

class ServiceStatus(BaseModel):
    """Status of a service"""
    name: str = Field(..., description="Service name")
    status: str = Field(..., description="Status: 'healthy', 'unhealthy', 'unknown'")
    message: Optional[str] = Field(None, description="Status message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Overall status: 'healthy' or 'unhealthy'")
    timestamp: str = Field(..., description="Check timestamp")
    services: List[ServiceStatus] = Field(default_factory=list, description="Service statuses")


class StatusResponse(BaseModel):
    """Detailed status response"""
    api_version: str = Field(..., description="API version")
    backend_running: bool = Field(..., description="Backend running status")
    llm_server_running: bool = Field(..., description="LLM server running status")
    mcp_server_running: bool = Field(..., description="MCP server running status")
    services: List[ServiceStatus] = Field(default_factory=list, description="Service details")


# ============================================================================
# DOCUMENT MODELS
# ============================================================================

class DocumentInfo(BaseModel):
    """Document information"""
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    path: str = Field(..., description="Storage path")
    size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    uploaded_at: str = Field(..., description="Upload timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DocumentList(BaseModel):
    """List of documents"""
    documents: List[DocumentInfo] = Field(default_factory=list, description="Documents")
    total: int = Field(..., description="Total number of documents")


class DocumentUploadResponse(BaseModel):
    """Response after document upload"""
    id: str = Field(..., description="Document ID")
    filename: str = Field(..., description="Filename")
    message: str = Field(..., description="Success message")


class DocumentSessionResponse(BaseModel):
    """Response after creating or updating a document session"""
    session_id: str = Field(..., description="Document session ID")
    filename: str = Field(..., description="Original filename")
    message: str = Field(..., description="Status message")


class DocumentSessionMessage(BaseModel):
    """Simple message response for session operations"""
    session_id: str = Field(..., description="Document session ID")
    message: str = Field(..., description="Status message")


class DocumentVersionInfo(BaseModel):
    """A saved version of a session state"""
    version_id: str = Field(..., description="Version identifier (timestamp based)")
    filename: str = Field(..., description="Stored filename")
    size: int = Field(..., description="File size in bytes")
    created_at: str = Field(..., description="ISO timestamp")


class DocumentSessionHistoryResponse(BaseModel):
    """History of saved versions for a session"""
    session_id: str = Field(..., description="Document session ID")
    versions: list[DocumentVersionInfo] = Field(default_factory=list)


class GoogleImportRequest(BaseModel):
    """Request to import a Google Doc as DOCX"""
    doc_id: str = Field(..., description="Google Docs file ID")


class GoogleExportRequest(BaseModel):
    """Request to export a session DOCX to Google Drive"""
    access_token: str = Field(..., description="OAuth2 access token with Drive scope")
    folder_id: str | None = Field(default=None, description="Optional Drive folder to upload into")
    name: str | None = Field(default=None, description="Optional filename in Drive (defaults to edited-<original>)")


class GoogleExportResponse(BaseModel):
    """Response after exporting to Google Drive"""
    session_id: str = Field(..., description="Document session ID")
    file_id: str = Field(..., description="Created file ID in Drive")
    name: str = Field(..., description="Uploaded filename")
    message: str = Field(..., description="Status message")


# ============================================================================
# ERROR MODELS
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[str] = Field(None, description="Error details")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")
