"""
llm_client.py

HTTP Client für llama.cpp Server auf localhost:8080
- Unterstützt Completion Endpoint
- Streaming Support optional
"""

import requests
import json
from typing import Optional, Dict, Any


class LLMClient:
    """Simple HTTP client for llama.cpp server"""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.temperature = 0.1
        self.top_p = 0.9
        self.top_k = 40
        self.max_tokens = 512
        self.timeout = 60

    def complete(self, prompt: str, **kwargs) -> str:
        """
        Ruft llama.cpp Completion Endpoint auf

        Args:
            prompt: Input prompt
            **kwargs: Override parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text
        """
        try:
            # Payload für /completion Endpoint
            payload = {
                "prompt": prompt,
                "temperature": kwargs.get("temperature", self.temperature),
                "top_p": kwargs.get("top_p", self.top_p),
                "top_k": kwargs.get("top_k", self.top_k),
                "n_predict": kwargs.get("max_tokens", self.max_tokens),
                "stop": kwargs.get("stop", []),
                "stream": False,
            }

            response = requests.post(
                f"{self.base_url}/completion",
                json=payload,
                timeout=self.timeout,
            )

            response.raise_for_status()
            result = response.json()

            # llama.cpp gibt content in "content" Feld zurück
            return result.get("content", "").strip()

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LLM Request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")

    def chat(self, messages: list, **kwargs) -> str:
        """
        Chat-style completion

        Args:
            messages: List of dicts with 'role' and 'content'
            **kwargs: Override parameters

        Returns:
            Generated text
        """
        # Convert messages to prompt
        prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt += f"System: {content}\n"
            elif role == "user":
                prompt += f"User: {content}\n"
            elif role == "assistant":
                prompt += f"Assistant: {content}\n"

        prompt += "Assistant: "

        return self.complete(prompt, **kwargs)

    def is_healthy(self) -> bool:
        """Check if llama.cpp server is running"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
