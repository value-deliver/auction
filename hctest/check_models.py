#!/usr/bin/env python3
"""
Check available Gemini models for your API key.

This script helps you identify which Gemini models are available for your API key.
Run this first to see what models you can use before running the main AgentV test.
"""

import os
import sys
from pathlib import Path

# Change to script directory to ensure .env file is found
script_dir = Path(__file__).parent
os.chdir(script_dir)

try:
    import google.generativeai as genai
    from hcaptcha_challenger import AgentConfig
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure hcaptcha-challenger is installed")
    sys.exit(1)


def check_available_models():
    """Check which Gemini models are available for your API key."""

    print("Checking available Gemini models...")
    print("=" * 50)

    # Get API key from AgentConfig (loads from .env)
    try:
        temp_config = AgentConfig()
        api_key = temp_config.GEMINI_API_KEY.get_secret_value()
        if not api_key:
            raise ValueError("API key is empty")
        print("✓ API key loaded successfully")
    except Exception as e:
        print("✗ ERROR: GEMINI_API_KEY not found!")
        print("   Please get an API key from: https://aistudio.google.com/apikey")
        print("   Then set GEMINI_API_KEY in your .env file")
        print(f"   Error details: {e}")
        return

    # Configure the API
    genai.configure(api_key=api_key)

    try:
        # List available models
        models = genai.list_models()
        print(f"\n📋 Found {len(models)} models total")

        # Filter for Gemini models that support generateContent
        gemini_models = []
        for model in models:
            if 'gemini' in model.name.lower() and 'generateContent' in model.supported_generation_methods:
                gemini_models.append(model)

        print(f"🎯 Found {len(gemini_models)} Gemini models that support content generation:")
        print()

        for model in gemini_models:
            print(f"  • {model.name}")
            print(f"    Description: {model.description}")
            print(f"    Methods: {model.supported_generation_methods}")
            print()

        # Suggest the best models for AgentV
        print("💡 Recommended models for AgentV:")
        recommended = []

        for model in gemini_models:
            if '1.5' in model.name:
                if 'flash' in model.name.lower():
                    recommended.append((model.name, "Fast and cost-effective"))
                elif 'pro' in model.name.lower():
                    recommended.append((model.name, "More accurate but slower"))

        if recommended:
            for model_name, description in recommended:
                print(f"  ✓ {model_name} - {description}")
        else:
            print("  No 1.5 models found, using available models:")
            for model in gemini_models[:3]:  # Show first 3
                print(f"  ✓ {model.name}")

        return gemini_models

    except Exception as e:
        print(f"✗ Error checking models: {e}")
        print("\nPossible issues:")
        print("• API key may not have proper permissions")
        print("• API key may be invalid or expired")
        print("• Network connectivity issues")
        print("• Regional restrictions on the API")
        return []


if __name__ == "__main__":
    models = check_available_models()

    if models:
        print("\n🚀 Next steps:")
        print("1. Update agentv_test.py with working model names")
        print("2. Run: python agentv_test.py")
    else:
        print("\n❌ No working models found. Please check your API key and permissions.")