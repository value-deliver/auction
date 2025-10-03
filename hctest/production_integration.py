#!/usr/bin/env python3
"""
Production Integration Example - How to use AgentV on real websites

This script demonstrates how to integrate AgentV into your website automation
for handling hCaptcha challenges in production scenarios.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from hcaptcha_challenger import AgentV, AgentConfig

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

    async def detect_captcha_in_frame(self, frame, depth=0):
        """Recursively detect CAPTCHA in a frame and its child frames, returning the frame containing CAPTCHA"""
        indent = "  " * depth
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
                        print(f"{indent}Found {count} CAPTCHA iframes with selector: {selector}")
                        return frame
                except Exception as e:
                    pass

            # Check for iframes in this frame
            iframes = frame.locator('iframe')
            iframe_count = await iframes.count()
            print(f"{indent}Found {iframe_count} iframes in frame")

            for i in range(iframe_count):
                try:
                    iframe = iframes.nth(i)
                    src = await iframe.get_attribute('src')
                    data_id = await iframe.get_attribute('data-id')
                    print(f"{indent}  Iframe {i}: src='{src}', data-id='{data_id}'")

                    # Recursively check child frames
                    try:
                        element = await iframe.element_handle()
                        child_frame = await element.content_frame()
                    except Exception as e:
                        print(f"{indent}  Error getting content frame for iframe {i}: {e}")
                        continue
                    if child_frame:
                        # Recurse into child frame
                        result = await self.detect_captcha_in_frame(child_frame, depth + 1)
                        if result:
                            return result

                except Exception as e:
                    print(f"{indent}  Error checking iframe {i}: {e}")

            return None

        except Exception as e:
            print(f"{indent}Error in frame detection: {e}")
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
                print("hCaptcha detected, initializing solver...")

                # Manually click the checkbox
                frame_locator = captcha_frame.frame_locator("iframe[title='Widget containing checkbox for hCaptcha security challenge']")
                checkbox = frame_locator.locator("#checkbox")
                await checkbox.click()
                print("Clicked checkbox")

                # Initialize AgentV and solve the challenge
                agent = AgentV(page=page, agent_config=self.agent_config)

                # Wait for and solve challenge
                await agent.wait_for_challenge()

                # Check result
                if agent.cr_list:
                    latest_result = agent.cr_list[-1]
                    success = latest_result.is_pass
                    print(f"hCaptcha result: {'SOLVED' if success else 'FAILED'}")
                    return True
                else:
                    print("No hCaptcha response received")
                    return False
            else:
                # No hCaptcha found, continue normally
                return True

        except Exception as e:
            print(f"hCaptcha solving error: {e}")
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
            print("hCaptcha appeared, solving...")

            # Solve it
            return await self.solve_hcaptcha_if_present(page)

        except Exception as e:
            print(f"Timeout waiting for hCaptcha: {e}")
            return False


class WebsiteAutomationBot:
    """Example bot showing how to integrate hCaptcha solving into website automation."""

    def __init__(self):
        self.hcaptcha_solver = HcaptchaSolver()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    async def setup_browser(self, headless: bool = False):
        """Setup browser with anti-detection measures."""
        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=[
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
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York"
        )

        return playwright

    async def login_with_hcaptcha_handling(self, url: str, username: str, password: str) -> bool:
        """
        Example: Login to a website with automatic hCaptcha handling.

        Args:
            url: Login page URL
            username: Username/email
            password: Password

        Returns:
            bool: True if login successful
        """
        if not self.context:
            await self.setup_browser()

        page = await self.context.new_page()

        try:
            print(f"Navigating to {url}")
            #await page.wait_for_selector('input[name="Input.Email"]')
            await page.goto(url, wait_until="domcontentloaded")

            # Fill login form (adjust selectors for your site)
            await page.fill('input[name="Input.Email"]', username)
            await page.fill('input[name="Input.Password"]', password)

            # Click login button
            await page.click('button[type="submit"]')

            await page.wait_for_timeout(3000)
            # Handle any hCaptcha that appears
            hcaptcha_success = await self.hcaptcha_solver.solve_hcaptcha_if_present(page)

            if hcaptcha_success:
                # Check for Log In link and click if present
                try:
                    await page.wait_for_timeout(5000)
                    print("Try Log In link")
                    links = page.locator('a[href="/Dashboard/Default"][aria-label="Log In"]')
                    count = await links.count()
                    for i in range(count):
                        if await links.nth(i).is_visible():
                            await links.nth(i).click()
                            print(f"Clicked visible link at index {i}")
                            # Wait for redirect to Dashboard
                            await page.wait_for_url("**/Dashboard/Default")
                            print("Redirected to Dashboard")
                            # Enter "bmw" in search input and press Enter
                            await page.fill('#suggestions', 'bmw')
                            await page.press('#suggestions', 'Enter')
                            print("Entered 'bmw' and pressed Enter")
                            break
                        else:
                            print("No visible Log In link found")
                except:
                    pass

                # Wait a bit for login to complete
                await page.wait_for_timeout(3000)

                # Check if login was successful (adjust selector for your site)
                success_indicators = [
                    ".dashboard", "#logout", ".user-menu",
                    "text='Log Out'", "text='My Vehicles'"
                ]

                login_successful = False
                for indicator in success_indicators:
                    try:
                        await page.wait_for_selector(indicator, timeout=5000)
                        login_successful = True
                        break
                    except:
                        continue

                if login_successful:
                    print("Login successful!")
                    return True
                else:
                    print("Login may have failed - check page content")
                    return False
            else:
                print("Failed to solve hCaptcha")
                return False

        except Exception as e:
            print(f"Login automation error: {e}")
            return False

        finally:
            await page.close()

    async def automate_form_submission(self, url: str, form_data: dict) -> bool:
        """
        Generic form submission with hCaptcha handling.

        Args:
            form_data: Dictionary of field selectors to values
                       e.g., {"#name": "John", "#email": "john@example.com"}
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
            await page.click("#submit, [type='submit'], .submit-btn")

            # Handle hCaptcha
            return await self.hcaptcha_solver.solve_hcaptcha_if_present(page)

        finally:
            await page.close()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


async def main():
    """Example usage of the production integration."""

    print("🚀 Production AgentV Integration Demo")
    print("=" * 50)

    # Initialize the automation bot
    bot = WebsiteAutomationBot()

    try:
        # Example 1: Login with hCaptcha handling
        print("\n📝 Example 1: Login with hCaptcha")
        login_success = await bot.login_with_hcaptcha_handling(
            url="https://login.iaai.com/Identity/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3DAuctionCenterPortal%26redirect_uri%3Dhttps%253A%252F%252Fwww.iaai.com%252Fsignin-oidc%26response_type%3Dcode%26scope%3Dopenid%2520profile%2520email%2520phone%2520offline_access%2520BuyerProfileClaims%26code_challenge%3Db1T7tYYAI-Vx6aKGntT6h4yXzGzLq2MsTWiFOaVtGu0%26code_challenge_method%3DS256%26response_mode%3Dform_post%26nonce%3D638950966499688152.MjUyZTNjNTQtYTg4MC00Mjc0LWJiNTUtZTJhNjNlNjg1ZTczNDhjZDdlNzctNzU3NC00NTliLTllNGYtZmExNjYwM2M5MWM1%26state%3DCfDJ8DRA0jV6pYhPksRz74aoaTinSqJEhz9-iUC1_AUgtiTwZV_lpOU93Hhbt3RO77QyZIv6vp38Tuuj-BmeQH264PSLRGT0zbXlBUS3ME4iYAWk_OM9mguA3TCdHwtbb6koDytsYd8GcSQM75cxl3t2HjLwZpHrZlYndk6ptdeBzfPhA6e_OfjqHwsS0_Je9y1SM58aiGJ26AMgt6wbLZcjkSIwqav_UfZVf-L0JJiROxpOEoFNW0vYiyntVPRdNnZhKFGtJDXGzZVc5jOIgM_E33sv1fX1hF7iA05wgiJIoN4DBl9uVpgSB26PzyuU_O213jRCL9uHYJrG3f1dEE4jhdVIqa195jW30gtaQyYzCupeQJvTAybo_xpOShjaVfg890XGedizvFET4aiKPpqdtaSTsvsD-ZVdakLpVdhS1iE8Lf6T_6V1PcoQktPjsXG8k1GRUfZ98zrXkG_NpdELNNpz-ahwoo1bQ4A5NZYiQr7L",  # Replace with real site
            username="reportbraziltest@gmail.com",
            password="y7{xkGm70z$S"
        )

        if login_success:
            print("✅ Login completed successfully")
        else:
            print("❌ Login failed")

        # Example 2: Form submission with hCaptcha
 #       print("\n📝 Example 2: Form submission with hCaptcha")
  #      form_data = {
  #           "#name": "John Doe",
  #           "#email": "john@example.com",
  #          "#message": "Test message"
  #       }

  #       form_success = await bot.automate_form_submission(
  #           url="https://example-site.com/contact",  # Replace with real site
  #           form_data=form_data
  #       )

  #       if form_success:
  #           print("✅ Form submitted successfully")
  #       else:
  #           print("❌ Form submission failed")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await bot.cleanup()
        print("\n🧹 Cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())
