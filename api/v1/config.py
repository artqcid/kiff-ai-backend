"""
config.py

Configuration and profile management endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import sys
import json
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import ModelInfo, ProfileInfo, CurrentConfig, ServerConfig
from backend.core.model_registry import ModelRegistry

router = APIRouter()


# Provider-related Pydantic models
class ProviderInfo(BaseModel):
    name: str
    display_name: str
    type: str
    enabled: bool
    description: str
    requires_api_key: bool
    has_api_key: bool
    is_current: bool
    features: Dict[str, bool]
    rate_limits: Dict[str, Any]


class ProviderValidateRequest(BaseModel):
    api_key: Optional[str] = None


class ProviderValidateResponse(BaseModel):
    valid: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# Global registry instance
_model_registry = None


def get_model_registry():
    """Get or create model registry instance"""
    global _model_registry
    if _model_registry is None:
        _model_registry = ModelRegistry()
    return _model_registry


@router.get("/config/models", response_model=List[ModelInfo])
async def get_models():
    """
    Get list of available models
    """
    registry = get_model_registry()
    available_models = registry.get_available_models()
    
    models = []
    for model_name in available_models:
        details = registry.get_model_details(model_name)
        model_config = registry.config.get("models", {}).get(model_name, {})
        
        models.append(ModelInfo(
            name=model_name,
            display_name=details,
            path=model_config.get("path", ""),
            context_length=model_config.get("context_length", 2048),
            parameters=model_config.get("parameters", {})
        ))
    
    return models


@router.get("/config/profiles", response_model=List[ProfileInfo])
async def get_profiles():
    """
    Get list of available agent profiles
    """
    config_path = Path("config/profiles_kiff.json")
    
    if not config_path.exists():
        return []
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            profiles_config = json.load(f)
        
        profiles = []
        for profile_name, profile_data in profiles_config.items():
            profiles.append(ProfileInfo(
                name=profile_name,
                display_name=profile_data.get("display_name", profile_name),
                description=profile_data.get("description"),
                system_prompt=profile_data.get("system_prompt"),
                parameters=profile_data.get("parameters", {})
            ))
        
        return profiles
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load profiles: {str(e)}")


@router.get("/config/current", response_model=CurrentConfig)
async def get_current_config():
    """
    Get current active configuration
    """
    registry = get_model_registry()
    current_model = registry.get_default_model()

    # Determine current profile from persisted state if available
    current_profile = "general_chat"
    try:
        backend_dir = Path(__file__).resolve().parent.parent.parent
        profile_file = backend_dir / "documents" / "current_profile.json"
        if profile_file.exists():
            data = json.loads(profile_file.read_text(encoding="utf-8"))
            current_profile = data.get("profile", "general_chat")
    except Exception:
        pass

    # Reflect actual LLM server URL from environment
    llm_server_url = os.getenv("LLM_SERVER_URL", "http://localhost:11434")
    mcp_server_url = os.getenv("MCP_SERVER_URL", "http://localhost:3000")

    return CurrentConfig(
        model=current_model,
        profile=current_profile,
        server=ServerConfig(
            llama_server_url=llm_server_url,
            mcp_server_url=mcp_server_url,
            timeout=60
        )
    )


@router.get("/config/servers")
async def get_server_config():
    """
    Get server configuration
    """
    config_path = Path("config/servers_kiff.json")
    
    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Server config not found")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load server config: {str(e)}")


# Convenience aliases for frontend
@router.get("/models", response_model=List[ModelInfo])
async def get_models_alias():
    """Get list of available models (alias)"""
    return await get_models()


@router.get("/profiles", response_model=List[ProfileInfo])
async def get_profiles_alias():
    """Get list of available agent profiles (alias)"""
    return await get_profiles()


# ========================================
# Provider Management Endpoints
# ========================================

from backend.core.provider_manager import get_provider_manager
from pydantic import BaseModel


class ProviderValidateRequest(BaseModel):
    """Request für Provider-Validierung"""
    api_key: Optional[str] = None


class ProviderValidateResponse(BaseModel):
    """Response für Provider-Validierung"""
    valid: bool
    message: str
    details: Optional[dict] = None


class ProviderInfo(BaseModel):
    """Provider-Informationen"""
    name: str
    display_name: str
    type: str
    enabled: bool
    description: str
    requires_api_key: bool
    has_api_key: bool
    is_current: bool
    features: dict
    rate_limits: dict


class CurrentProviderResponse(BaseModel):
    """Aktueller Provider Status"""
    provider: str
    profile: str
    model: str
    provider_display_name: str


@router.get("/providers", response_model=List[ProviderInfo])
async def get_providers():
    """
    Get list of all available LLM providers
    
    Returns:
        List of providers with status and capabilities
    """
    manager = get_provider_manager()
    providers = manager.get_available_providers()
    
    return [ProviderInfo(**p) for p in providers]


@router.post("/provider/{provider_name}/validate", response_model=ProviderValidateResponse)
async def validate_provider(provider_name: str, request: ProviderValidateRequest = None):
    """
    Validate provider configuration and API access
    
    Args:
        provider_name: Name of provider to validate
        request: Optional request with API key to test
        
    Returns:
        Validation result with status and message
    """
    manager = get_provider_manager()
    
    api_key = request.api_key if request else None
    result = await manager.validate_provider(provider_name, api_key)
    
    return ProviderValidateResponse(
        valid=result.valid,
        message=result.message,
        details=result.details
    )


@router.post("/provider/{provider_name}/set")
async def set_provider(provider_name: str):
    """
    Set current LLM provider
    
    Args:
        provider_name: Name of provider to set as current
        
    Returns:
        Success message
    """
    manager = get_provider_manager()
    
    success = manager.set_current_provider(provider_name)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Provider '{provider_name}' nicht gefunden"
        )
    
    return {"message": f"Provider '{provider_name}' aktiviert", "provider": provider_name}


@router.get("/provider/current", response_model=CurrentProviderResponse)
async def get_current_provider():
    """
    Get current provider, profile and model
    
    Returns:
        Current provider status
    """
    manager = get_provider_manager()
    
    # Get current provider
    current_provider_name = manager.get_current_provider_name()
    current_provider = manager.get_provider(current_provider_name)
    
    # Get current profile from persisted file
    backend_dir = Path(__file__).parent.parent.parent
    profile_file = backend_dir / "documents" / "current_profile.json"
    current_profile = "general_chat"
    
    try:
        if profile_file.exists():
            data = json.loads(profile_file.read_text(encoding="utf-8"))
            current_profile = data.get("profile", "general_chat")
    except Exception:
        pass
    
    # Get default model for current profile and provider
    from backend.core.profile_agent import ProfileAgent
    agent = ProfileAgent(provider_manager=manager)
    default_model = agent.get_default_model_for_profile(current_profile, current_provider_name)
    
    if not default_model:
        # Fallback to first supported model
        supported_models = agent.get_models_for_profile(current_profile, current_provider_name)
        default_model = supported_models[0] if supported_models else "unknown"
    
    return CurrentProviderResponse(
        provider=current_provider_name,
        profile=current_profile,
        model=default_model,
        provider_display_name=current_provider.config.display_name
    )


@router.get("/profile/{profile_name}/models")
async def get_profile_models(profile_name: str, provider: Optional[str] = None):
    """
    Get available models for a profile and provider
    
    Args:
        profile_name: Name of profile
        provider: Optional provider name (uses current if None)
        
    Returns:
        List of model IDs and details
    """
    manager = get_provider_manager()
    
    # Get provider
    provider_name = provider or manager.get_current_provider_name()
    
    # Get profile agent
    from backend.core.profile_agent import ProfileAgent
    agent = ProfileAgent(provider_manager=manager)
    
    # Get supported models for profile+provider
    supported_model_ids = agent.get_models_for_profile(profile_name, provider_name)
    
    if not supported_model_ids:
        return {"profile": profile_name, "provider": provider_name, "models": []}
    
    # Get model details from provider
    provider_inst = manager.get_provider(provider_name)
    all_models = provider_inst.get_models()
    
    # Filter to only supported models
    filtered_models = [m for m in all_models if m.model_id in supported_model_ids]
    
    return {
        "profile": profile_name,
        "provider": provider_name,
        "models": [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "short_name": m.short_name,
                "description": m.description,
                "context_size": m.context_size,
                "is_default": m.is_default,
                "capabilities": m.capabilities,
                "metadata": m.metadata
            }
            for m in filtered_models
        ]
    }


@router.get("/provider/current")
async def get_current_provider():
    """Get current active provider, profile, and model with display names"""
    from backend.core.provider_manager import ProviderManager
    from backend.core.profile_agent import ProfileAgent
    
    manager = ProviderManager()
    
    # Get current provider
    current_provider_name = manager.current_provider
    provider = manager.get_provider(current_provider_name)
    provider_config = manager.providers_config.get("providers", {}).get(current_provider_name, {})
    provider_display_name = provider_config.get("display_name", current_provider_name)
    
    # Get current profile
    backend_dir = Path(__file__).resolve().parent.parent.parent
    profile_file = backend_dir / "documents" / "current_profile.json"
    current_profile_name = "general_chat"
    if profile_file.exists():
        try:
            profile_data = json.loads(profile_file.read_text(encoding="utf-8"))
            current_profile_name = profile_data.get("profile", "general_chat")
        except:
            pass
    
    # Get profile display name
    profiles_path = backend_dir / "config" / "profiles_kiff.json"
    profile_display_name = current_profile_name
    if profiles_path.exists():
        try:
            profiles_config = json.loads(profiles_path.read_text(encoding="utf-8"))
            profile_display_name = profiles_config.get(current_profile_name, {}).get("display_name", current_profile_name)
        except:
            pass
    
    # Get current model
    agent = ProfileAgent(profile_name=current_profile_name, provider_manager=manager)
    current_model = agent.get_default_model_for_profile(current_profile_name, current_provider_name)
    
    # Get model short name
    model_short_name = current_model
    try:
        all_models = provider.get_models()
        for m in all_models:
            if m.model_id == current_model:
                model_short_name = m.short_name or m.model_id
                break
    except:
        pass
    
    return {
        "provider": current_provider_name,
        "profile": current_profile_name,
        "model": current_model,
        "provider_display_name": provider_display_name,
        "profile_display_name": profile_display_name,
        "model_short_name": model_short_name
    }

