"""
Context Manager für KIFF-AI Backend

Verwaltet Web-Context-Sets und deren Auflösung aus JSON-Konfiguration.
Fetcht Contexts basierend auf @tags in User-Prompts.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Set

from .web_context_service import fetch_text

logger = logging.getLogger(__name__)

# Pfad zur KIFF Context-Konfiguration
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONTEXT_SETS_FILE = CONFIG_DIR / "context_sets_kiff.json"


class ContextManager:
    """
    Verwaltet Context-Sets und fetcht Web-Inhalte basierend auf @tags
    """

    def __init__(self, config_file: Path = CONTEXT_SETS_FILE):
        self.config_file = config_file
        self.context_sets: Dict = {}
        self._load_context_sets()

    def _load_context_sets(self):
        """Lädt Context-Sets aus JSON-Konfiguration"""
        try:
            if not self.config_file.exists():
                logger.warning(f"Context sets file not found: {self.config_file}")
                self.context_sets = {}
                return

            with open(self.config_file, "r", encoding="utf-8") as f:
                self.context_sets = json.load(f)

            logger.info(f"Loaded {len(self.context_sets)} context sets from {self.config_file}")

        except Exception as e:
            logger.error(f"Failed to load context sets: {e}")
            self.context_sets = {}

    def reload_context_sets(self):
        """Lädt Context-Sets neu (für dynamische Updates)"""
        self._load_context_sets()

    def resolve_set(self, name: str, seen: Set[str] | None = None) -> List[str]:
        """
        Löst ein Context-Set rekursiv auf.
        Unterstützt @references auf andere Sets.

        Args:
            name: Name des Context-Sets (mit oder ohne @)
            seen: Set von bereits besuchten Sets (verhindert Zyklen)

        Returns:
            Liste von URLs
        """
        if seen is None:
            seen = set()

        # Normalisiere name - stelle sicher dass @ vorhanden ist
        if not name.startswith("@"):
            name = "@" + name

        if name in seen:
            logger.warning(f"Circular reference detected in context set: {name}")
            return []

        seen.add(name)

        set_data = self.context_sets.get(name, {})

        # Unterstütze sowohl Liste als auch Dict-Format
        if isinstance(set_data, list):
            urls_or_sets = set_data
        elif isinstance(set_data, dict):
            urls_or_sets = set_data.get("urls", [])
        else:
            logger.warning(f"Invalid format for context set: {name}")
            urls_or_sets = []

        resolved = []
        for item in urls_or_sets:
            if isinstance(item, str):
                if item.startswith("@"):
                    # Rekursive Auflösung von referenzierten Sets
                    resolved.extend(self.resolve_set(item, seen.copy()))
                else:
                    # Direkte URL
                    resolved.append(item)

        return resolved

    def parse_prompt_for_sets(self, prompt: str) -> List[str]:
        """
        Extrahiert @tags aus einem Prompt.

        Args:
            prompt: User-Prompt Text

        Returns:
            Liste von Context-Set Namen (mit @)
        """
        # Finde alle @words die in context_sets existieren
        words = prompt.split()
        found_sets = []

        for word in words:
            # Entferne Satzzeichen am Ende
            word = re.sub(r'[.,!?;:]$', '', word)

            if word.startswith("@"):
                # Check both with and without @ prefix in keys
                if word in self.context_sets:
                    found_sets.append(word)
                elif word[1:] in self.context_sets:
                    found_sets.append(word[1:])
                else:
                    logger.debug(f"Unknown context set referenced: {word}")

        return found_sets

    async def fetch_contexts_for_prompt(self, prompt: str) -> Dict[str, str]:
        """
        Fetcht alle Contexts die in einem Prompt via @tags referenziert werden.

        Args:
            prompt: User-Prompt mit @tags

        Returns:
            Dict mapping URLs zu deren Text-Inhalten.
            Fehlerhafte URLs werden übersprungen.
        """
        # Parse @tags
        set_names = self.parse_prompt_for_sets(prompt)

        if not set_names:
            logger.debug("No context sets found in prompt")
            return {}

        logger.info(f"Found context sets in prompt: {set_names}")

        # Resolve URLs
        all_urls = []
        for set_name in set_names:
            urls = self.resolve_set(set_name)
            all_urls.extend(urls)

        # Deduplizieren
        unique_urls = list(set(all_urls))
        logger.info(f"Fetching {len(unique_urls)} unique URLs for context")

        # Fetch alle URLs
        contexts = {}
        for url in unique_urls:
            try:
                text, _ = await fetch_text(url)
                if text:
                    contexts[url] = text
                    logger.info(f"Successfully fetched context from {url}")
            except Exception as e:
                logger.warning(f"Failed to fetch context from {url}: {e}")
                # Überspringe fehlerhafte URLs, blockiere Chat nicht

        logger.info(f"Successfully fetched {len(contexts)} contexts")
        return contexts

    def get_available_sets(self) -> List[str]:
        """Gibt Liste aller verfügbaren Context-Set Namen zurück"""
        return list(self.context_sets.keys())

    def get_set_urls(self, set_name: str) -> List[str]:
        """Gibt alle URLs für ein bestimmtes Set zurück (resolved)"""
        return self.resolve_set(set_name)
