"""
profile_agent.py

Multi-Profil Agent mit Provider-Support
- Unterstützt mehrere LLM Provider (Ollama, Groq, etc.)
- Lädt System Prompts aus profiles_kiff.json oder .md-Dateien
- Provider-aware Model-Auswahl
- Unterstützt Web-Context Fetching via @tags
"""

import json
import os
from typing import Dict, Optional, List
from backend.core.llm_client import LLMClient
from backend.core.provider_manager import get_provider_manager, ProviderManager
from backend.adapters.base_provider import ChatMessage, ChatResponse
from backend.mcp import ContextManager


class ProfileAgent:
    """Multi-Profil Agent mit Provider-Support"""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        profiles_config_path: str = "config/profiles_kiff.json",
        provider_manager: Optional[ProviderManager] = None,
    ):
        """
        Args:
            llm_client: Legacy LLM Client (deprecated, nur für Backward-Compatibility)
            profiles_config_path: Pfad zu profiles_kiff.json
            provider_manager: Provider Manager Instanz
        """
        self.llm = llm_client  # Legacy support
        self.provider_manager = provider_manager or get_provider_manager()
        self.profiles_config_path = profiles_config_path
        self.profiles = self._load_profiles()
        self.current_profile = "general_chat"
        self.context_manager = ContextManager()
        self.last_model_used: Optional[str] = None
        self.last_provider_used: Optional[str] = None
        self.last_response_metadata: Optional[Dict] = None

    def _load_profiles(self) -> Dict:
        """Lädt Profile aus profiles_kiff.json und lädt externe Prompt-Dateien"""
        if not os.path.exists(self.profiles_config_path):
            # Fallback profiles
            return {
                "general_chat": {
                    "name": "Standard Assistant",
                    "system_prompt": "Du bist ein hilfreicher Assistent.",
                    "description": "Allgemeiner Assistent"
                },
                "kiff": {
                    "name": "KIFF Expert",
                    "system_prompt": "Du bist KIFF, ein Experte für Event-Management und Dokumentenerstellung.",
                    "description": "Spezialisiert auf Events"
                },
                "coding": {
                    "name": "Code Assistant",
                    "system_prompt": "Du bist ein Programmier-Assistent.",
                    "description": "Hilft beim Coding"
                }
            }

        with open(self.profiles_config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Support both {"profiles": {...}} and direct {...} format
            profiles = data["profiles"] if "profiles" in data else data
            
            # Load external prompt files if they exist
            config_dir = os.path.dirname(self.profiles_config_path)
            prompts_dir = os.path.join(config_dir, "prompts")
            
            for profile_name, profile_config in profiles.items():
                # Check for external .md prompt file
                prompt_file = os.path.join(prompts_dir, f"{profile_name}.md")
                if os.path.exists(prompt_file):
                    with open(prompt_file, "r", encoding="utf-8") as pf:
                        profile_config["system_prompt"] = pf.read()
            
            return profiles

    def set_profile(self, profile_name: str) -> bool:
        """Wechselt aktives Profil"""
        if profile_name in self.profiles:
            self.current_profile = profile_name
            return True
        return False

    def get_available_profiles(self) -> list:
        """Gibt Liste aller Profile-Namen zurück"""
        return list(self.profiles.keys())

    def get_profile_description(self, profile_name: str) -> str:
        """Gibt Beschreibung eines Profils zurück"""
        profile = self.profiles.get(profile_name, {})
        return profile.get("description", profile_name)
    
    def get_models_for_profile(self, profile_name: Optional[str] = None, provider_name: Optional[str] = None) -> List[str]:
        """
        Gibt unterstützte Modelle für ein Profil und Provider zurück
        
        Args:
            profile_name: Profil-Name (verwendet current wenn None)
            provider_name: Provider-Name (verwendet current wenn None)
            
        Returns:
            Liste von Modell-IDs
        """
        active_profile = profile_name or self.current_profile
        profile = self.profiles.get(active_profile, {})
        
        # Get current provider
        current_provider = provider_name or self.provider_manager.get_current_provider_name()
        
        # Get provider-specific models from profile
        providers_config = profile.get("providers", {})
        provider_config = providers_config.get(current_provider, {})
        
        return provider_config.get("supported_models", [])
    
    def get_default_model_for_profile(self, profile_name: Optional[str] = None, provider_name: Optional[str] = None) -> Optional[str]:
        """
        Gibt Standard-Modell für Profil und Provider zurück
        
        Args:
            profile_name: Profil-Name (verwendet current wenn None)
            provider_name: Provider-Name (verwendet current wenn None)
            
        Returns:
            Modell-ID oder None
        """
        active_profile = profile_name or self.current_profile
        profile = self.profiles.get(active_profile, {})
        
        # Get current provider
        current_provider = provider_name or self.provider_manager.get_current_provider_name()
        
        # Get provider-specific models from profile
        providers_config = profile.get("providers", {})
        provider_config = providers_config.get(current_provider, {})
        
        return provider_config.get("default_model")

    async def run(self, query: str, profile_name: Optional[str] = None, provider_name: Optional[str] = None, **kwargs) -> str:
        """
        Führt Query mit aktuellem oder spezifischem Profil und Provider aus

        Args:
            query: User query
            profile_name: Optional override für Profil
            provider_name: Optional override für Provider
            **kwargs: Weitere Parameter für LLM (model, temperature, max_tokens, etc.)

        Returns:
            LLM response
        """
        # Verwende aktuelles Profil oder override
        active_profile = profile_name if profile_name else self.current_profile
        
        if active_profile not in self.profiles:
            active_profile = "general_chat"

        profile = self.profiles[active_profile]
        system_prompt = profile.get("system_prompt", "")
        
        # Determine provider
        active_provider = provider_name or self.provider_manager.get_current_provider_name()
        
        # Model-Auflösung: kwargs.model > profile default for provider > first supported model
        model_name = kwargs.pop("model", None)
        if not model_name:
            model_name = self.get_default_model_for_profile(active_profile, active_provider)
        
        # Fallback: Use first supported model if no default
        if not model_name:
            supported_models = self.get_models_for_profile(active_profile, active_provider)
            if supported_models:
                model_name = supported_models[0]
            else:
                raise RuntimeError(f"Keine Modelle für Profil '{active_profile}' und Provider '{active_provider}' konfiguriert")
        
        # WICHTIG: Setze last_model_used und last_provider_used VOR dem LLM-Aufruf
        self.last_model_used = model_name
        self.last_provider_used = active_provider

        # Profile-Parameter als Defaults verwenden
        params = profile.get("parameters", {}) or {}
        temperature = kwargs.pop("temperature", params.get("temperature"))
        max_tokens = kwargs.pop("max_tokens", params.get("max_tokens"))

        # Baue Messages mit ChatMessage-Objekten
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=query)
        ]

        # Rufe Provider auf
        try:
            response: ChatResponse = await self.provider_manager.chat(
                messages=messages,
                model=model_name,
                provider_name=active_provider,
                temperature=temperature,
                max_tokens=max_tokens
            )
            # Store response metadata for rate limits
            if hasattr(response, 'metadata'):
                self.last_response_metadata = response.metadata
            return response.content
        except Exception as e:
            # Fallback zu lokalem Provider wenn möglich
            if active_provider != "lokal":
                try:
                    print(f"⚠️  Provider '{active_provider}' failed: {e}")
                    print(f"🔄 Fallback zu lokalem Provider...")
                    
                    # Get default model for lokal provider
                    fallback_model = self.get_default_model_for_profile(active_profile, "lokal")
                    if not fallback_model:
                        fallback_model = "mistral-7b"
                    
                    self.last_provider_used = "lokal"
                    self.last_model_used = fallback_model
                    
                    response: ChatResponse = await self.provider_manager.chat(
                        messages=messages,
                        model=fallback_model,
                        provider_name="lokal",
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    return f"⚠️ Fallback zu lokalem Modell\n\n{response.content}"
                except Exception as fallback_error:
                    return f"Error: Provider '{active_provider}' failed: {e}\nFallback failed: {fallback_error}"
            else:
                return f"Error: {str(e)}"

    def get_current_profile(self) -> str:
        """Gibt Namen des aktuellen Profils zurück"""
        return self.current_profile

    def detect_profile(self, prompt: str) -> str:
        """
        Erkennt Profil basierend auf Keywords im Prompt
        
        Args:
            prompt: User-Prompt Text
            
        Returns:
            Profil-Name ("kiff" oder "default")
        """
        p = prompt.lower()
        if any(k in p for k in ["kiff", "kiff2.0", "betra"]):
            return "kiff"
        return "default"

    async def get_contexts_for_prompt(self, prompt: str) -> Dict[str, str]:
        """
        Fetcht Web-Contexts für einen Prompt basierend auf @tags
        
        Args:
            prompt: User-Prompt mit potentiellen @tags
            
        Returns:
            Dict mapping URLs zu deren Text-Inhalten
        """
        try:
            contexts = await self.context_manager.fetch_contexts_for_prompt(prompt)
            return contexts
        except Exception as e:
            # Log error but don't fail
            print(f"Error fetching contexts: {e}")
            return {}
