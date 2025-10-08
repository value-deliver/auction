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

    async def detect_captcha_in_frame(self, frame: Page, depth: int = 0) -> Optional[Page]:
        """Recursively detect CAPTCHA in a frame and its child frames, returning the frame containing CAPTCHA"""
        try:
            # Check for CAPTCHA iframes in this frame
            captcha_selectors = [
                "iframe[src*='hcaptcha.com']",
                "iframe[src*='newassets.hcaptcha.com']",
            ]

            for selector in captcha_selectors:
                try:
                    elements = frame.locator(selector)
                    count = await elements.count()
                    if count > 0:
                        logger.info(f"Found {count} CAPTCHA iframes with selector: {selector}")
                        return frame
                except Exception:
                    continue

            # Check for iframes in this frame
            iframes = frame.locator('iframe')
            iframe_count = await iframes.count()
            if iframe_count > 0:
                logger.debug(f"Found {iframe_count} iframes in frame at depth {depth}")

            for i in range(iframe_count):
                try:
                    iframe = iframes.nth(i)
                    # Recursively check child frames
                    try:
                        element = await iframe.element_handle()
                        child_frame = await element.content_frame()
                    except Exception as e:
                        logger.debug(f"Error getting content frame for iframe {i}: {e}")
                        continue
                    if child_frame:
                        # Recurse into child frame
                        result = await self.detect_captcha_in_frame(child_frame, depth + 1)
                        if result:
                            return result

                except Exception as e:
                    logger.debug(f"Error checking iframe {i}: {e}")

            return None

        except Exception as e:
            logger.error(f"Error in frame detection: {e}")
            return None

    async def wait_for_hcaptcha(self, page: Page, timeout: int = 30000) -> bool:
        """Wait for hCaptcha challenge to appear using recursive frame detection."""
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) * 1000 < timeout:
            try:
                # Use the same detection logic as production integration
                captcha_frame = await self.detect_captcha_in_frame(page, 0)
                if captcha_frame:
                    logger.info("hCaptcha detected using recursive frame detection")
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
            # Find hCaptcha iframe
            iframe_element = page.locator('iframe[src*="hcaptcha.com"]').first
            if not await iframe_element.is_visible():
                return None

            # Get iframe content
            frame = await iframe_element.content_frame()
            if not frame:
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

    async def capture_from_url(self, url: str, wait_time: int = 5000, trigger_login: bool = False) -> Optional[str]:
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

                # If login triggering is enabled, try to perform login actions
                if trigger_login:
                    await self._trigger_login_flow(page)

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

    async def _trigger_login_flow(self, page):
        """Attempt to trigger hCaptcha by performing login actions."""
        try:
            logger.info("Attempting to trigger hCaptcha via login flow...")

            # Common login form selectors
            login_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[type="text"]',
                '#email',
                '#username'
            ]

            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                '#password'
            ]

            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
                '.login-btn',
                '#login-button'
            ]

            # Try to find and fill email/username field
            email_field = None
            for selector in login_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible():
                        email_field = field
                        logger.info(f"Found email field: {selector}")
                        break
                except:
                    continue

            # Try to find password field
            password_field = None
            for selector in password_selectors:
                try:
                    field = page.locator(selector).first
                    if await field.is_visible():
                        password_field = field
                        logger.info(f"Found password field: {selector}")
                        break
                except:
                    continue

            # Try to find submit button
            submit_button = None
            for selector in submit_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible():
                        submit_button = button
                        logger.info(f"Found submit button: {selector}")
                        break
                except:
                    continue

            # If we found the form elements, fill them with dummy data and submit
            if email_field and password_field and submit_button:
                logger.info("Filling login form with dummy credentials...")

                # Fill with dummy credentials that will likely fail but trigger hCaptcha
                await email_field.fill("test@example.com")
                await password_field.fill("dummy_password_123")

                # Click submit to trigger hCaptcha
                await submit_button.click()
                logger.info("Clicked submit button - waiting for hCaptcha...")

                # Wait a bit for hCaptcha to appear
                await page.wait_for_timeout(3000)

            else:
                logger.warning("Could not find complete login form - trying alternative triggers")

                # Alternative: look for any buttons that might trigger hCaptcha
                alt_buttons = page.locator('button, input[type="submit"], a[href*="login"], a[href*="signin"]')
                count = await alt_buttons.count()

                for i in range(min(count, 3)):  # Try first 3 buttons
                    try:
                        button = alt_buttons.nth(i)
                        if await button.is_visible():
                            button_text = await button.text_content()
                            logger.info(f"Trying to click button: '{button_text[:30]}...'")
                            await button.click()
                            await page.wait_for_timeout(2000)
                            break
                    except Exception as e:
                        logger.debug(f"Button click failed: {e}")
                        continue

        except Exception as e:
            logger.warning(f"Login flow triggering failed: {e}")

    async def capture_multiple_challenges(self, urls: List[str], delay_between: int = 3000, trigger_login: bool = False) -> List[str]:
        """Capture challenges from multiple URLs."""
        captured_files = []

        for i, url in enumerate(urls):
            logger.info(f"Processing URL {i+1}/{len(urls)}: {url}")
            filepath = await self.capture_from_url(url, trigger_login=trigger_login)
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
    parser.add_argument("--trigger-login", action="store_true", help="Attempt to trigger hCaptcha by performing login actions")

    args = parser.parse_args()

    capture = ChallengeCapture(args.output_dir)

    if args.url:
        logger.info("Starting single URL capture...")
        result = await capture.capture_from_url(args.url, args.wait_time, args.trigger_login)
        if result:
            logger.info(f"✅ Challenge captured: {result}")
        else:
            logger.warning("❌ No challenge captured")

    elif args.urls_file:
        logger.info(f"Starting batch capture from {args.urls_file}...")
        try:
            with open(args.urls_file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]

            results = await capture.capture_multiple_challenges(urls, trigger_login=args.trigger_login)
            logger.info(f"✅ Captured {len(results)} challenges")

        except FileNotFoundError:
            logger.error(f"URLs file not found: {args.urls_file}")

    else:
        logger.info("No URL specified. Use --url or --urls-file")
        logger.info("Example: python challenge_capture.py --url 'https://example.com'")


if __name__ == "__main__":
    asyncio.run(main())