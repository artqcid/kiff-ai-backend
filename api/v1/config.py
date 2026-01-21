"""
config.py

Configuration and profile management endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import List
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from backend.api.v1.models import ModelInfo, ProfileInfo, CurrentConfig, ServerConfig
from backend.core.model_registry import ModelRegistry

router = APIRouter()

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
    
    return CurrentConfig(
        model=current_model,
        profile="default",
        server=ServerConfig(
            llama_server_url="http://localhost:8080",
            mcp_server_url="http://localhost:3000",
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
