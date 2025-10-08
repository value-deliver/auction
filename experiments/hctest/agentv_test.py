#!/usr/bin/env python3
"""
AgentV Test Script - Demonstrates how to use AgentV to solve hCaptcha challenges

This script shows the basic usage pattern for AgentV, the AI-powered hCaptcha solver.
Make sure to set your GEMINI_API_KEY environment variable before running.

Usage:
    export GEMINI_API_KEY=your_api_key_here
    python agentv_test.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page

from hcaptcha_challenger import AgentV, AgentConfig, CaptchaResponse
from hcaptcha_challenger.utils import SiteKey

# Change to script directory to ensure .env file is found
script_dir = Path(__file__).parent
os.chdir(script_dir)


async def solve_hcaptcha(page: Page) -> AgentV:
    """
    Automates the process of solving an hCaptcha challenge.

    Args:
        page: Playwright Page object where hCaptcha is located

    Returns:
        AgentV instance with challenge results
    """
    print("Initializing AgentV...")

    # Create agent configuration
    # You can customize these settings based on your needs
    agent_config = AgentConfig(
        # Disable bezier trajectories if using Camoufox
        DISABLE_BEZIER_TRAJECTORY=False,

        # Timeouts (in seconds)
        EXECUTION_TIMEOUT=120,
        RESPONSE_TIMEOUT=30,

        # Retry on failure
        RETRY_ON_FAILURE=True,

        # Model configurations (using Gemini 2.5 Flash for speed/cost balance)
        IMAGE_CLASSIFIER_MODEL="gemini-2.5-flash",
        SPATIAL_POINT_REASONER_MODEL="gemini-2.5-flash",
        SPATIAL_PATH_REASONER_MODEL="gemini-2.5-flash",

        # Thinking budgets (token limits for AI reasoning)
        IMAGE_CLASSIFIER_THINKING_BUDGET=970,    # For binary classification
        SPATIAL_POINT_THINKING_BUDGET=1387,      # For point selection
        SPATIAL_PATH_THINKING_BUDGET=-1,         # -1 = automatic for drag-drop
    )

    # Initialize AgentV with the page and configuration
    agent = AgentV(page=page, agent_config=agent_config)

    print("AgentV initialized successfully")

    # Click the hCaptcha checkbox to trigger the challenge
    print("Clicking hCaptcha checkbox...")
    await agent.robotic_arm.click_checkbox()

    # Wait for the challenge to appear and solve it automatically
    print("Solving challenge...")
    challenge_result = await agent.wait_for_challenge()

    return agent


async def main():
    """
    Main function demonstrating AgentV usage with different test scenarios.
    """
    print("Starting AgentV Test Script")
    print("=" * 50)

    # Check for API key by creating a temporary AgentConfig (it loads .env automatically)
    try:
        temp_config = AgentConfig()
        # This will raise an error if GEMINI_API_KEY is not set
        api_key = temp_config.GEMINI_API_KEY.get_secret_value()
        if not api_key:
            raise ValueError("API key is empty")
        print("GEMINI_API_KEY found")
    except Exception as e:
        print("ERROR: GEMINI_API_KEY not found!")
        print("   Please get an API key from: https://aistudio.google.com/apikey")
        print("   Then set GEMINI_API_KEY in your .env file or environment variables")
        print(f"   Error details: {e}")
        return

    # Launch browser with Playwright
    async with async_playwright() as p:
        print("Launching browser...")

        # Launch browser (set headless=False to see the process)
        browser = await p.chromium.launch(
            headless=False,  # Set to True for headless mode
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu"
            ]
        )

        # Create a new context and page
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        try:
            # Navigate to a test page with hCaptcha
            print("Navigating to hCaptcha test page...")

            # Choose your test URL - uncomment one of these options:
            test_url = SiteKey.as_site_link("dd6e16a7-972e-47d2-93d0-96642fb6d8de")
            # test_url = SiteKey.as_site_link(SiteKey.user_easy)      # Easy challenges
            # test_url = SiteKey.as_site_link(SiteKey.user_moderate) # Moderate challenges
            # test_url = SiteKey.as_site_link(SiteKey.user_difficult) # Difficult challenges
            # test_url = SiteKey.as_site_link(SiteKey.discord)       # Discord-style challenges
            # test_url = SiteKey.as_site_link(SiteKey.epic)          # Epic Games-style challenges
            # test_url = SiteKey.as_site_link(SiteKey.hcaptcha)      # Standard hCaptcha demo
            # test_url = SiteKey.choice()                            # Random challenge type

            await page.goto(test_url)
            print(f"Loaded test page: {test_url}")

            # Wait for page to load (with timeout handling)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)  # 10 second timeout
                print("Page loaded successfully")
            except Exception as e:
                print(f"Page load timeout (continuing anyway): {e}")

            await asyncio.sleep(2)

            # Solve the hCaptcha
            print("\nStarting hCaptcha solving process...")
            agent = await solve_hcaptcha(page)

            # Check results
            if agent.cr_list:
                print("hCaptcha solved successfully!")
                print(f"Found {len(agent.cr_list)} challenge response(s)")

                # Display the latest challenge response
                latest_cr: CaptchaResponse = agent.cr_list[-1]
                print("\nChallenge Response Details:")
                print(json.dumps(latest_cr.model_dump(by_alias=True), indent=2, ensure_ascii=False))

                # Check if the challenge passed
                if latest_cr.is_pass:
                    print("SUCCESS: Challenge passed!")
                else:
                    print("FAILED: Challenge not passed")
            else:
                print("No challenge responses found - challenge may have failed")

        except Exception as e:
            print(f"Error during execution: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Clean up
            await context.close()
            await browser.close()
            print("\nBrowser closed")


async def demo_custom_config():
    """
    Demo showing how to use custom AgentConfig settings.
    """
    print("\n🔧 Demo: Custom AgentConfig")

    # Example of custom configuration
    custom_config = AgentConfig(
        # Use different models for different challenge types
        IMAGE_CLASSIFIER_MODEL="gemini-2.5-pro",  # More accurate but slower
        SPATIAL_POINT_REASONER_MODEL="gemini-2.5-flash",  # Faster for point selection
        SPATIAL_PATH_REASONER_MODEL="gemini-2.5-pro",  # More accurate for drag-drop

        # Custom timeouts
        EXECUTION_TIMEOUT=180,  # 3 minutes for complex challenges
        RESPONSE_TIMEOUT=60,   # 1 minute for responses

        # Custom cache directories
        cache_dir=Path("./my_cache"),
        challenge_dir=Path("./my_challenges"),

        # Disable specific challenge types if needed
        ignore_request_types=[],  # Add challenge types to ignore
        ignore_request_questions=[],  # Add specific questions to ignore

        # Enable debug mode for detailed logging
        enable_challenger_debug=True,
    )

    print("Custom config created with:")
    print(f"  - Image classifier: {custom_config.IMAGE_CLASSIFIER_MODEL}")
    print(f"  - Execution timeout: {custom_config.EXECUTION_TIMEOUT}s")
    print(f"  - Debug mode: {custom_config.enable_challenger_debug}")


if __name__ == "__main__":
    # Run the main demo
    asyncio.run(main())

    # Optionally run the custom config demo
    # asyncio.run(demo_custom_config())