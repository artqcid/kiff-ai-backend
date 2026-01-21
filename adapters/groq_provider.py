"""
groq_provider.py

Groq Provider Implementation
Nutzt OpenAI-kompatible Chat Completions API von Groq
"""

import os
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


class GroqProvider(AbstractLLMProvider):
    """
    Groq Provider für schnelle Cloud-Inferenz
    Nutzt Groq LPU™ Inference Engine mit OpenAI-kompatiblem API
    """
    
    def __init__(self, config: ProviderConfig, models_config: dict):
        super().__init__(config)
        self.base_url = config.base_url
        self.models_config = models_config.get("groq", {}).get("models", {})
        self.api_key = self._get_api_key(config.api_key_env)
        self.timeout = 30  # Groq ist schnell, 30s reicht
        
    def _get_api_key(self, env_var: Optional[str]) -> Optional[str]:
        """Get API key from environment"""
        if env_var:
            return os.getenv(env_var)
        return None
    
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """Send chat request to Groq"""
        
        if not self.api_key:
            raise RuntimeError("Groq API-Key fehlt. Bitte GROQ_API_KEY setzen.")
        
        # Convert ChatMessage objects to dict
        messages_dict = [{"role": msg.role, "content": msg.content} for msg in messages]
        
        # Build payload (OpenAI-compatible)
        payload = {
            "model": model,
            "messages": messages_dict,
            "stream": False,
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if kwargs.get("top_p"):
            payload["top_p"] = kwargs["top_p"]
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response (OpenAI format)
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            content = message.get("content", "").strip()
            
            # Extract usage
            usage = result.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)
            
            # Calculate cost (simplified - aus models config holen)
            model_info = self.get_model_info(model)
            cost_info = self._calculate_cost(usage, model_info)
            
            return ChatResponse(
                content=content,
                model=model,
                provider=self.name,
                tokens_used=total_tokens,
                cost=cost_info.get("total_cost", 0.0),
                metadata={
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": total_tokens,
                    "finish_reason": choice.get("finish_reason", "unknown"),
                    "cost_breakdown": cost_info
                }
            )
            
        except requests.exceptions.HTTPError as e:
            # Handle rate limits and auth errors
            if e.response.status_code == 429:
                raise RuntimeError("Groq Rate Limit erreicht. Bitte später erneut versuchen.")
            elif e.response.status_code == 401:
                raise RuntimeError("Groq API-Key ungültig. Bitte überprüfen.")
            else:
                raise RuntimeError(f"Groq API Error: {e}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Groq request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Unexpected error: {e}")
    
    def _calculate_cost(self, usage: dict, model_info: Optional[ModelInfo]) -> dict:
        """
        Calculate cost based on token usage
        
        Note: Viele Groq-Modelle sind aktuell kostenlos im Free Tier
        """
        if not model_info or not model_info.metadata:
            return {"total_cost": 0.0, "note": "Kostenlos im Free Tier"}
        
        # Parse cost from metadata (format: "$0.20/$0.30 per 1k")
        cost_str = model_info.metadata.get("cost", "$0.00/$0.00")
        if "kostenlos" in cost_str.lower() or "free" in cost_str.lower():
            return {"total_cost": 0.0, "note": "Kostenlos im Free Tier"}
        
        # Extract input/output costs
        try:
            parts = cost_str.split("/")
            input_cost_per_1k = float(parts[0].replace("$", "").strip())
            output_cost_per_1k = float(parts[1].split(" ")[0].replace("$", "").strip())
            
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            
            input_cost = (prompt_tokens / 1000) * input_cost_per_1k
            output_cost = (completion_tokens / 1000) * output_cost_per_1k
            total_cost = input_cost + output_cost
            
            return {
                "total_cost": round(total_cost, 6),
                "input_cost": round(input_cost, 6),
                "output_cost": round(output_cost, 6),
                "input_cost_per_1k": input_cost_per_1k,
                "output_cost_per_1k": output_cost_per_1k
            }
        except:
            return {"total_cost": 0.0, "note": "Kostenberechnung fehlgeschlagen"}
    
    async def validate(self, api_key: Optional[str] = None) -> ProviderValidationResult:
        """Validate Groq API access"""
        
        # Use provided key or fallback to instance key
        test_key = api_key or self.api_key
        
        if not test_key:
            return ProviderValidationResult(
                valid=False,
                message="Kein API-Key vorhanden. Bitte GROQ_API_KEY setzen oder Key eingeben."
            )
        
        # Test with simple request
        headers = {
            "Authorization": f"Bearer {test_key}",
            "Content-Type": "application/json"
        }
        
        # Use minimal payload to test auth
        payload = {
            "model": "gemma2-9b-it",  # Default model
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return ProviderValidationResult(
                    valid=True,
                    message="Groq API-Zugang erfolgreich validiert",
                    details={"api_key_valid": True}
                )
            elif response.status_code == 401:
                return ProviderValidationResult(
                    valid=False,
                    message="API-Key ungültig. Bitte überprüfen."
                )
            elif response.status_code == 429:
                # Rate limit erreicht, aber Key ist gültig
                return ProviderValidationResult(
                    valid=True,
                    message="API-Key gültig (Rate Limit erreicht, normal bei Free Tier)",
                    details={"rate_limited": True}
                )
            else:
                return ProviderValidationResult(
                    valid=False,
                    message=f"Groq API Error: Status {response.status_code}"
                )
                
        except Exception as e:
            return ProviderValidationResult(
                valid=False,
                message=f"Verbindung zu Groq fehlgeschlagen: {e}"
            )
    
    def get_models(self) -> List[ModelInfo]:
        """Get available Groq models from config"""
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
        """Check if Groq API is reachable"""
        if not self.api_key:
            return False
        
        result = await self.validate()
        return result.valid
