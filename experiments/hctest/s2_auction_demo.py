#!/usr/bin/env python3
"""
Simplified Auction Demo Script

This script loads a saved session and directly navigates to LiveAuctionsCalendar
to join the first available auction.
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from production_integration import WebsiteAutomationBot

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Change to script directory to ensure .env file is found
script_dir = Path(__file__).parent
os.chdir(script_dir)

# Load environment variables from .env file
load_dotenv()


async def main():
    """Direct navigation to LiveAuctionsCalendar and join first auction."""

    logger.info("🚀 Simplified Auction Demo")
    logger.info("=" * 50)

    # Load environment variables
    login_url = os.getenv("LOGIN_URL")
    user_email = os.getenv("USER_EMAIL")
    password = os.getenv("PASSWORD")

    if not all([login_url, user_email, password]):
        logger.error("Missing required environment variables: LOGIN_URL, USER_EMAIL, PASSWORD")
        return

    # Initialize the automation bot
    bot = WebsiteAutomationBot()

    try:
        # Setup browser with saved session
        await bot.setup_browser(headless=False)  # Set to True for headless if needed

        # Check if we have a valid session by trying to access a protected page
        logger.info("Checking session validity...")
        test_page = await bot.context.new_page()
        await test_page.goto("https://www.iaai.com/Dashboard/Default", wait_until="domcontentloaded")
        await test_page.wait_for_timeout(3000)

        # Check if redirected to login page or if login elements are present
        current_url = test_page.url
        login_indicators = [
            "login" in current_url.lower(),
            "signin" in current_url.lower(),
            await test_page.locator('input[name="Input.Email"]').is_visible(),
            await test_page.locator('input[name="Input.Password"]').is_visible()
        ]

        is_logged_in = not any(login_indicators)
        await test_page.close()

        if is_logged_in:
            logger.info("Session is valid, user is logged in")
        else:
            logger.info("Session invalid or expired, performing login...")

            # Perform login
            login_success, login_page = await bot.login_with_hcaptcha_handling(
                url=login_url,
                username=user_email,
                password=password,
                close_page=False
            )

            if not login_success:
                logger.error("Login failed, cannot proceed")
                return

            # Close the login page after successful login
            if login_page:
                await login_page.close()

        # Create a new page for the auction
        page = await bot.context.new_page()

        # Navigate directly to LiveAuctionsCalendar
        live_auctions_url = "https://www.iaai.com/LiveAuctionsCalendar"
        logger.info(f"Navigating to {live_auctions_url}")
        await page.goto(live_auctions_url, wait_until="domcontentloaded")
        logger.info("Arrived at LiveAuctionsCalendar")

        # Wait for page to load
        await page.wait_for_timeout(5000)

        # Find and click the first "Join Auction" button
        auction_button = page.locator('a.btn.btn-lg.btn-primary.btn-block').nth(0)
        if await auction_button.is_visible():
            await auction_button.click()
            logger.info("Clicked the first Join Auction button")

            # Wait for the page to load and captcha to appear
            await page.wait_for_timeout(5000)

            # Check if it's reCAPTCHA (not hCaptcha)
            recaptcha_present = await page.locator('.g-recaptcha').is_visible()
            if recaptcha_present:
                logger.info("reCAPTCHA detected on AuctionGateway page - waiting for manual solving")

                # Wait for the submit button to be enabled (when captcha is solved)
                submit_button = page.locator('#captchaContinueButton')
                await submit_button.wait_for(state='visible', timeout=300000)  # Wait up to 5 minutes

                # Wait until the button is not disabled
                while await submit_button.get_attribute('disabled') is not None:
                    await page.wait_for_timeout(1000)
                    logger.info("Waiting for reCAPTCHA to be solved...")

                # Click the submit button
                await submit_button.click()
                logger.info("Clicked Submit button after reCAPTCHA solving")
            else:
                # Try hCaptcha solving as fallback
                hcaptcha_success = await bot.hcaptcha_solver.solve_hcaptcha_if_present(page)
                if hcaptcha_success:
                    logger.info("hCaptcha solved successfully on AuctionGateway page")
                else:
                    logger.warning("No captcha found or solving failed on AuctionGateway")

            await page.wait_for_timeout(5000)  # Wait for auction to fully load
        else:
            logger.warning("No Join Auction buttons found or not visible")

        # Keep the page open for observation (optional)
        logger.info("Auction joined. Keeping page open for 30 seconds...")
        await page.wait_for_timeout(30000)

    except Exception as e:
        logger.error(f"❌ Error: {e}")

    finally:
        await bot.cleanup()
        logger.info("\n🧹 Cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())