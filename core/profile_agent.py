"""
profile_agent.py

Multi-Profil Agent
- default, kiff, coding Profile
- Lädt System Prompts aus profiles_kiff.json
- Unterstützt Web-Context Fetching via @tags
"""

import json
import os
from typing import Dict, Optional
from backend.core.llm_client import LLMClient
from backend.mcp import ContextManager


class ProfileAgent:
    """Multi-Profil Agent"""

    def __init__(
        self,
        llm_client: LLMClient,
        profiles_config_path: str = "config/profiles_kiff.json",
    ):
        """
        Args:
            llm_client: LLM Client Instanz
            profiles_config_path: Pfad zu profiles_kiff.json
        """
        self.llm = llm_client
        self.profiles_config_path = profiles_config_path
        self.profiles = self._load_profiles()
        self.current_profile = "default"
        self.context_manager = ContextManager()

    def _load_profiles(self) -> Dict:
        """Lädt Profile aus profiles_kiff.json"""
        if not os.path.exists(self.profiles_config_path):
            # Fallback profiles
            return {
                "default": {
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
            return data.get("profiles", {})

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

    def run(self, query: str, profile_name: Optional[str] = None, **kwargs) -> str:
        """
        Führt Query mit aktuellem oder spezifischem Profil aus

        Args:
            query: User query
            profile_name: Optional override für Profil
            **kwargs: Weitere Parameter für LLM

        Returns:
            LLM response
        """
        # Verwende aktuelles Profil oder override
        active_profile = profile_name if profile_name else self.current_profile
        
        if active_profile not in self.profiles:
            active_profile = "default"

        profile = self.profiles[active_profile]
        system_prompt = profile.get("system_prompt", "")

        # Baue Messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        # Rufe LLM auf
        try:
            response = self.llm.chat(messages, **kwargs)
            return response
        except Exception as e:
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
