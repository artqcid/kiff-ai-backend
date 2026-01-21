"""
llm_client.py

HTTP Client für Ollama (lokal oder remote)
- Nutzt /api/generate (Prompt) und /api/chat (Messages)
- keep_alive zur Schonung von VRAM (6GB RTX 3060)
"""

import os
from typing import Optional, Dict, Any, List

import requests


class LLMClient:
    """HTTP client for Ollama (backed by llama.cpp)"""

    def __init__(self, base_url: Optional[str] = None):
        # Basis-URL konfigurierbar für spätere Remote-Nutzung
        env_url = os.getenv("LLM_SERVER_URL")
        self.base_url = base_url or env_url or "http://localhost:11434"

        # Defaults (überschreibbar per ENV)
        self.default_model = os.getenv("LLM_DEFAULT_MODEL", "mistral-7b")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
        self.top_p = float(os.getenv("LLM_TOP_P", "0.9"))
        self.top_k = int(os.getenv("LLM_TOP_K", "40"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))
        self.timeout = int(os.getenv("LLM_CLIENT_TIMEOUT", "180"))
        self.keep_alive = os.getenv("LLM_KEEP_ALIVE", "5m")

    def _build_options(self, **kwargs) -> Dict[str, Any]:
        """Merge default and override generation options"""
        options = {
            "temperature": kwargs.get("temperature", self.temperature),
            "top_p": kwargs.get("top_p", self.top_p),
            "top_k": kwargs.get("top_k", self.top_k),
            "num_predict": kwargs.get("max_tokens", self.max_tokens),
        }

        # Remove None to avoid overriding Ollama defaults unintentionally
        return {k: v for k, v in options.items() if v is not None}

    def complete(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """Prompt-based completion via Ollama /api/generate"""
        model_name = model or self.default_model
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": kwargs.get("keep_alive", self.keep_alive),
            "options": self._build_options(**kwargs),
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            # Ollama returns text in "response"
            return result.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM Request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, **kwargs) -> str:
        """Chat-style completion via Ollama /api/chat"""
        model_name = model or self.default_model
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "keep_alive": kwargs.get("keep_alive", self.keep_alive),
            "options": self._build_options(**kwargs),
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            message = result.get("message", {})
            return message.get("content", "").strip()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM Request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    def is_healthy(self) -> bool:
        """Check if Ollama server is reachable"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
