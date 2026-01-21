"""
base_provider.py

Abstract Base Class für LLM Provider
Definiert das Interface für alle Provider (Ollama, Groq, OpenAI, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class ProviderConfig(BaseModel):
    """Provider-Konfiguration"""
    name: str
    display_name: str
    type: str
    enabled: bool
    description: str
    base_url: str
    requires_api_key: bool
    api_key_env: Optional[str] = None
    features: Dict[str, bool]
    rate_limits: Dict[str, Any]
    cost: Dict[str, Any]


class ModelInfo(BaseModel):
    """Model-Informationen"""
    model_id: str
    display_name: str
    description: str
    short_name: str
    context_size: int
    is_default: bool
    capabilities: List[str]
    metadata: Dict[str, str]


class ChatMessage(BaseModel):
    """Chat-Nachricht"""
    role: str  # "system", "user", "assistant"
    content: str


class ChatResponse(BaseModel):
    """Chat-Antwort"""
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    cost: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ProviderValidationResult(BaseModel):
    """Validierungsergebnis eines Providers"""
    valid: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class AbstractLLMProvider(ABC):
    """
    Abstract Base Class für LLM Provider
    
    Jeder Provider (Ollama, Groq, OpenAI, etc.) muss diese Methoden implementieren.
    """
    
    def __init__(self, config: ProviderConfig):
        """
        Initialisiert den Provider mit Konfiguration
        
        Args:
            config: Provider-Konfiguration aus providers_kiff.json
        """
        self.config = config
        self.name = config.name
        self.type = config.type
        
    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatResponse:
        """
        Sendet Chat-Anfrage an Provider
        
        Args:
            messages: Liste von Chat-Nachrichten (system, user, assistant)
            model: Model-ID (z.B. "mistral-7b", "gemma2-9b-it")
            temperature: Temperature-Parameter (0.0-1.0)
            max_tokens: Maximale Token-Anzahl
            **kwargs: Weitere Provider-spezifische Parameter
            
        Returns:
            ChatResponse mit generierter Antwort und Metadaten
            
        Raises:
            RuntimeError: Bei API-Fehlern oder Validierungsproblemen
        """
        pass
    
    @abstractmethod
    async def validate(self, api_key: Optional[str] = None) -> ProviderValidationResult:
        """
        Validiert Provider-Konfiguration und API-Zugang
        
        Args:
            api_key: Optional API-Key zum Testen (falls nicht in ENV)
            
        Returns:
            ProviderValidationResult mit Status und Fehlermeldung
        """
        pass
    
    @abstractmethod
    def get_models(self) -> List[ModelInfo]:
        """
        Gibt Liste verfügbarer Modelle zurück
        
        Returns:
            Liste von ModelInfo mit allen Details
        """
        pass
    
    @abstractmethod
    async def is_healthy(self) -> bool:
        """
        Prüft ob Provider erreichbar und funktional ist
        
        Returns:
            True wenn gesund, False bei Problemen
        """
        pass
    
    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """
        Gibt Informationen zu spezifischem Modell zurück
        
        Args:
            model_id: Model-ID
            
        Returns:
            ModelInfo oder None wenn nicht gefunden
        """
        models = self.get_models()
        for model in models:
            if model.model_id == model_id:
                return model
        return None
    
    def supports_streaming(self) -> bool:
        """Gibt zurück ob Provider Streaming unterstützt"""
        return self.config.features.get("streaming", False)
    
    def supports_function_calling(self) -> bool:
        """Gibt zurück ob Provider Function Calling unterstützt"""
        return self.config.features.get("function_calling", False)
    
    def requires_api_key(self) -> bool:
        """Gibt zurück ob Provider API-Key benötigt"""
        return self.config.requires_api_key
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Gibt Rate Limits zurück"""
        return self.config.rate_limits
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' type='{self.type}'>"
