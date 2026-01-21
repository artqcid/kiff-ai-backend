"""
ollama_provider.py

Ollama Provider Implementation
Wrapper für bestehende LLMClient-Logik als AbstractLLMProvider
"""

import os
import json
from typing import List, Optional
import requests

from backend.adapters.base_provider import (
    AbstractLLMProvider,
    ProviderConfig,
    ModelInfo,
    ChatMessage,
    ChatResponse,
    ProviderValidationResult
)


class OllamaProvider(AbstractLLMProvider):
    """
    Ollama Provider für lokale LLM-Inferenz
    Nutzt llama.cpp mit Ollama Server
    """
    
    def __init__(self, config: ProviderConfig, models_config: dict):
        super().__init__(config)
        self.base_url = self._resolve_base_url(config.base_url)
        self.models_config = models_config.get("lokal", {}).get("models", {})
        self.timeout = int(os.getenv("LLM_CLIENT_TIMEOUT", "180"))
        self.keep_alive = os.getenv("LLM_KEEP_ALIVE", "5m")
        
    def _resolve_base_url(self, url_template: str) -> str:
        """Resolve ENV variable in URL template"""
        if "${" in url_template:
            # Extract default: ${LLM_SERVER_URL:http://localhost:11434}
            parts = url_template.split(":")
            env_var = parts[0].replace("${", "").replace("}", "")
            default = ":".join(parts[1:]).replace("}", "") if len(parts) > 1 else "http://localhost:11434"
            return os.getenv(env_var, default)
        return url_template
    
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """Send chat request to Ollama"""
        
        # Build options
        options = {}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        if kwargs.get("top_p"):
            options["top_p"] = kwargs["top_p"]
        if kwargs.get("top_k"):
            options["top_k"] = kwargs["top_k"]
        
        # Convert ChatMessage objects to dict
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]
        
        payload = {
            "model": model,
            "messages": messages_dict,
            "stream": False,
            "keep_alive": kwargs.get("keep_alive", self.keep_alive),
            "options": options if options else {}
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            message = result.get("message", {})
            content = message.get("content", "").strip()
            
            # Extract metadata
            eval_count = result.get("eval_count", 0)
            
            return ChatResponse(
                content=content,
                model=model,
                provider=self.name,
                tokens_used=eval_count,
                cost=0.0,  # Lokal = kostenlos
                metadata={
                    "eval_count": eval_count,
                    "prompt_eval_count": result.get("prompt_eval_count", 0),
                    "total_duration": result.get("total_duration", 0),
                }
            )
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")
    
    async def validate(self, api_key: Optional[str] = None) -> ProviderValidationResult:
        """Validate Ollama server is reachable"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                tags = response.json().get("models", [])
                return ProviderValidationResult(
                    valid=True,
                    message="Ollama server erreichbar",
                    details={"available_models": len(tags)}
                )
            else:
                return ProviderValidationResult(
                    valid=False,
                    message=f"Ollama server antwortet mit Status {response.status_code}"
                )
        except Exception as e:
            return ProviderValidationResult(
                valid=False,
                message=f"Ollama server nicht erreichbar: {e}"
            )
    
    def get_models(self) -> List[ModelInfo]:
        """Get available local models from config"""
        models = []
        for model_id, model_data in self.models_config.items():
            models.append(ModelInfo(
                model_id=model_id,
                display_name=model_data.get("display_name", model_id),
                description=model_data.get("description", ""),
                short_name=model_data.get("short_name", model_id),
                context_size=model_data.get("context_size", 8192),
                is_default=model_data.get("is_default", False),
                capabilities=model_data.get("capabilities", []),
                metadata=model_data.get("metadata", {})
            ))
        return models
    
    async def is_healthy(self) -> bool:
        """Check if Ollama is healthy"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
