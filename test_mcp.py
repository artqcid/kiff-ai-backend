"""
Test-Skript für KIFF MCP Integration

Testet Context Fetching ohne kompletten Server-Start
"""

import asyncio
import sys
from pathlib import Path

# Füge Backend zum Python Path hinzu
sys.path.insert(0, str(Path(__file__).parent))

from core.context_manager import ContextManager
from core.web_context_service import get_cache_stats


async def test_context_fetching():
    """Testet das Fetchen von Web-Contexts"""
    
    print("=" * 60)
    print("KIFF MCP Context Fetching Test")
    print("=" * 60)
    
    # Initialize Context Manager
    print("\n1. Initialisiere Context Manager...")
    cm = ContextManager()
    available_sets = cm.get_available_sets()
    print(f"   ✓ {len(available_sets)} Context-Sets geladen")
    print(f"   Sets: {', '.join(available_sets[:5])}...")
    
    # Test Prompt Parsing
    print("\n2. Teste @tag Parsing...")
    test_prompt = "Ich brauche Infos über @gastronomie und @bar für ein neues Konzept."
    found_sets = cm.parse_prompt_for_sets(test_prompt)
    print(f"   Prompt: {test_prompt}")
    print(f"   ✓ Gefundene @tags: {found_sets}")
    
    # Resolve URLs
    print("\n3. Resolve URLs für gefundene Sets...")
    for set_name in found_sets:
        urls = cm.resolve_set(set_name if not set_name.startswith("@") else set_name[1:])
        print(f"   {set_name}: {len(urls)} URLs")
        for url in urls[:2]:
            print(f"      - {url}")
    
    # Fetch Contexts (nur erste URL für Test)
    print("\n4. Fetche Contexts (nur erste 2 URLs für Test)...")
    print("   ⚠️  Dies kann einige Sekunden dauern...")
    
    try:
        # Teste nur @bar (kleineres Set)
        test_urls = cm.resolve_set("bar")[:2]
        
        for url in test_urls:
            try:
                from core.web_context_service import fetch_text
                text, length = await fetch_text(url, max_chars=500)  # Nur 500 chars für Test
                print(f"   ✓ {url}")
                print(f"     Länge: {length} chars, Preview: {text[:100]}...")
            except Exception as e:
                print(f"   ✗ {url}: {e}")
        
    except Exception as e:
        print(f"   Fehler beim Fetchen: {e}")
    
    # Cache Stats
    print("\n5. Cache-Statistiken...")
    try:
        stats = await get_cache_stats()
        print(f"   Dateien: {stats['file_count']}")
        print(f"   Größe: {stats['total_size_bytes'] / 1024:.1f} KB")
        if stats['newest_file_age_hours'] is not None:
            print(f"   Neueste: {stats['newest_file_age_hours']:.1f}h alt")
    except Exception as e:
        print(f"   Cache-Stats nicht verfügbar: {e}")
    
    print("\n" + "=" * 60)
    print("Test abgeschlossen!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_context_fetching())
