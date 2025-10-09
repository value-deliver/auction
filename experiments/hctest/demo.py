#!/usr/bin/env python3
"""
Demo script for Production AgentV Integration

This script demonstrates how to use the production integration library
for handling hCaptcha challenges in website automation.
"""

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from solvecaptcha import Solvecaptcha

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
    """Example usage of the production integration."""

    logger.info("🚀 Production AgentV Integration Demo")
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
        # Example 1: Login with hCaptcha handling
        logger.info("\n📝 Example 1: Login with hCaptcha")
        login_success, page = await bot.login_with_hcaptcha_handling(
            url=login_url,
            username=user_email,
            password=password,
            close_page=False
        )

        if login_success and page:
            logger.info("✅ Login completed successfully")

            # Check for session cookies as additional confirmation
            cookies = await page.context.cookies()
            session_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'auth' in c['name'].lower()]
            if session_cookies:
                logger.info(f"Found {len(session_cookies)} session/auth cookies: {[c['name'] for c in session_cookies]}")
            else:
                logger.warning("No session/auth cookies found, but proceeding with post-login")

            # Handle IAAI-specific post-login redirect
            try:
                await page.wait_for_timeout(5000)
                logger.info("Checking for Log In link to redirect to dashboard")
                links = page.locator('a[href="/Dashboard/Default"][aria-label="Log In"]')
                count = await links.count()
                for i in range(count):
                    if await links.nth(i).is_visible():
                        await links.nth(i).click()
                        logger.info(f"Clicked visible Log In link at index {i}")
                        # Wait for redirect to Dashboard
                        await page.wait_for_url("**/Dashboard/Default")
                        logger.info("Redirected to Dashboard")

                         # Enter "bmw" in search input and press Enter
                        await page.fill('#suggestions', 'bmw')
                        await page.press('#suggestions', 'Enter')
                        logger.info("Entered 'bmw' and pressed Enter")
                        # Wait for search results to load
                        await page.wait_for_load_state('domcontentloaded')
                        logger.info("Search results loaded")
                 
                        # Click the watchlist button for the first vehicle found, if not already watching
                        watch_buttons = page.locator('a.btn-watch')
                        count = await watch_buttons.count()
                        vehicle_id = None
                        vehicle_id_short = None
                        if count > 1:  # Ensure there are vehicle buttons beyond "Watch all"
                            watch_button = watch_buttons.nth(1)  # Skip the "Watch all" button
                            if await watch_button.is_visible():
                                button_class = await watch_button.get_attribute('class')
                                if button_class and 'is-watching' not in button_class:
                                    await watch_button.click()
                                    logger.info("Clicked watchlist button for the first vehicle")
                                    # Store the vehicle ID
                                    vehicle_id = await watch_button.get_attribute('watchinventoryid')
                                    if vehicle_id:
                                        # Extract the ID part, e.g., "43847964~US" -> "43847964"
                                        vehicle_id_short = vehicle_id.split('~')[0]
                                        logger.info(f"Stored vehicle ID: {vehicle_id_short}")
                                    await page.wait_for_timeout(2000)  # Wait for action to complete
                                else:
                                    logger.info("Vehicle is already in watchlist or class not found")
                            else:
                                logger.warning("Watchlist button not visible")
                        else:
                            logger.warning("No vehicle watch buttons found")

                        # Hover over "My Auction Center" a to reveal menu
                        auctions_button = page.locator('a[href="/Dashboard/Default"]').nth(0)
                        await auctions_button.hover()
                        await page.wait_for_timeout(2000)  # Wait for dropdown to appear
                        logger.info("Hovered over My Auction Center a")

                        # Click on "My Vehicles" in the navigation
                        my_vehicles_link = page.locator('a[href="/MyVehicles"]').nth(0)
                        await my_vehicles_link.click()
                        logger.info("Clicked 'My Vehicles' link")
                        await page.wait_for_load_state('domcontentloaded')
                        logger.info("My Vehicles page loaded")
                       # Confirm that the vehicle is in the watchlist and remove it
                        vehicle_present = False
                        if vehicle_id:
                            all_elements = page.locator('a.btn-watch[watchinventoryid]')
                            count = await all_elements.count()
                            for i in range(count):
                                element = all_elements.nth(i)
                                id_value = await element.get_attribute('watchinventoryid')
                                if id_value == vehicle_id:
                                    vehicle_present = True
                                    # Click the button to remove from watchlist
                                    await element.click()
                                    logger.info(f"Clicked to remove vehicle {vehicle_id} from watchlist")
                                    await page.wait_for_timeout(2000)  # Wait for action to complete
                                    break
                            if vehicle_present:
                                logger.info(f"Vehicle {vehicle_id} was present and removed from My Vehicles")
                            else:
                                logger.warning(f"Vehicle {vehicle_id} not found in My Vehicles")
                        else:
                            logger.warning("No vehicle ID stored to check in My Vehicles")
                            
                        # Hover over the active Auctions dropdown (first li)
                        active_auctions = page.locator('a[href="/Auctions"]').nth(0)
                        await active_auctions.hover()
                        logger.info("Hovered over Auctions dropdown")

                        # Click on the inactive Auctions dropdown (second li)
                        inactive_auctions = page.locator('a[href="/LiveAuctionsCalendar"]').nth(0)
                        await inactive_auctions.wait_for(state='visible')
                        await inactive_auctions.click()
                        logger.info("Clicked on LiveAuctionsCalendar")
                        await page.wait_for_timeout(10000) 

                        auction_button = page.locator('a.btn.btn-lg.btn-primary.btn-block').nth(0)
                        if await auction_button.is_visible():
                            await auction_button.click()
                            logger.info("Clicked the first Join Auction button")
                            await page.wait_for_timeout(5000)  # Wait for auction to load

                            # Solve reCaptcha if present
                            logger.info("Checking for reCaptcha after joining auction")
                            sitekey = await page.evaluate('''
                                const recaptcha = document.querySelector('.g-recaptcha');
                                return recaptcha ? recaptcha.getAttribute('data-sitekey') : null;
                            ''')
                            if sitekey:
                                logger.info(f"reCaptcha found with sitekey: {sitekey}")
                                api_key = os.getenv("SOLVECAPTCHA_API_KEY")
                                if api_key:
                                    solver = Solvecaptcha(api_key)
                                    url = page.url
                                    try:
                                        result = solver.recaptcha(sitekey=sitekey, url=url)
                                        token = result['code']
                                        logger.info("reCaptcha token obtained")
                                        await page.evaluate(f'document.querySelector(\'textarea[name="g-recaptcha-response"]\').value = "{token}";')
                                        logger.info("reCaptcha token injected")
                                    except Exception as e:
                                        logger.error(f"reCaptcha solving failed: {e}")
                                else:
                                    logger.error("SOLVECAPTCHA_API_KEY not found")
                            else:
                                logger.info("No reCaptcha found")
                        else:
                            logger.warning("No Join Auction buttons found or not visible")


                    else:
                        logger.debug("Log In link not visible")
                else:
                    logger.info("No visible Log In link found")
            except Exception as e:
                logger.warning(f"Post-login redirect failed: {e}")
            finally:
                await page.close()

        else:
            logger.error("❌ Login failed")
            if page:
                await page.close()

    except Exception as e:
        logger.error(f"❌ Error: {e}")

    finally:
        await bot.cleanup()
        logger.info("\n🧹 Cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())