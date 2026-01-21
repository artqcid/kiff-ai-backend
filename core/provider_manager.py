"""
provider_manager.py

Provider Manager - Zentrale Verwaltung aller LLM Provider
- Registry für Provider (Ollama, Groq, OpenAI, etc.)
- Factory Pattern für Provider-Instanziierung
- Persistierung des aktuellen Providers
- Provider-Wechsel und Validierung
"""

import json
import os
from typing import Dict, Optional, List
from pathlib import Path

from backend.adapters.base_provider import (
    AbstractLLMProvider,
    ProviderConfig,
    ModelInfo,
    ChatMessage,
    ChatResponse,
    ProviderValidationResult
)
from backend.adapters.ollama_provider import OllamaProvider
from backend.adapters.groq_provider import GroqProvider


class ProviderManager:
    """
    Singleton Manager für alle LLM Provider
    """
    
    _instance: Optional['ProviderManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.providers: Dict[str, AbstractLLMProvider] = {}
        self.current_provider_name: Optional[str] = None
        
        # Load configs
        self.backend_dir = Path(__file__).parent.parent
        self.providers_config_path = self.backend_dir / "config" / "providers_kiff.json"
        self.models_config_path = self.backend_dir / "config" / "models_kiff.json"
        self.current_provider_path = self.backend_dir / "documents" / "current_provider.json"
        
        # Initialize providers
        self._load_and_register_providers()
        
        # Load persisted current provider
        self.current_provider_name = self._load_current_provider()
    
    def _load_and_register_providers(self):
        """Load provider configs and register provider instances"""
        
        # Load providers config
        with open(self.providers_config_path, "r", encoding="utf-8") as f:
            providers_data = json.load(f)
        
        # Load models config
        with open(self.models_config_path, "r", encoding="utf-8") as f:
            models_data = json.load(f)
        
        # Register each enabled provider
        providers_config = providers_data.get("providers", {})
        
        for provider_name, provider_data in providers_config.items():
            if not provider_data.get("enabled", False):
                continue
            
            # Create ProviderConfig
            config = ProviderConfig(**provider_data)
            
            # Instantiate provider based on type
            provider_type = config.type
            
            if provider_type == "ollama":
                provider = OllamaProvider(config, models_data.get("providers", {}))
            elif provider_type == "groq":
                provider = GroqProvider(config, models_data.get("providers", {}))
            else:
                print(f"⚠️  Unknown provider type: {provider_type}, skipping {provider_name}")
                continue
            
            self.providers[provider_name] = provider
            print(f"✅ Registered provider: {provider_name} ({provider_type})")
    
    def _load_current_provider(self) -> str:
        """Load persisted current provider or return default"""
        
        # Create documents directory if not exists
        self.current_provider_path.parent.mkdir(parents=True, exist_ok=True)
        
        if self.current_provider_path.exists():
            try:
                with open(self.current_provider_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    provider_name = data.get("provider", "lokal")
                    
                    # Validate provider exists
                    if provider_name in self.providers:
                        return provider_name
            except Exception as e:
                print(f"⚠️  Failed to load current provider: {e}")
        
        # Default to "lokal"
        return "lokal"
    
    def _save_current_provider(self, provider_name: str):
        """Persist current provider to file"""
        try:
            with open(self.current_provider_path, "w", encoding="utf-8") as f:
                json.dump({"provider": provider_name}, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save current provider: {e}")
    
    def get_provider(self, provider_name: Optional[str] = None) -> AbstractLLMProvider:
        """
        Get provider by name or current provider
        
        Args:
            provider_name: Optional provider name, uses current if None
            
        Returns:
            AbstractLLMProvider instance
            
        Raises:
            ValueError: If provider not found
        """
        name = provider_name or self.current_provider_name
        
        if not name or name not in self.providers:
            raise ValueError(f"Provider '{name}' not found. Available: {list(self.providers.keys())}")
        
        return self.providers[name]
    
    def set_current_provider(self, provider_name: str) -> bool:
        """
        Set current provider and persist
        
        Args:
            provider_name: Name of provider to set as current
            
        Returns:
            True if successful, False if provider not found
        """
        if provider_name not in self.providers:
            return False
        
        self.current_provider_name = provider_name
        self._save_current_provider(provider_name)
        return True
    
    def get_current_provider_name(self) -> str:
        """Get name of current provider"""
        return self.current_provider_name or "lokal"
    
    def get_available_providers(self) -> List[Dict]:
        """
        Get list of all available providers with status
        
        Returns:
            List of provider info dicts
        """
        result = []
        
        for name, provider in self.providers.items():
            result.append({
                "name": name,
                "display_name": provider.config.display_name,
                "type": provider.config.type,
                "enabled": provider.config.enabled,
                "description": provider.config.description,
                "requires_api_key": provider.requires_api_key(),
                "has_api_key": self._check_api_key(provider),
                "is_current": name == self.current_provider_name,
                "features": provider.config.features,
                "rate_limits": provider.config.rate_limits
            })
        
        return result
    
    def _check_api_key(self, provider: AbstractLLMProvider) -> bool:
        """Check if provider has API key configured"""
        if not provider.requires_api_key():
            return True  # No key needed
        
        api_key_env = provider.config.api_key_env
        if api_key_env:
            return bool(os.getenv(api_key_env))
        
        return False
    
    async def validate_provider(self, provider_name: str, api_key: Optional[str] = None) -> ProviderValidationResult:
        """
        Validate provider configuration and access
        
        Args:
            provider_name: Name of provider to validate
            api_key: Optional API key to test (if not in ENV)
            
        Returns:
            ProviderValidationResult
        """
        if provider_name not in self.providers:
            return ProviderValidationResult(
                valid=False,
                message=f"Provider '{provider_name}' nicht gefunden"
            )
        
        provider = self.providers[provider_name]
        return await provider.validate(api_key)
    
    def get_models_for_provider(self, provider_name: Optional[str] = None) -> List[ModelInfo]:
        """
        Get available models for provider
        
        Args:
            provider_name: Provider name, uses current if None
            
        Returns:
            List of ModelInfo
        """
        provider = self.get_provider(provider_name)
        return provider.get_models()
    
    def get_model_info(self, model_id: str, provider_name: Optional[str] = None) -> Optional[ModelInfo]:
        """
        Get info for specific model
        
        Args:
            model_id: Model ID
            provider_name: Provider name, uses current if None
            
        Returns:
            ModelInfo or None
        """
        provider = self.get_provider(provider_name)
        return provider.get_model_info(model_id)
    
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        provider_name: Optional[str] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Send chat request to provider
        
        Args:
            messages: Chat messages
            model: Model ID
            provider_name: Provider name, uses current if None
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            ChatResponse
        """
        provider = self.get_provider(provider_name)
        return await provider.chat(messages, model, **kwargs)
    
    async def is_healthy(self, provider_name: Optional[str] = None) -> bool:
        """
        Check if provider is healthy
        
        Args:
            provider_name: Provider name, uses current if None
            
        Returns:
            True if healthy
        """
        try:
            provider = self.get_provider(provider_name)
            return await provider.is_healthy()
        except:
            return False


# Global singleton instance
_provider_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get global ProviderManager singleton"""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager
