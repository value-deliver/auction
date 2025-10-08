#!/usr/bin/env python3
"""
Production Integration Library - Reusable components for AgentV integration

This module provides production-ready classes for integrating AgentV into website automation
for handling hCaptcha challenges.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from hcaptcha_challenger import AgentV, AgentConfig

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Change to script directory to ensure .env file is found
script_dir = Path(__file__).parent
os.chdir(script_dir)


class HcaptchaSolver:
    """Production-ready hCaptcha solver integration."""

    def __init__(self):
        """Initialize with production-ready configuration."""
        self.agent_config = AgentConfig(
            # API key loaded from environment/.env
            EXECUTION_TIMEOUT=120,    # 2 minutes for complex challenges
            RESPONSE_TIMEOUT=30,      # 30 seconds for API responses
            RETRY_ON_FAILURE=True,    # Auto-retry failed challenges

            # Optimized model selection
            IMAGE_CLASSIFIER_MODEL="gemini-2.5-flash",      # Fast binary classification
            SPATIAL_POINT_REASONER_MODEL="gemini-2.5-flash", # Fast point selection
            SPATIAL_PATH_REASONER_MODEL="gemini-2.5-pro",    # Accurate drag-drop

            # Production settings
            enable_challenger_debug=False,  # Disable debug logging in production
        )

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

    async def solve_hcaptcha_if_present(self, page: Page) -> bool:
        """
        Check for and solve hCaptcha challenges on a page.

        Args:
            page: Playwright page object

        Returns:
            bool: True if hCaptcha was solved successfully or no hCaptcha found
        """
        try:
            # Use custom detection for initial CAPTCHA check
            captcha_frame = await self.detect_captcha_in_frame(page, 0)
            if captcha_frame:
                logger.info("hCaptcha detected, initializing solver...")

                # Manually click the checkbox
                frame_locator = captcha_frame.frame_locator("iframe[title='Widget containing checkbox for hCaptcha security challenge']")
                checkbox = frame_locator.locator("#checkbox")
                await checkbox.click()
                logger.info("Clicked checkbox")

                # Initialize AgentV and solve the challenge
                agent = AgentV(page=page, agent_config=self.agent_config)

                # Wait for and solve challenge
                await agent.wait_for_challenge()

                # Check result
                if agent.cr_list:
                    latest_result = agent.cr_list[-1]
                    success = latest_result.is_pass
                    logger.info(f"hCaptcha result: {'SOLVED' if success else 'FAILED'}")
                    return success
                else:
                    logger.warning("No hCaptcha response received")
                    return False
            else:
                # No hCaptcha found, continue normally
                return True

        except Exception as e:
            logger.error(f"hCaptcha solving error: {e}")
            return False

    async def wait_for_hcaptcha_and_solve(self, page: Page, timeout: int = 30) -> bool:
        """
        Wait for hCaptcha to appear and then solve it.

        Args:
            page: Playwright page object
            timeout: Seconds to wait for hCaptcha to appear

        Returns:
            bool: True if solved successfully
        """
        try:
            # Wait for hCaptcha to appear
            await page.wait_for_selector("iframe[src*='hcaptcha.com']", timeout=timeout*1000)
            logger.info("hCaptcha appeared, solving...")

            # Solve it
            return await self.solve_hcaptcha_if_present(page)

        except Exception as e:
            logger.error(f"Timeout waiting for hCaptcha: {e}")
            return False


class WebsiteAutomationBot:
    """Example bot showing how to integrate hCaptcha solving into website automation."""

    def __init__(self):
        self.hcaptcha_solver = HcaptchaSolver()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.state_file = "browser_state.json"

    async def setup_browser(self, headless: bool = False, browser_args: Optional[List[str]] = None):
        """Setup browser with anti-detection measures."""
        if browser_args is None:
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-web-security",  # May help with some sites
                "--disable-features=VizDisplayCompositor",
                "--disable-blink-features=AutomationControlled",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-extensions",
                "--disable-default-apps"
            ]

        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )

        if os.path.exists(self.state_file):
            logger.info(f"Loading saved session from {self.state_file}")
            self.context = await self.browser.new_context(
                storage_state=self.state_file,
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )

        return playwright

    async def login_with_hcaptcha_handling(
        self,
        url: str,
        username: str,
        password: str,
        selectors: Optional[Dict[str, str]] = None,
        close_page: bool = True
    ) -> Tuple[bool, Optional[Page]]:
        """
        Login to a website with automatic hCaptcha handling.

        Args:
            url: Login page URL
            username: Username/email
            password: Password
            selectors: Dict of selectors for form elements (email, password, submit)

        Returns:
            Tuple[bool, Optional[Page]]: (success, page) - page is returned if close_page=False
        """
        if selectors is None:
            selectors = {
                "email": 'input[name="Input.Email"]',
                "password": 'input[name="Input.Password"]',
                "submit": 'button[type="submit"]'
            }

        if not self.context:
            await self.setup_browser()

        page = await self.context.new_page()

        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Fill login form
            await page.fill(selectors["email"], username)
            await page.fill(selectors["password"], password)

            # Click login button
            await page.click(selectors["submit"])

            await page.wait_for_timeout(3000)
            # Handle any hCaptcha that appears
            hcaptcha_success = await self.hcaptcha_solver.solve_hcaptcha_if_present(page)

            if hcaptcha_success:
                # Wait a bit for login to complete
                await page.wait_for_timeout(3000)

                # Check if login was successful based on session cookies
                cookies = await page.context.cookies()
                session_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'auth' in c['name'].lower()]
                login_successful = len(session_cookies) > 0
                if login_successful:
                    logger.info(f"Login successful - found {len(session_cookies)} session/auth cookies: {[c['name'] for c in session_cookies]}")
                else:
                    logger.warning("Login may have failed - no session/auth cookies found")

                if login_successful:
                    logger.info("Login successful!")
                    # Save session state for future use
                    await self.context.storage_state(path=self.state_file)
                    logger.info(f"Session state saved to {self.state_file}")
                    return True, page if not close_page else None
                else:
                    logger.warning("Login may have failed - check page content")
                    return False, page if not close_page else None
            else:
                logger.error("Failed to solve hCaptcha")
                return False, page if not close_page else None

        except Exception as e:
            logger.error(f"Login automation error: {e}")
            return False, page if not close_page else None

        finally:
            if close_page:
                await page.close()

    async def automate_form_submission(self, url: str, form_data: Dict[str, str], submit_selector: str = "#submit, [type='submit'], .submit-btn") -> bool:
        """
        Generic form submission with hCaptcha handling.

        Args:
            url: Form page URL
            form_data: Dictionary of field selectors to values
                        e.g., {"#name": "John", "#email": "john@example.com"}
            submit_selector: Selector for submit button

        Returns:
            bool: True if form submitted successfully
        """
        if not self.context:
            await self.setup_browser()

        page = await self.context.new_page()

        try:
            await page.goto(url, wait_until="networkidle")

            # Fill form fields
            for selector, value in form_data.items():
                await page.fill(selector, value)

            # Submit form
            await page.click(submit_selector)

            # Handle hCaptcha
            return await self.hcaptcha_solver.solve_hcaptcha_if_present(page)

        except Exception as e:
            logger.error(f"Form submission error: {e}")
            return False

        finally:
            await page.close()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


