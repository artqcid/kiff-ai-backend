"""
model_registry.py

Verwaltet Modelle und LoRA-Adapter aus models_kiff.json
- Lädt und validiert Modell-Konfigurationen
- Gibt verfügbare Modelle / Adapter für UI zurück
- Prüft ob Dateien existieren
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class ModelRegistry:
    """Verwaltet Modelle und Adapter-Konfigurationen"""

    def __init__(self, config_path: str = "config/models_kiff.json"):
        """
        Args:
            config_path: Pfad zur models_kiff.json
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Lädt models_kiff.json"""
        if not os.path.exists(self.config_path):
            # Fallback config
            return {
                "models": {
                    "mistral-7b": {
                        "model_path": "c:/llama/models/mistral-7b-instruct-v0.3.Q4_K_M.gguf",
                        "gpu_layers": 20,
                        "context_size": 8192,
                        "description": "Mistral 7B Instruct",
                        "is_default": True
                    }
                },
                "adapters": {}
            }

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_default_model(self) -> str:
        """Gibt Name des Standard-Modells zurück"""
        for model_name, config in self.config.get("models", {}).items():
            if config.get("is_default"):
                return model_name
        # Fallback auf erstes Modell
        return next(iter(self.config.get("models", {})))

    def get_available_models(self) -> List[str]:
        """Gibt Liste aller verfügbaren Modelle (Base + Adapter)"""
        models = list(self.config.get("models", {}).keys())
        adapters = list(self.config.get("adapters", {}).keys())
        return models + adapters

    def get_model_config(self, model_name: str) -> Optional[Dict]:
        """
        Gibt Konfiguration für ein Modell oder Adapter zurück

        Returns:
            Dict mit: model_path, gpu_layers, context_size, description, lora_path (falls Adapter)
        """
        # Prüfe Basis-Modelle
        if model_name in self.config.get("models", {}):
            model_config = self.config["models"][model_name].copy()
            model_config["type"] = "base_model"
            return model_config

        # Prüfe Adapter
        if model_name in self.config.get("adapters", {}):
            adapter_config = self.config["adapters"][model_name].copy()
            base_model = adapter_config.get("base_model")

            # Hole Config vom Base-Modell
            if base_model and base_model in self.config.get("models", {}):
                base_config = self.config["models"][base_model].copy()
                base_config["type"] = "adapter"
                base_config["lora_path"] = adapter_config.get("lora_path")
                base_config["adapter_name"] = model_name
                base_config["description"] = adapter_config.get("description")
                return base_config

        return None

    def validate_model_paths(self, model_name: str) -> bool:
        """Prüft ob alle erforderlichen Dateien für ein Modell existieren"""
        config = self.get_model_config(model_name)
        if not config:
            return False

        model_path = config.get("model_path")
        if not model_path or not Path(model_path).exists():
            return False

        # Falls Adapter: Prüfe auch LoRA-Datei
        if config.get("type") == "adapter":
            lora_path = config.get("lora_path")
            if not lora_path or not Path(lora_path).exists():
                return False

        return True

    def get_model_details(self, model_name: str) -> str:
        """Gibt Beschreibung eines Modells zurück (für UI)"""
        config = self.get_model_config(model_name)
        return config.get("description", model_name) if config else model_name
