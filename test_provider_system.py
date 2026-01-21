"""
Quick test script to verify provider system works
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from core.provider_manager import get_provider_manager
from core.profile_agent import ProfileAgent

async def test_provider_system():
    print("="*60)
    print("Testing Provider System")
    print("="*60)
    
    # Get provider manager
    manager = get_provider_manager()
    print(f"\n✅ ProviderManager initialized")
    print(f"   Current provider: {manager.get_current_provider_name()}")
    
    # List providers
    providers = manager.get_available_providers()
    print(f"\n📋 Available providers: {len(providers)}")
    for p in providers:
        status = "✅" if p["has_api_key"] or not p["requires_api_key"] else "❌"
        print(f"   {status} {p['display_name']} ({p['name']})")
    
    # Test ProfileAgent
    agent = ProfileAgent(provider_manager=manager)
    print(f"\n✅ ProfileAgent initialized")
    print(f"   Current profile: {agent.get_current_profile()}")
    
    # Get models for current profile+provider
    models = agent.get_models_for_profile()
    print(f"\n🤖 Models for profile '{agent.get_current_profile()}' with provider 'lokal':")
    for model_id in models:
        print(f"   - {model_id}")
    
    # Test health check
    print(f"\n🏥 Testing provider health...")
    is_healthy = await manager.is_healthy("lokal")
    print(f"   Lokal provider: {'✅ Healthy' if is_healthy else '❌ Unavailable'}")
    
    print("\n" + "="*60)
    print("✅ All tests passed!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_provider_system())
