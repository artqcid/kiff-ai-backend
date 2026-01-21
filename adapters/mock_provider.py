"""
mock_provider.py

Mock Provider für Tests
Simuliert LLM-Antworten ohne echte API-Calls
"""

from typing import List, Optional
import time

from backend.adapters.base_provider import (
    AbstractLLMProvider,
    ProviderConfig,
    ModelInfo,
    ChatMessage,
    ChatResponse,
    ProviderValidationResult
)


class MockProvider(AbstractLLMProvider):
    """
    Mock Provider für Unit-Tests
    Gibt vordefinierte Antworten zurück ohne echte API-Calls
    """
    
    def __init__(self, config: ProviderConfig, mock_responses: Optional[dict] = None):
        super().__init__(config)
        self.mock_responses = mock_responses or {
            "default": "Dies ist eine Mock-Antwort vom Test-Provider."
        }
        self.call_count = 0
        self.last_request = None
        
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """Return mock response"""
        
        self.call_count += 1
        self.last_request = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "kwargs": kwargs
        }
        
        # Simulate some processing time
        time.sleep(0.1)
        
        # Get mock response
        user_message = messages[-1].content if messages else ""
        response_content = self.mock_responses.get(
            user_message,
            self.mock_responses.get("default", "Mock response")
        )
        
        return ChatResponse(
            content=response_content,
            model=model,
            provider=self.name,
            tokens_used=100,
            cost=0.0,
            metadata={
                "mock": True,
                "call_count": self.call_count
            }
        )
    
    async def validate(self, api_key: Optional[str] = None) -> ProviderValidationResult:
        """Always validate successfully"""
        return ProviderValidationResult(
            valid=True,
            message="Mock provider is always valid",
            details={"mock": True}
        )
    
    def get_models(self) -> List[ModelInfo]:
        """Return mock models"""
        return [
            ModelInfo(
                model_id="mock-model",
                display_name="Mock Model",
                description="Test model for unit tests",
                short_name="mock",
                context_size=8192,
                is_default=True,
                capabilities=["chat", "test"],
                metadata={
                    "context": "8K",
                    "speed": "instant",
                    "cost": "Free",
                    "request_limit": "Unlimited",
                    "token_limit": "Unlimited"
                }
            )
        ]
    
    async def is_healthy(self) -> bool:
        """Always healthy"""
        return True
    
    def set_mock_response(self, trigger: str, response: str):
        """Set custom mock response for specific trigger"""
        self.mock_responses[trigger] = response
    
    def reset(self):
        """Reset mock state"""
        self.call_count = 0
        self.last_request = None
