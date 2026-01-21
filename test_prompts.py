"""Test ob externe Prompt-Dateien korrekt geladen werden"""
import os
import json

# Pfade
config_path = "config/profiles_kiff.json"
prompts_dir = "config/prompts"

# Profile laden
with open(config_path, "r", encoding="utf-8") as f:
    profiles = json.load(f)

print("=== Profile Config ===")
print(f"Geladene Profile: {list(profiles.keys())}\n")

# Prüfe externe Prompt-Dateien
for profile_name in profiles.keys():
    prompt_file = os.path.join(prompts_dir, f"{profile_name}.md")
    if os.path.exists(prompt_file):
        with open(prompt_file, "r", encoding="utf-8") as pf:
            content = pf.read()
        print(f"✓ {profile_name}: Externe Datei gefunden")
        print(f"  Datei: {prompt_file}")
        print(f"  Länge: {len(content)} Zeichen")
        print(f"  Start: {content[:80]}...")
        print()
    else:
        print(f"✗ {profile_name}: Keine externe Datei")
        print(f"  Erwartet: {prompt_file}")
        print(f"  Verwendet JSON system_prompt (Länge: {len(profiles[profile_name].get('system_prompt', ''))})")
        print()
