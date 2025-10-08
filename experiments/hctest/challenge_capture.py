#!/usr/bin/env python3
"""
Challenge Capture Utility for hCaptcha Testing

This script captures real hCaptcha challenges from websites and saves them
as test data for validating the captcha service implementation.
"""

import asyncio
import json
import logging
import os
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page, Browser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Change to script directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

# Load environment variables
load_dotenv()


class ChallengeCapture:
    """Utility for capturing hCaptcha challenges for testing."""

    def __init__(self, output_dir: str = "captured_challenges"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.captured_challenges: List[Dict[str, Any]] = []

    async def wait_for_hcaptcha(self, page: Page, timeout: int = 30000) -> bool:
        """Wait for hCaptcha challenge to appear using multiple detection strategies."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) * 1000 < timeout:
            try:
                # Strategy 1: Check for hCaptcha iframe by src
                iframe_count = await page.locator('iframe[src*="hcaptcha.com"]').count()
                if iframe_count > 0:
                    logger.info(f"hCaptcha iframe detected (src pattern): {iframe_count} iframes")
                    return True

                # Strategy 2: Check for hCaptcha iframe by class or other attributes
                hcaptcha_iframes = await page.locator('iframe').all()
                for iframe in hcaptcha_iframes:
                    try:
                        src = await iframe.get_attribute('src') or ""
                        if 'hcaptcha' in src.lower():
                            logger.info("hCaptcha iframe detected (src content)")
                            return True
                    except:
                        continue

                # Strategy 3: Check for hCaptcha div containers
                hcaptcha_divs = [
                    'div[class*="hcaptcha"]',
                    'div[id*="hcaptcha"]',
                    'div[data-sitekey]',
                    '.h-captcha'
                ]

                for selector in hcaptcha_divs:
                    try:
                        element = page.locator(selector).first
                        if await element.is_visible():
                            logger.info(f"hCaptcha container detected: {selector}")
                            return True
                    except:
                        continue

                # Strategy 4: Check for hCaptcha script tags
                scripts = await page.locator('script[src*="hcaptcha"]').all()
                if scripts:
                    logger.info(f"hCaptcha scripts detected: {len(scripts)}")
                    return True

                # Strategy 5: Check page content for hCaptcha indicators
                content = await page.content()
                if 'hcaptcha' in content.lower():
                    logger.info("hCaptcha content detected in page")
                    return True

                # Wait a bit before checking again
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.debug(f"Detection check failed: {e}")
                await asyncio.sleep(0.5)

        logger.warning(f"No hCaptcha detected within {timeout}ms timeout")
        return False

    async def capture_challenge_data(self, page: Page) -> Optional[Dict[str, Any]]:
        """Capture hCaptcha challenge data from the page."""
        try:
            # Find hCaptcha iframe using multiple strategies
            iframe_element = None

            # Strategy 1: Direct src pattern
            try:
                iframe_element = page.locator('iframe[src*="hcaptcha.com"]').first
                if not await iframe_element.is_visible():
                    iframe_element = None
            except:
                iframe_element = None

            # Strategy 2: Check all iframes for hCaptcha content
            if not iframe_element:
                all_iframes = await page.locator('iframe').all()
                for iframe in all_iframes:
                    try:
                        src = await iframe.get_attribute('src') or ""
                        if 'hcaptcha' in src.lower() and await iframe.is_visible():
                            iframe_element = iframe
                            break
                    except:
                        continue

            if not iframe_element:
                logger.warning("No suitable hCaptcha iframe found")
                return None

            # Get iframe content
            frame = await iframe_element.content_frame()
            if not frame:
                logger.warning("Could not access iframe content")
                return None

            # Extract challenge type and prompt
            challenge_type = "unknown"
            prompt = ""

            # Try to detect challenge type from DOM elements
            try:
                # Check for different challenge types
                if await frame.locator('.challenge-type').is_visible():
                    challenge_type_element = frame.locator('.challenge-type').first
                    challenge_type = await challenge_type_element.get_attribute('data-type') or "unknown"

                # Get prompt text
                prompt_selectors = [
                    '.prompt-text',
                    '.challenge-prompt',
                    '[data-prompt]',
                    '.task-text'
                ]

                for selector in prompt_selectors:
                    try:
                        prompt_element = frame.locator(selector).first
                        if await prompt_element.is_visible():
                            prompt = await prompt_element.text_content()
                            break
                    except:
                        continue

            except Exception as e:
                logger.warning(f"Could not extract challenge metadata: {e}")

            # Capture screenshot of the challenge
            screenshot_bytes = await frame.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

            challenge_data = {
                "timestamp": datetime.now().isoformat(),
                "challenge_type": challenge_type,
                "prompt": prompt.strip(),
                "image_base64": screenshot_b64,
                "url": page.url,
                "user_agent": await page.evaluate("navigator.userAgent")
            }

            logger.info(f"Captured challenge: {challenge_type} - '{prompt[:50]}...'")
            return challenge_data

        except Exception as e:
            logger.error(f"Failed to capture challenge data: {e}")
            return None

    async def save_challenge(self, challenge_data: Dict[str, Any]) -> str:
        """Save captured challenge to file."""
        timestamp = datetime.fromisoformat(challenge_data["timestamp"])
        filename = f"challenge_{timestamp.strftime('%Y%m%d_%H%M%S')}_{challenge_data['challenge_type']}.json"

        filepath = self.output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(challenge_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved challenge to: {filepath}")
        return str(filepath)

    async def capture_from_url(self, url: str, wait_time: int = 5000) -> Optional[str]:
        """Capture hCaptcha challenge from a specific URL."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = await context.new_page()

            try:
                logger.info(f"Navigating to: {url}")
                await page.goto(url, wait_until='domcontentloaded')

                # Wait for page to load
                await page.wait_for_timeout(wait_time)

                # Check for hCaptcha
                if await self.wait_for_hcaptcha(page):
                    challenge_data = await self.capture_challenge_data(page)
                    if challenge_data:
                        filepath = await self.save_challenge(challenge_data)
                        return filepath
                    else:
                        logger.warning("Failed to capture challenge data")
                else:
                    logger.info("No hCaptcha found on page")

            except Exception as e:
                logger.error(f"Error capturing from URL: {e}")

            finally:
                await browser.close()

        return None

    async def capture_multiple_challenges(self, urls: List[str], delay_between: int = 3000) -> List[str]:
        """Capture challenges from multiple URLs."""
        captured_files = []

        for i, url in enumerate(urls):
            logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
            filepath = await self.capture_from_url(url)
            if filepath:
                captured_files.append(filepath)

            if i < len(urls) - 1:  # Don't delay after last URL
                await asyncio.sleep(delay_between / 1000)

        return captured_files


async def main():
    """Main capture function."""
    import argparse

    parser = argparse.ArgumentParser(description="Capture hCaptcha challenges for testing")
    parser.add_argument("--url", help="Single URL to capture from")
    parser.add_argument("--urls-file", help="File containing URLs (one per line)")
    parser.add_argument("--output-dir", default="captured_challenges", help="Output directory")
    parser.add_argument("--wait-time", type=int, default=5000, help="Wait time after page load (ms)")

    args = parser.parse_args()

    capture = ChallengeCapture(args.output_dir)

    if args.url:
        logger.info("Starting single URL capture...")
        result = await capture.capture_from_url(args.url, args.wait_time)
        if result:
            logger.info(f"✅ Challenge captured: {result}")
        else:
            logger.warning("❌ No challenge captured")

    elif args.urls_file:
        logger.info(f"Starting batch capture from {args.urls_file}...")
        try:
            with open(args.urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]

            results = await capture.capture_multiple_challenges(urls)
            logger.info(f"✅ Captured {len(results)} challenges")

        except FileNotFoundError:
            logger.error(f"URLs file not found: {args.urls_file}")

    else:
        logger.info("No URL specified. Use --url or --urls-file")
        logger.info("Example: python challenge_capture.py --url 'https://example.com'")


if __name__ == "__main__":
    asyncio.run(main())