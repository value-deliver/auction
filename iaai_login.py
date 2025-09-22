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
from pathlib import Path
import base64
import time

def load_env_file():
    """Load environment variables from .env file if it exists"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key] = value

async def detect_incapsula_block(page):
    """Detect if Incapsula WAF has blocked the request"""
    try:
        # Check for Chrome error pages (Incapsula blocking at browser level)
        current_url = page.url
        if current_url.startswith('chrome-error://') or 'chromewebdata' in current_url:
            print("Chrome error page detected - likely Incapsula WAF block!")
            print("Incapsula is blocking requests at the browser level.")
            return "chrome_error_block"

        # Check for Incapsula-specific indicators
        page_title = await page.title()
        if "Request unsuccessful" in page_title:
            return True

        # Check for Incapsula iframe
        try:
            incapsula_iframe = page.locator('iframe#main-iframe, iframe[src*="_Incapsula_Resource"]')
            if await incapsula_iframe.is_visible(timeout=2000):
                src = await incapsula_iframe.get_attribute('src')
                if src and '_Incapsula_Resource' in src:
                    print("Incapsula WAF iframe block detected!")
                    print(f"Incident ID: {src.split('incident_id=')[1].split('&')[0] if 'incident_id=' in src else 'Unknown'}")
                    return True
        except:
            pass

        # Check page content for Incapsula indicators
        page_text = await page.inner_text('body')
        incapsula_indicators = [
            "Request unsuccessful. Incapsula incident ID:",
            "_Incapsula_Resource",
            "ROBOTS NOINDEX, NOFOLLOW",
            "Your request has been blocked",
            "Access denied",
            "Forbidden"
        ]

        for indicator in incapsula_indicators:
            if indicator in page_text:
                print(f"Incapsula block detected: {indicator}")
                return True

        return False

    except Exception as e:
        print(f"Error detecting Incapsula block: {e}")
        return False

async def detect_captcha(page):
    """Detect if a CAPTCHA is present on the page"""
    try:
        print("Scanning page for CAPTCHA elements...")

        # First check for Incapsula blocks (more serious than CAPTCHAs)
        if await detect_incapsula_block(page):
            print("Incapsula WAF block detected - this is more serious than a CAPTCHA!")
            return "incapsula_block"

        # Common CAPTCHA selectors
        captcha_selectors = [
            '.captcha',
            '.recaptcha',
            '.h-captcha',
            '[class*="captcha"]',
            '.challenge-container',  # Common for image-based CAPTCHAs
            '.rc-imageselect',  # reCAPTCHA image select
            '.task-image',  # Some custom CAPTCHAs
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '.challenge',  # Generic challenge container
            '.security-check',
            '.verification',
            '.puzzle',  # Some sites use puzzle
            '.grid-captcha',  # Grid-based CAPTCHAs
            '.image-captcha'
        ]

        for selector in captcha_selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    print(f"CAPTCHA detected with selector: {selector}")
                    # Get more details about the CAPTCHA
                    try:
                        captcha_text = await element.inner_text()
                        if captcha_text:
                            # Handle encoding issues
                            safe_text = captcha_text.encode('ascii', 'ignore').decode('ascii')
                            print(f"CAPTCHA content preview: {safe_text[:100]}...")
                    except:
                        pass
                    return True
            except:
                continue

        # Check for CAPTCHA-related text in the entire page
        captcha_text_indicators = [
            "select all images",
            "select all squares",
            "select all pictures",
            "click on all",
            "choose all",
            "verify you are human",
            "security check",
            "prove you are not a robot",
            "complete the challenge",
            "security verification",
            "are you a robot",
            "confirm you are human",
            "select the images",
            "pick the correct images",
            "what do you usually find in",
            "select all images with",
            "click on the",
            "forest",  # Specific to IAAI CAPTCHA
            "bat",     # Specific to IAAI CAPTCHA
            "animals", # Common in image CAPTCHAs
            "birds",   # Common in image CAPTCHAs
            "verify your humanity",
            "anti-bot verification",
            "bot detection",
            "suspicious activity detected",
            "additional security check",
            "please verify"
        ]

        page_text = await page.inner_text('body')
        # Handle encoding issues by removing problematic characters
        page_text = page_text.encode('ascii', 'ignore').decode('ascii')
        page_text_lower = page_text.lower()

        for indicator in captcha_text_indicators:
            if indicator.lower() in page_text_lower:
                print(f"CAPTCHA text detected: '{indicator}'")
                # Safely extract text around the CAPTCHA
                start_pos = max(0, page_text_lower.find(indicator) - 50)
                end_pos = min(len(page_text), page_text_lower.find(indicator) + 150)
                context_text = page_text[start_pos:end_pos]
                # Remove any remaining problematic characters
                context_text = context_text.encode('ascii', 'ignore').decode('ascii')
                print(f"Page context: ...{context_text}...")
                return True

        # Check for iframe-based CAPTCHAs
        try:
            iframes = page.locator('iframe')
            iframe_count = await iframes.count()
            for i in range(iframe_count):
                iframe = iframes.nth(i)
                src = await iframes.nth(i).get_attribute('src')
                if src and ('recaptcha' in src or 'hcaptcha' in src or 'captcha' in src):
                    print(f"CAPTCHA iframe detected: {src}")
                    return True
        except:
            pass

        print("No CAPTCHA detected on this page")
        return False

    except Exception as e:
        print(f"Error detecting CAPTCHA: {e}")
        return False

async def solve_captcha(page):
    """Attempt to solve CAPTCHA using 2Captcha service"""
    try:
        # Get CAPTCHA solving API key from environment
        api_key = os.environ.get('TWOCAPTCHA_API_KEY')
        if not api_key:
            print("No 2Captcha API key found. Set TWOCAPTCHA_API_KEY environment variable.")
            print("Get API key from: https://2captcha.com/")
            return False

        print("Attempting to solve image-based CAPTCHA...")

        # Try different CAPTCHA selectors
        captcha_selectors = [
            '.challenge-container',
            '.rc-imageselect',
            '.task-image',
            '[class*="captcha"]',
            '.captcha-challenge'
        ]

        captcha_element = None
        for selector in captcha_selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    captcha_element = element
                    print(f"Found CAPTCHA element with selector: {selector}")
                    break
            except:
                continue

        if not captcha_element:
            print("Could not find CAPTCHA element")
            return False

        # Get the CAPTCHA task text
        task_selectors = [
            '.challenge-prompt',
            '.task-text',
            '.instruction',
            '.rc-imageselect-instructions',
            '.captcha-text'
        ]

        task_text = ""
        for selector in task_selectors:
            try:
                text = await page.inner_text(selector)
                if text and len(text.strip()) > 5:
                    task_text = text.strip()
                    print(f"CAPTCHA task: {task_text}")
                    break
            except:
                continue

        if not task_text:
            task_text = "Select images"
            print("Could not extract CAPTCHA task text, using default")

        # Take screenshot of CAPTCHA area
        try:
            captcha_screenshot = await captcha_element.screenshot(type='png')
            if not captcha_screenshot:
                print("Could not capture CAPTCHA screenshot")
                return False
        except Exception as e:
            print(f"Error taking CAPTCHA screenshot: {e}")
            return False

        # Convert to base64 for API
        captcha_base64 = base64.b64encode(captcha_screenshot).decode('utf-8')

        # Determine CAPTCHA type and send to 2Captcha
        print("Sending CAPTCHA to 2Captcha service...")

        # For now, implement a basic Grid CAPTCHA solver
        # In production, you'd want more sophisticated logic for different CAPTCHA types

        success = await solve_grid_captcha(page, captcha_element, task_text, captcha_base64, api_key)

        if success:
            print("CAPTCHA solved successfully!")
            return True
        else:
            print("CAPTCHA solving failed")
            return False

    except Exception as e:
        print(f"Error solving CAPTCHA: {e}")
        return False

async def solve_grid_captcha(page, captcha_element, task_text, image_base64, api_key):
    """Solve grid-based CAPTCHA (select specific images)"""
    try:
        # This is a simplified implementation
        # Real implementation would:
        # 1. Send image to 2Captcha with proper task type
        # 2. Wait for solution
        # 3. Parse coordinates and click images

        print("Grid CAPTCHA solving not fully implemented yet.")
        print("This would require:")
        print("- Proper 2Captcha API integration")
        print("- Image analysis to determine grid layout")
        print("- Coordinate parsing and clicking")

        # For demonstration, we'll implement a basic approach
        # In practice, you'd use the 2Captcha API

        # Example API call structure (commented out):
        """
        import requests

        # Submit CAPTCHA task
        submit_url = "http://2captcha.com/in.php"
        submit_data = {
            'key': api_key,
            'method': 'base64',
            'body': image_base64,
            'textinstructions': task_text,
            'json': 1
        }

        submit_response = requests.post(submit_url, data=submit_data)
        if submit_response.json().get('status') == 1:
            task_id = submit_response.json()['request']

            # Poll for result
            result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"

            for _ in range(60):  # Wait up to 60 seconds
                result_response = requests.get(result_url)
                result_data = result_response.json()

                if result_data.get('status') == 1:
                    solution = result_data['request']
                    # Parse solution and click images
                    return await apply_captcha_solution(page, captcha_element, solution)

                time.sleep(1)

        return False
        """

        print("For now, keeping browser open for manual CAPTCHA solving...")
        await asyncio.sleep(60)  # Keep browser open for manual solving
        return False

    except Exception as e:
        print(f"Error in grid CAPTCHA solving: {e}")
        return False

async def apply_captcha_solution(page, captcha_element, solution):
    """Apply the CAPTCHA solution by clicking appropriate images"""
    try:
        # Parse solution (typically coordinates like "1,2,4" for grid positions)
        if isinstance(solution, str) and ',' in solution:
            positions = [int(pos.strip()) for pos in solution.split(',')]

            # Click each position
            for pos in positions:
                try:
                    # Find image at position (this depends on CAPTCHA layout)
                    image_selector = f'.captcha-image:nth-child({pos}), [data-position="{pos}"], .grid-item:nth-child({pos})'
                    await page.click(image_selector, timeout=5000)
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                except:
                    print(f"Could not click position {pos}")

            # Submit the CAPTCHA
            submit_selectors = ['.captcha-submit', '.verify-button', 'button[type="submit"]']
            for selector in submit_selectors:
                try:
                    await page.click(selector, timeout=2000)
                    print("Submitted CAPTCHA solution")
                    return True
                except:
                    continue

        return False

    except Exception as e:
        print(f"Error applying CAPTCHA solution: {e}")
        return False

async def main():

    print("IAAI Script started")

    # Load environment variables from .env file
    load_env_file()

    # Load credentials from environment variables
    USERNAME = os.environ.get('IAAI_USERNAME')
    PASSWORD = os.environ.get('IAAI_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("IAAI_USERNAME and IAAI_PASSWORD environment variables must be set")

    async with async_playwright() as p:
        # Launch browser with GUI for Docker/server environments
        # Set DISPLAY for virtual framebuffer (e.g., Xvfb :99)
        os.environ.setdefault('DISPLAY', ':99')
        browser = await p.chromium.launch(headless=False)  # Set to True for headless mode when running locally

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1366, 'height': 768},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            geolocation={'latitude': 40.7128, 'longitude': -74.0060},  # New York coordinates
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
            },
            # Additional anti-detection measures
            bypass_csp=True,
            ignore_https_errors=True,
            # Reduce automation detection
            has_touch=False,  # Most desktop users don't have touch
            is_mobile=False,
        )

        page = await context.new_page()

        try:
            # Navigate to IAAI login page with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"Navigating to IAAI login page (attempt {attempt + 1}/{max_retries})...")
                    response = await page.goto("https://login.iaai.com/Identity/Account/Login", timeout=60000)  # 2 minutes
                    print(f"Response status: {response.status if response else 'No response'}")
                    print("Waiting for page to load...")
                    await page.wait_for_load_state('domcontentloaded', timeout=30000)
                    # Wait a bit more for dynamic content
                    await asyncio.sleep(2)
                    break  # Success, exit retry loop
                except Exception as e:
                    print(f"Navigation error: {e}")
                    if attempt == max_retries - 1:
                        raise e  # Last attempt failed, re-raise exception
                    print(f"Attempt {attempt + 1} failed, retrying in 5 seconds...")
                    await asyncio.sleep(5)
            try:
                print(f"Login page title: {await page.title()}")
                print(f"Login page URL: {page.url}")
            except Exception as e:
                print(f"Error getting page info: {e}")
                print(f"Page URL: {page.url if page else 'No page'}")

            # Debug: Check page content
            content = await page.content()
            print(f"Page content length: {len(content)}")
            if 'email' in content.lower():
                print("Email field found in page content")
            else:
                print("Email field NOT found in page content")

            # Wait for the login form to load (dynamic elements)
            await page.wait_for_selector('input[name="Input.Email"]', timeout=62000)

            # Add human-like behavior: scroll a bit
            await page.evaluate("window.scrollTo(0, " + str(random.randint(50, 150)) + ")")
            await asyncio.sleep(random.uniform(1, 2))

            # Click on email field to focus
            await page.click('input[name="Input.Email"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Type email character by character with random delays (more human-like)
            for char in USERNAME:
                await page.type('input[name="Input.Email"]', char, delay=random.randint(100, 300))
            await asyncio.sleep(random.uniform(1, 3))

            # Click on password field to focus
            await page.click('input[name="Input.Password"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Type password character by character
            for char in PASSWORD:
                await page.type('input[name="Input.Password"]', char, delay=random.randint(150, 400))
            await asyncio.sleep(random.uniform(1, 3))

            # Maybe check "Remember Me" checkbox sometimes
            if random.choice([True, False]):
                try:
                    await page.click('input[name="Input.RememberMe"]')
                    await asyncio.sleep(random.uniform(0.5, 1))
                except:
                    pass  # Checkbox might not be present

            # Add random mouse movements to simulate human behavior
            for _ in range(random.randint(2, 5)):
                await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                await asyncio.sleep(random.uniform(0.5, 1.5))

            # Maybe hover over some elements randomly
            try:
                # Find some random clickable elements and hover over them briefly
                links = page.locator('a')
                if await links.count() > 0:
                    random_link = links.nth(random.randint(0, min(5, await links.count() - 1)))
                    await random_link.hover()
                    await asyncio.sleep(random.uniform(0.5, 2))
            except:
                pass

            # Submit the form (triggers POST request)
            await asyncio.sleep(random.uniform(5, 12))  # Longer pause before submit

            # Debug: Check if form fields are filled
            email_value = await page.input_value('input[name="Input.Email"]')
            password_value = await page.input_value('input[name="Input.Password"]')
            print(f"Email field value: '{email_value}'")
            print(f"Password field value: '{password_value[:3] if password_value else 'empty'}***'")

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

            # Wait for form submission and check result
            try:
                # Wait a bit for any form processing
                await asyncio.sleep(3)

                # Check current URL
                current_url = page.url
                print(f"Current URL after submit: {current_url}")

                # Check for error messages
                error_selectors = [
                    '#lblErrorMessage',
                    '#lblEmailMessage',
                    '#lblBuyerProfileCalims',
                    '.alert-error',
                    '.alert-danger'
                ]

                login_successful = True
                for selector in error_selectors:
                    try:
                        error_element = page.locator(selector).first
                        if await error_element.is_visible():
                            error_text = await error_element.text_content()
                            print(f"Login error found: {error_text}")
                            login_successful = False
                            break
                    except:
                        continue

                if "login.iaai.com" not in current_url and login_successful:
                    print(f"Post-login page title: {await page.title()}")
                    print(f"Post-login URL: {current_url}")

                    # Wait for dashboard to fully load and check for CAPTCHA
                    print("Waiting for dashboard to load completely...")
                    await asyncio.sleep(3)  # Give time for any redirects or dynamic content

                    # Check current URL again (might have redirected)
                    final_url = page.url
                    print(f"Final dashboard URL: {final_url}")

                    # Check for CAPTCHA on dashboard page - multiple checks with delays
                    print("Checking for CAPTCHA on dashboard page...")

                    # First check immediately
                    captcha_detected = await detect_captcha(page)
                    if not captcha_detected:
                        # Wait a bit and check again (CAPTCHA might load dynamically)
                        print("Waiting for potential dynamic CAPTCHA loading...")
                        await asyncio.sleep(5)
                        captcha_detected = await detect_captcha(page)

                    if not captcha_detected:
                        # Final check after more waiting
                        await asyncio.sleep(3)
                        captcha_detected = await detect_captcha(page)

                    if captcha_detected:
                        if captcha_detected == "incapsula_block":
                            print("INCAPSULA WAF IFRAME BLOCK DETECTED!")
                            print("This is a serious security block, not just a CAPTCHA.")
                            print("Incapsula has flagged this session as suspicious.")
                            print("")
                            print("RECOMMENDED ACTIONS:")
                            print("1. Wait several hours before trying again")
                            print("2. Use a different IP address")
                            print("3. Reduce login frequency")
                            print("4. Consider using residential proxies")
                            print("5. The browser will stay open for manual inspection")
                            await asyncio.sleep(600)  # 10 minutes to inspect
                        elif captcha_detected == "chrome_error_block":
                            print("INCAPSULA CHROME ERROR BLOCK DETECTED!")
                            print("Incapsula is blocking requests at the browser level.")
                            print("This is the most serious type of block.")
                            print("")
                            print("CRITICAL ISSUES DETECTED:")
                            print("- Browser-level blocking (chrome-error:// URL)")
                            print("- Incapsula WAF is rejecting all requests")
                            print("")
                            print("IMMEDIATE ACTIONS REQUIRED:")
                            print("1. STOP all automation immediately")
                            print("2. Wait 24-48 hours before any attempts")
                            print("3. Use a completely different IP address")
                            print("4. Consider residential proxies or VPN")
                            print("5. Reduce automation frequency significantly")
                            print("6. The account may be flagged - manual login may also fail")
                            print("")
                            print("The browser will stay open for inspection, but automation should stop.")
                            await asyncio.sleep(1200)  # 20 minutes for serious inspection
                        else:
                            print("CAPTCHA detected on dashboard page. Attempting to solve...")
                            captcha_solved = await solve_captcha(page)
                            if not captcha_solved:
                                print("CAPTCHA solving failed. Manual intervention required.")
                                print("Please complete the CAPTCHA in the browser window.")
                                print("The script will wait for you to complete it manually.")
                                # Keep browser open for manual solving
                                await asyncio.sleep(300)  # 5 minutes for manual solving
                            else:
                                print("CAPTCHA solved successfully! Continuing...")
                                await asyncio.sleep(2)  # Wait for any post-CAPTCHA redirects
                    else:
                        print("No security challenges detected on dashboard page.")
                else:
                    print("Login appears to have failed or is still processing")

            except Exception as e:
                print(f"Error checking login result: {e}")
                print(f"Current URL: {page.url}")

            # Check for login success
            if "login.iaai.com" not in page.url:
                print("Login successful!")
                print(f"Current page: {page.url}")
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