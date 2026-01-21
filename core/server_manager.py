"""
server_manager.py

Historisch für llama.cpp Process-Handling. Nicht mehr genutzt seit Umstieg auf Ollama.
Belassen für Referenz; kann entfernt werden, wenn keine Altpfade mehr genutzt werden.
"""

import json
import os
import subprocess
import time
import requests
from pathlib import Path
from typing import Optional, Dict
from backend.core.model_registry import ModelRegistry


class ServerManager:
    """Manages llama.cpp and MCP server lifecycle"""

    def __init__(self, config_path: str = "config/servers_kiff.json"):
        """
        Args:
            config_path: Pfad zur servers_kiff.json
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.model_registry = ModelRegistry()
        self.current_model: Optional[str] = None
        self.llama_process = None
        self.mcp_process = None

    def _load_config(self) -> Dict:
        """Lädt servers_kiff.json"""
        if not os.path.exists(self.config_path):
            # Fallback legacy config (deprecated; Ollama used instead)
            return {
                "llama_server": {
                    "deprecated": True,
                    "note": "llama.cpp launcher removed; use Ollama"
                },
                "mcp_server": {
                    "launch_script": "scripts/start_mcp_server.ps1"
                }
            }

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def start_all_servers(self, model_name: Optional[str] = None) -> bool:
        """
        Startet llama.cpp und MCP Server

        Args:
            model_name: Modell-Name (Default aus Registry)

        Returns:
            True bei erfolg, False bei Fehler
        """
        if not model_name:
            model_name = self.model_registry.get_default_model()

        # Starte llama.cpp
        if not self.start_llama_server(model_name):
            return False

        # Starte MCP
        if not self.start_mcp_server():
            return False

        self.current_model = model_name
        return True

    def start_llama_server(self, model_name: str) -> bool:
        """
        Startet llama.cpp Server mit spezifischem Modell

        Args:
            model_name: Modell aus Registry

        Returns:
            True bei erfolg
        """
        # Hole Modell-Config
        model_config = self.model_registry.get_model_config(model_name)
        if not model_config:
            print(f"[KIFF] ERROR: Modell nicht gefunden: {model_name}")
            return False

        # Validiere Pfade
        if not self.model_registry.validate_model_paths(model_name):
            print(f"[KIFF] ERROR: Modell-Dateien nicht gefunden für: {model_name}")
            return False

        # Hole Script-Pfad
        launch_script = self.config["llama_server"]["launch_script"]
        if not Path(launch_script).exists():
            print(f"[KIFF] ERROR: Launch-Script nicht gefunden: {launch_script}")
            return False

        # Vorbereite PowerShell Aufruf
        model_path = model_config["model_path"]
        gpu_layers = model_config["gpu_layers"]
        context_size = model_config["context_size"]
        lora_path = model_config.get("lora_path", "")

        print(f"[KIFF] Starte llama.cpp mit Modell: {model_name}")

        try:
            # Rufe PowerShell-Script auf
            ps_cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                launch_script,
                "-model_path",
                model_path,
                "-gpu_layers",
                str(gpu_layers),
                "-context_size",
                str(context_size),
            ]

            if lora_path:
                ps_cmd.extend(["-lora_path", lora_path])

            self.llama_process = subprocess.Popen(
                ps_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )

            # Health-Check: Warte bis Server antwortet
            if self._health_check_llama():
                print(f"[KIFF] llama.cpp Server läuft auf Port 8080")
                self.current_model = model_name
                return True
            else:
                print(f"[KIFF] ERROR: llama.cpp Server konnte nicht erreicht werden")
                return False

        except Exception as e:
            print(f"[KIFF] ERROR beim Starten von llama.cpp: {e}")
            return False

    def start_mcp_server(self) -> bool:
        """Startet MCP Server"""
        launch_script = self.config["mcp_server"]["launch_script"]
        if not Path(launch_script).exists():
            print(f"[KIFF] WARNING: MCP Launch-Script nicht gefunden: {launch_script}")
            return True  # MCP ist optional

        try:
            ps_cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                launch_script,
            ]

            self.mcp_process = subprocess.Popen(
                ps_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )

            time.sleep(1)  # Kurze Wartezeit für MCP-Start
            print(f"[KIFF] MCP Server gestartet")
            return True

        except Exception as e:
            print(f"[KIFF] WARNING: Fehler beim Starten von MCP: {e}")
            return True  # MCP ist optional

    def _health_check_llama(self) -> bool:
        """Prüft ob llama.cpp:8080 antwortet"""
        health_url = self.config["llama_server"]["health_check_url"]
        timeout = self.config["llama_server"]["startup_timeout_seconds"]
        retry_delay = self.config["llama_server"]["retry_delay_seconds"]

        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                pass

            time.sleep(retry_delay)

        return False

    def is_healthy(self) -> bool:
        """Prüft ob llama.cpp Server noch läuft"""
        try:
            health_url = self.config["llama_server"]["health_check_url"]
            response = requests.get(health_url, timeout=2)
            return response.status_code == 200
        except:
            return False

    def stop_all_servers(self) -> None:
        """Stoppt llama.cpp und MCP Server"""
        if self.llama_process:
            try:
                self.llama_process.terminate()
                self.llama_process.wait(timeout=5)
                print("[KIFF] llama.cpp Server gestoppt")
            except Exception as e:
                print(f"[KIFF] ERROR beim Stoppen von llama.cpp: {e}")
            finally:
                self.llama_process = None

        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                self.mcp_process.wait(timeout=5)
                print("[KIFF] MCP Server gestoppt")
            except Exception as e:
                print(f"[KIFF] WARNING beim Stoppen von MCP: {e}")
            finally:
                self.mcp_process = None

        self.current_model = None

    def switch_model(self, model_name: str) -> bool:
        """
        Wechselt Modell durch Server-Neustart

        Args:
            model_name: Neues Modell

        Returns:
            True bei erfolg
        """
        print(f"[KIFF] Wechsle Modell zu: {model_name}")
        self.stop_all_servers()
        time.sleep(2)  # Kurze Pause zwischen Stop und Start
        return self.start_all_servers(model_name)

    def get_status(self) -> Dict:
        """Gibt aktuellen Server-Status zurück"""
        return {
            "llama_running": self.llama_process is not None and self.is_healthy(),
            "mcp_running": self.mcp_process is not None,
            "current_model": self.current_model,
        }
