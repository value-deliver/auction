#!/usr/bin/env python3
"""
Sample Python script using Playwright to automate login on IAAI's website.
This script demonstrates filling email/password fields, handling dynamic elements,
basic error handling, and extracting vehicle data from My Vehicles page.
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import random
import os

async def main():

    print("IAAI Script started")

    # Load credentials from environment variables
    USERNAME = os.environ.get('IAAI_USERNAME')
    PASSWORD = os.environ.get('IAAI_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("IAAI_USERNAME and IAAI_PASSWORD environment variables must be set")

    async with async_playwright() as p:
        # Launch browser with GUI for Docker/server environments
        # Set DISPLAY for virtual framebuffer (e.g., Xvfb :99)
        os.environ.setdefault('DISPLAY', ':99')
        browser = await p.chromium.launch(headless=False)  # Set to False for GUI mode

        context = await browser.new_context()

        page = await context.new_page()

        try:
            # Navigate to IAAI login page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"Navigating to IAAI login page (attempt {attempt + 1}/{max_retries})...")
                    await page.goto("http://login.iaai.com/Identity/Account/Login", timeout=60000)  # 2 minutes
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
            if 'email' in content.lower():
                print("Email field found in page content")
            else:
                print("Email field NOT found in page content")

            # Wait for the login form to load (dynamic elements)
            await page.wait_for_selector('input[name="Input.Email"]', timeout=62000)

            # Click on email field to focus
            await page.click('input[name="Input.Email"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill email field
            await page.fill('input[name="Input.Email"]', USERNAME)
            await asyncio.sleep(random.uniform(2, 5))

            # Click on password field to focus
            await page.click('input[name="Input.Password"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill password field
            await page.fill('input[name="Input.Password"]', PASSWORD)
            await asyncio.sleep(random.uniform(2, 5))

            # Add random mouse movements to simulate human behavior
            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Submit the form (triggers POST request)
            await asyncio.sleep(random.uniform(3, 7))
            # Use the login button
            login_button_locator = page.locator('button[type="submit"]').first

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
                await page.wait_for_url(lambda url: "login.iaai.com" not in url, timeout=30000)
                print(f"Post-login page title: {await page.title()}")
                print(f"Post-login URL: {page.url}")
            except Exception as e:
                print(f"Error waiting for navigation: {e}")
                print(f"Current URL: {page.url}")

            # Check for login success
            if "login.iaai.com" not in page.url:
                print("Login successful!")

                # Navigate to My Vehicles page
                await page.goto("https://www.iaai.com/MyVehiclesNew")
                await page.wait_for_load_state('networkidle')
                print(f"My Vehicles page title: {await page.title()}")
                print(f"My Vehicles URL: {page.url}")

                # Extract vehicle data
                vehicles = []

                # Find all vehicle rows
                vehicle_rows = page.locator('.table-row.table-row-border')
                row_count = await vehicle_rows.count()
                print(f"Found {row_count} vehicle rows")

                for i in range(row_count):
                    try:
                        row = vehicle_rows.nth(i)

                        # Extract stock number
                        stock_locator = row.locator('p.text-md').filter(lambda el: el.text_content().strip().startswith('Stock#:'))
                        stock_text = await stock_locator.text_content()
                        stock_number = stock_text.replace('Stock#:', '').strip() if stock_text else 'N/A'

                        # Extract vehicle title
                        title_locator = row.locator('h4.heading-7 a')
                        title_text = await title_locator.text_content()
                        vehicle_title = title_text.strip() if title_text else 'N/A'

                        vehicles.append({
                            'stock_number': stock_number,
                            'title': vehicle_title
                        })

                        print(f"Vehicle {i+1}: Stock# {stock_number} - {vehicle_title}")

                    except Exception as e:
                        print(f"Error extracting data from row {i}: {e}")
                        continue

                print(f"\nExtracted {len(vehicles)} vehicles:")
                for vehicle in vehicles:
                    print(f"Stock#: {vehicle['stock_number']} - Title: {vehicle['title']}")

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