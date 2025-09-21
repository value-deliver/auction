#!/usr/bin/env python3
"""
Sample Python script using Playwright to automate login on Copart's website.
This script demonstrates filling username/password fields, handling CAPTCHA placeholder,
waiting for dynamic elements, basic error handling, and mouse movement simulation.
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import random
import os

async def main():

    print("Script started")

    # Load credentials from environment variables
    USERNAME = os.environ.get('COPART_USERNAME')
    PASSWORD = os.environ.get('COPART_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("COPART_USERNAME and COPART_PASSWORD environment variables must be set")

    async with async_playwright() as p:
        # Launch browser with GUI for Docker/server environments
        # Set DISPLAY for virtual framebuffer (e.g., Xvfb :99)
        os.environ.setdefault('DISPLAY', ':99')
        browser = await p.chromium.launch(headless=False)  # Set to False for GUI mode

        context = await browser.new_context()

        page = await context.new_page()

        try:
            # Navigate to Copart login page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"Navigating to Copart login page (attempt {attempt + 1}/{max_retries})...")
                    await page.goto("https://www.copart.com/login", timeout=60000)  # 2 minutes
                    print("Waiting for page to load...")
                    await page.wait_for_load_state('networkidle', timeout=60000)
                    break  # Success, exit retry loop
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e  # Last attempt failed, re-raise exception
                    print(f"Attempt {attempt + 1} failed, retrying in 5 seconds...")
                    await asyncio.sleep(5)
            print(f"Login page title: {await page.title()}")
            print(f"Login page URL: {page.url}")

            # Debug: Check page content
            content = await page.content()
            print(f"Page content length: {len(content)}")
            if 'username' in content.lower():
                print("Username field found in page content")
            else:
                print("Username field NOT found in page content")

            # Check for and handle cookie consent popup
            try:
                # First, check if there's any overlay or popup blocking the login form
                print("Checking for cookie consent or blocking popups...")

                # Step 1: Look for "Manage Options" button to open detailed preferences
                manage_options_selectors = [
                    'button[data-testid*="manage"]',
                    'button[id*="manage"]',
                    '.fc-button[data-testid*="manage"]',
                    'button:contains("Manage")',
                    'button:contains("Options")',
                    'button:contains("Settings")'
                ]

                manage_clicked = False
                for selector in manage_options_selectors:
                    try:
                        manage_button = page.locator(selector).first
                        if await manage_button.is_visible(timeout=2000):
                            print(f"Found 'Manage Options' button with selector: {selector}")
                            await manage_button.click()
                            await asyncio.sleep(random.uniform(1, 2))
                            manage_clicked = True
                            break
                    except Exception:
                        continue

                # Also try to find by text content
                if not manage_clicked:
                    try:
                        all_buttons = page.locator('button')
                        button_count = await all_buttons.count()
                        for i in range(button_count):
                            button_text = await all_buttons.nth(i).text_content()
                            if button_text and 'manage' in button_text.lower():
                                print(f"Found 'Manage Options' button with text: '{button_text}'. Clicking it...")
                                await all_buttons.nth(i).click()
                                await asyncio.sleep(random.uniform(1, 2))
                                manage_clicked = True
                                break
                    except Exception as e:
                        print(f"Error searching for manage buttons by text: {e}")

                # Step 2: If manage options was clicked, handle the detailed preferences dialog
                if manage_clicked:
                    print("Managing cookie preferences...")

                    # Wait for the preferences dialog to appear
                    await asyncio.sleep(random.uniform(1, 2))

                    # Uncheck all consent checkboxes that are currently checked
                    try:
                        consent_checkboxes = page.locator('input.fc-preference-consent.purpose:checked')
                        checked_count = await consent_checkboxes.count()
                        print(f"Found {checked_count} checked consent checkboxes to uncheck.")

                        for i in range(checked_count):
                            try:
                                await consent_checkboxes.nth(i).click()
                                await asyncio.sleep(random.uniform(0.1, 0.3))
                            except Exception as e:
                                print(f"Error unchecking consent checkbox {i}: {e}")
                    except Exception as e:
                        print(f"Error handling consent checkboxes: {e}")

                    # Click "Confirm choices" button
                    confirm_selectors = [
                        '.fc-button.fc-confirm-choices.fc-primary-button',
                        'button[data-testid*="confirm"]',
                        'button:contains("Confirm")'
                    ]

                    confirm_clicked = False
                    for selector in confirm_selectors:
                        try:
                            confirm_button = page.locator(selector).first
                            if await confirm_button.is_visible(timeout=2000):
                                print(f"Clicking 'Confirm choices' button with selector: {selector}")
                                await confirm_button.click()
                                await asyncio.sleep(random.uniform(2, 4))
                                confirm_clicked = True
                                break
                        except Exception:
                            continue

                    if not confirm_clicked:
                        # Try by text
                        try:
                            all_buttons = page.locator('button')
                            button_count = await all_buttons.count()
                            for i in range(button_count):
                                button_text = await all_buttons.nth(i).text_content()
                                if button_text and 'confirm' in button_text.lower():
                                    print(f"Found 'Confirm choices' button with text: '{button_text}'. Clicking it...")
                                    await all_buttons.nth(i).click()
                                    await asyncio.sleep(random.uniform(2, 4))
                                    confirm_clicked = True
                                    break
                        except Exception as e:
                            print(f"Error searching for confirm buttons by text: {e}")

                    if confirm_clicked:
                        print("Cookie preferences configured and confirmed.")
                    else:
                        print("Could not find 'Confirm choices' button.")
                else:
                    print("No 'Manage Options' button found.")

            except Exception as e:
                print(f"Error handling cookie consent popup: {e}")

            # Wait for the login form to load (dynamic elements)
            await page.wait_for_selector('input[name="username"]', timeout=62000)

            # Click on username field to focus
            await page.click('input[name="username"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill username field
            await page.fill('input[name="username"]', USERNAME)
            await asyncio.sleep(random.uniform(2, 5))

            # Click on password field to focus
            await page.click('input[name="password"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill password field
            await page.fill('input[name="password"]', PASSWORD)
            await asyncio.sleep(random.uniform(2, 5))

            # Add random mouse movements to simulate human behavior
            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # CAPTCHA handling placeholder
            # In a real scenario, integrate with a CAPTCHA solver like 2Captcha
            # Example: Check if CAPTCHA is present
            captcha_selector = 'div.captcha'  # Adjust based on actual selector
            if await page.query_selector(captcha_selector):
                print("CAPTCHA detected. Placeholder: Integrate 2Captcha or manual solve here.")
                # Placeholder: Wait for manual solve or API call
                await asyncio.sleep(10)  # Simulate waiting for solve

            # Submit the form (triggers POST request)
            await asyncio.sleep(random.uniform(3, 7))
            # Use the login button with specific data-uname
            login_button_locator = page.locator('button[data-uname="loginSigninmemberbutton"]').first

            # Simulate realistic mouse movement to the submit button
            print("Moving mouse to submit button...")
            button_box = await login_button_locator.bounding_box()
            if button_box:
                # Get current mouse position (start from a random position if needed)
                current_pos = await page.evaluate("() => ({ x: window.mouseX || 0, y: window.mouseY || 0 })")

                # If no current position, start from top-left area
                if not current_pos or (current_pos['x'] == 0 and current_pos['y'] == 0):
                    start_x, start_y = random.randint(50, 200), random.randint(50, 200)
                else:
                    start_x, start_y = current_pos['x'], current_pos['y']

                # Target position (center of button)
                target_x = button_box['x'] + button_box['width'] / 2
                target_y = button_box['y'] + button_box['height'] / 2

                # Simulate human-like mouse movement with multiple steps
                steps = random.randint(5, 10)
                for step in range(steps):
                    # Calculate intermediate position with some randomness
                    progress = (step + 1) / steps
                    intermediate_x = start_x + (target_x - start_x) * progress + random.randint(-10, 10)
                    intermediate_y = start_y + (target_y - start_y) * progress + random.randint(-10, 10)

                    # Ensure coordinates stay within viewport bounds
                    viewport = page.viewport_size
                    intermediate_x = max(0, min(intermediate_x, viewport['width']))
                    intermediate_y = max(0, min(intermediate_y, viewport['height']))

                    await page.mouse.move(intermediate_x, intermediate_y)
                    await asyncio.sleep(random.uniform(0.05, 0.15))  # Small delay between movements

                # Final precise movement to button center
                await page.mouse.move(target_x, target_y)
                await asyncio.sleep(random.uniform(0.2, 0.5))

            # Simulate manual hover and click
            await login_button_locator.hover()
            await asyncio.sleep(random.uniform(3, 5))  # Longer pause to show hover styles
            await login_button_locator.click(timeout=random.randint(10000, 30000))

            # Wait for navigation after login (e.g., redirect to dashboard)
            try:
                await page.wait_for_url(lambda url: url != "https://www.copart.com/login", timeout=30000)
                print(f"Post-login page title: {await page.title()}")
                print(f"Post-login URL: {page.url}")
            except Exception as e:
                print(f"Error waiting for navigation: {e}")
                print(f"Current URL: {page.url}")
            
            # Check for post-login elements
            dashboard_element = await page.query_selector('text="Dashboard"')
            logout_element = await page.query_selector('text="Logout"')
            if dashboard_element or logout_element:
                print("Found post-login elements: Dashboard or Logout")
            else:
                print("Post-login elements not found")
            
            # Check for login success
            if page.url != "https://www.copart.com/login":
                print("Login successful!")

                # Navigate to My Wishlist
                await page.goto("https://www.copart.com/watchList")
                await page.wait_for_load_state('networkidle')
                print(f"Wishlist page title: {await page.title()}")
                print(f"Wishlist URL: {page.url}")

                # Get all lot numbers from the wishlist items
                lot_links = page.locator('.search_result_lot_number a')
                lot_numbers = []
                for i in range(await lot_links.count()):
                    text = await lot_links.nth(i).text_content()
                    lot_number = text.strip()
                    if lot_number.isdigit():
                        lot_numbers.append(lot_number)

                print(f"Found lot numbers: {lot_numbers}")
            else:
                print("Login may have failed. Check for errors.")


        except PlaywrightTimeoutError as e:
            print(f"Timeout error: {e}. Page may not have loaded properly.")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            await asyncio.sleep(30)  # Keep browser open for 30 seconds
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())