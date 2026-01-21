"""
Web Context Service für KIFF-AI Backend

Dieses Modul stellt Funktionalität zum Fetchen und Cachen von Web-Inhalten bereit,
die als Kontext für LLM-Anfragen verwendet werden können.

Features:
- HTML-zu-Text Konvertierung
- Datei-basiertes Caching mit TTL
- Rate Limiting pro Domain
- Async HTTP-Requests mit httpx
"""

import hashlib
import html.parser
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Konfiguration
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_TTL_DAYS = 14
CACHE_TTL_SECONDS = CACHE_TTL_DAYS * 24 * 3600
MAX_CHARS_PER_URL = 10000
REQUEST_TIMEOUT = 10

# Rate Limiting: 10 Requests pro Minute pro Domain
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_WINDOW = 60  # Sekunden

# Cache-Verzeichnis erstellen
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class TextExtractor(html.parser.HTMLParser):
    """
    HTML Parser der nur Text-Inhalte extrahiert (ohne Tags, Scripts, etc.)
    """

    def __init__(self):
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str):
        """Sammelt Text-Daten aus HTML"""
        data = data.strip()
        if data:
            self.parts.append(data)

    def text(self) -> str:
        """Gibt den gesammelten Text zurück"""
        return " ".join(self.parts)


class RateLimiter:
    """
    Dict-basierter Rate Limiter der Requests pro Domain limitiert.
    Verwendet Timestamps in einer Liste pro Domain.
    """

    def __init__(self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)

    def _cleanup_old_requests(self, domain: str):
        """Entfernt Timestamps außerhalb des Zeitfensters"""
        now = time.time()
        cutoff = now - self.window_seconds
        self.requests[domain] = [ts for ts in self.requests[domain] if ts > cutoff]

    def is_allowed(self, url: str) -> bool:
        """Prüft ob Request erlaubt ist"""
        domain = urlparse(url).netloc
        self._cleanup_old_requests(domain)

        if len(self.requests[domain]) >= self.max_requests:
            logger.debug(f"Rate limit reached for domain {domain}")
            return False

        return True

    def record_request(self, url: str):
        """Registriert einen Request"""
        domain = urlparse(url).netloc
        self.requests[domain].append(time.time())


# Globaler Rate Limiter (Singleton)
_rate_limiter = RateLimiter()


def url_to_cache_file(url: str) -> Path:
    """
    Generiert Cache-Dateinamen aus URL via SHA-256 Hash
    """
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{h}.txt"


def get_cache_ttl() -> int:
    """
    Gibt Cache-TTL in Sekunden zurück (fix 14 Tage für KIFF)
    """
    return CACHE_TTL_SECONDS


async def fetch_text(
    url: str,
    max_chars: int = MAX_CHARS_PER_URL,
    force_update: bool = False,
    rate_limiter: RateLimiter = _rate_limiter
) -> Tuple[str, int]:
    """
    Fetcht Text-Inhalt von einer URL mit Caching und Rate Limiting.

    Args:
        url: Die zu fetchende URL
        max_chars: Maximale Anzahl Zeichen die zurückgegeben werden
        force_update: Cache ignorieren und neu fetchen
        rate_limiter: RateLimiter Instanz (Default: globaler Limiter)

    Returns:
        Tuple[str, int]: (Text-Inhalt, Länge des Textes)

    Raises:
        httpx.HTTPError: Bei HTTP-Fehlern
        Exception: Bei anderen Fehlern (z.B. Timeout, Parsing)
    """
    cache_file = url_to_cache_file(url)
    use_cache = cache_file.exists() and not force_update

    # Cache-Validierung (TTL-Check)
    if use_cache:
        age = time.time() - cache_file.stat().st_mtime
        if age > get_cache_ttl():
            use_cache = False
            logger.debug(f"Cache expired for {url} (age: {age/3600:.1f}h)")

    # Cache-Hit
    if use_cache:
        text = cache_file.read_text(encoding="utf-8")
        logger.info(f"[CACHE] {url} -> {len(text)} chars")
        return text[:max_chars], len(text)

    # Rate Limiting Check
    if not rate_limiter.is_allowed(url):
        logger.warning(f"[RATE_LIMIT] {url} - waiting...")
        # Warte bis Rate Limit Window abgelaufen ist
        await asyncio.sleep(5)
        if not rate_limiter.is_allowed(url):
            raise Exception(f"Rate limit exceeded for {urlparse(url).netloc}")

    # Fetch von URL
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "KIFF-AI-WebContext/1.0"},
                follow_redirects=True
            )
            response.raise_for_status()
            html = response.text

        # Rate Limit Request registrieren
        rate_limiter.record_request(url)

        # HTML zu Text konvertieren
        parser = TextExtractor()
        parser.feed(html)
        text = parser.text()[:max_chars]

        # In Cache speichern
        cache_file.write_text(text, encoding="utf-8")
        logger.info(f"[FETCH] {url} -> {len(text)} chars")

        return text[:max_chars], len(text)

    except httpx.HTTPError as e:
        logger.error(f"[HTTP_ERROR] {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"[ERROR] {url}: {e}")
        raise


async def clear_cache():
    """Löscht alle Cache-Dateien"""
    count = 0
    for file in CACHE_DIR.glob("*.txt"):
        file.unlink()
        count += 1
    logger.info(f"Cleared {count} cache files")
    return count


async def get_cache_stats() -> Dict:
    """
    Gibt Cache-Statistiken zurück

    Returns:
        Dict mit: file_count, total_size_bytes, oldest_file_age_hours, newest_file_age_hours
    """
    files = list(CACHE_DIR.glob("*.txt"))
    if not files:
        return {
            "file_count": 0,
            "total_size_bytes": 0,
            "oldest_file_age_hours": None,
            "newest_file_age_hours": None
        }

    total_size = sum(f.stat().st_size for f in files)
    now = time.time()
    ages = [(now - f.stat().st_mtime) / 3600 for f in files]  # in Stunden

    return {
        "file_count": len(files),
        "total_size_bytes": total_size,
        "oldest_file_age_hours": max(ages),
        "newest_file_age_hours": min(ages)
    }


# Import asyncio hier am Ende um zirkuläre Imports zu vermeiden
import asyncio
