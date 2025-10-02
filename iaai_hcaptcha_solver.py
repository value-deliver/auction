#!/usr/bin/env python3
"""
IAAI hCaptcha Solver using SolveCaptcha API
Based on the tutorial for modern hCaptcha solving
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import random
import os
from pathlib import Path
import requests
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

load_env_file()

# Configuration
SOLVECAPTCHA_API_KEY = os.environ.get('SOLVECAPTCHA_API_KEY')
if not SOLVECAPTCHA_API_KEY:
    print("Warning: SOLVECAPTCHA_API_KEY not found in environment variables")
    print("Set it in your .env file or environment")

async def detect_captcha_in_frame(frame, depth=0):
    """Recursively detect CAPTCHA in a frame and its child frames"""
    indent = "  " * depth
    try:
        # Check for CAPTCHA elements in this frame
        captcha_selectors = [
            '.h-captcha',
            '[data-sitekey]',
            'iframe[src*="hcaptcha"]',
            'iframe[src*="challenge"]',
            'iframe[src*="captcha"]',
            '.challenge-container',
            '.captcha',
            '.recaptcha',
            '.challenge',
            '.security-check',
            '.verification'
        ]

        for selector in captcha_selectors:
            try:
                elements = frame.locator(selector)
                count = await elements.count()
                if count > 0:
                    print(f"{indent}Found {count} CAPTCHA elements with selector: {selector}")
                    return True
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

                # Check if iframe source contains CAPTCHA keywords
                if src and any(keyword in src.lower() for keyword in ['hcaptcha', 'recaptcha', 'captcha']):
                    print(f"{indent}    Found CAPTCHA iframe by src: {src}")
                    return True

                # Check if iframe has hCaptcha data-id
                if data_id and 'hcaptcha' in data_id.lower():
                    print(f"{indent}    Found hCaptcha iframe by data-id: {data_id}")
                    return True

                # Recursively check child frames
                try:
                    element = await iframe.element_handle()
                    child_frame = await element.content_frame()
                except Exception as e:
                    print(f"{indent}  Error getting content frame for iframe {i}: {e}")
                    continue
                if child_frame:
                    # Check html data-id in child frame
                    try:
                        html_element = child_frame.locator('html')
                        inner_data_id = await html_element.get_attribute('data-id')
                        if inner_data_id and 'hcaptcha' in inner_data_id.lower():
                            print(f"{indent}    Found hCaptcha iframe by inner data-id: {inner_data_id}")
                            return True
                    except Exception as e:
                        print(f"{indent}    Error checking inner data-id: {e}")

                    # Recurse into child frame
                    if await detect_captcha_in_frame(child_frame, depth + 1):
                        return True

            except Exception as e:
                print(f"{indent}  Error checking iframe {i}: {e}")

        return False

    except Exception as e:
        print(f"{indent}Error in frame detection: {e}")
        return False

async def detect_captcha(page):
    """Detect if a CAPTCHA is present on the page"""
    try:
        print("Scanning page for CAPTCHA elements...")

        # Wait a bit for dynamic content to load
        await asyncio.sleep(2)

        # Start recursive detection from the main frame
        return await detect_captcha_in_frame(page, 0)

    except Exception as e:
        print(f"Error detecting CAPTCHA: {e}")
        return False

        # Check for various CAPTCHA types
        captcha_selectors = [
            '.h-captcha',
            '[data-sitekey]',
            'iframe[src*="hcaptcha"]',
            'iframe[src*="challenge"]',
            'iframe[src*="captcha"]',
            '.challenge-container',
            '.captcha',
            '.recaptcha',
            '.challenge',
            '.security-check',
            '.verification'
        ]

        for selector in captcha_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    print(f"Found {count} elements with selector: {selector}")
                    # Check if any are visible
                    for i in range(count):
                        element = elements.nth(i)
                        try:
                            visible = await element.is_visible(timeout=1000)
                            if visible:
                                print(f"CAPTCHA detected with selector: {selector} (element {i})")

                                # Try to get more details
                                try:
                                    sitekey = await element.get_attribute('data-sitekey')
                                    if sitekey:
                                        print(f"Site key found: {sitekey}")
                                except:
                                    pass

                                return True
                        except Exception as e:
                            print(f"Error checking visibility for {selector} element {i}: {e}")
            except Exception as e:
                print(f"Error checking selector {selector}: {e}")
                continue

        # Check for CAPTCHA-related text
        page_text = await page.inner_text('body')
        captcha_keywords = [
            'hcaptcha', 'recaptcha', 'captcha', 'challenge',
            'security check', 'verification', 'prove you are human',
            'verify you are not a robot'
        ]

        page_text_lower = page_text.lower()
        found_keywords = [kw for kw in captcha_keywords if kw in page_text_lower]
        if found_keywords:
            print(f"CAPTCHA-related text found: {found_keywords}")
            return True

        print("No CAPTCHA detected on this page")
        return False

    except Exception as e:
        print(f"Error detecting CAPTCHA: {e}")
        return False

async def extract_sitekey_from_frame(frame, depth=0):
    """Recursively extract hCaptcha sitekey from a frame and its child frames"""
    indent = "  " * depth
    try:
        # Method 1: Look for data-sitekey attributes in this frame
        hcaptcha_elements = frame.locator('[data-sitekey]')
        if await hcaptcha_elements.count() > 0:
            for i in range(await hcaptcha_elements.count()):
                element = hcaptcha_elements.nth(i)
                site_key = await element.get_attribute('data-sitekey')
                if site_key and len(site_key) == 36:  # hCaptcha site keys are UUIDs
                    print(f"{indent}Found hCaptcha site key: {site_key}")
                    return site_key

        # Method 2: Look for hCaptcha iframe URLs in this frame
        iframes = frame.locator('iframe[src*="hcaptcha"]')
        iframe_count = await iframes.count()
        for i in range(iframe_count):
            iframe = iframes.nth(i)
            src = await iframe.get_attribute('src')
            if src and 'sitekey=' in src:
                import re
                site_key_match = re.search(r'sitekey=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', src)
                if site_key_match:
                    site_key = site_key_match.group(1)
                    print(f"{indent}Found hCaptcha site key in iframe URL: {site_key}")
                    return site_key

        # Method 3: Look for iframes with hCaptcha data-id in this frame
        hcaptcha_iframes = frame.locator('iframe[data-id*="hcaptcha"]')
        iframe_count = await hcaptcha_iframes.count()
        for i in range(iframe_count):
            iframe = hcaptcha_iframes.nth(i)
            src = await iframe.get_attribute('src')
            if src and 'sitekey=' in src:
                import re
                site_key_match = re.search(r'sitekey=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', src)
                if site_key_match:
                    site_key = site_key_match.group(1)
                    print(f"{indent}Found hCaptcha site key in hCaptcha iframe URL: {site_key}")
                    return site_key

        # Recursively check child frames
        all_iframes = frame.locator('iframe')
        iframe_count = await all_iframes.count()
        for i in range(iframe_count):
            iframe = all_iframes.nth(i)
            try:
                element = await iframe.element_handle()
                child_frame = await element.content_frame()
            except Exception as e:
                print(f"{indent}Error getting content frame for iframe {i}: {e}")
                continue
            if child_frame:
                sitekey = await extract_sitekey_from_frame(child_frame, depth + 1)
                if sitekey:
                    return sitekey

        return None

    except Exception as e:
        print(f"{indent}Error extracting sitekey from frame: {e}")
        return None

async def extract_hcaptcha_sitekey(page):
    """Extract hCaptcha sitekey from the page"""
    try:
        # Start recursive extraction from the main frame
        return await extract_sitekey_from_frame(page, 0)

    except Exception as e:
        print(f"Error extracting hCaptcha site key: {e}")
        return None

def solve_hcaptcha(sitekey, page_url):
    """Solve hCaptcha using SolveCaptcha API"""
    if not SOLVECAPTCHA_API_KEY:
        print("No SolveCaptcha API key available")
        return None

    try:
        print(f"Solving hCaptcha with sitekey: {sitekey}")

        # Step 1: Send request to get captcha_id
        in_url = "https://api.solvecaptcha.com/in.php"
        payload = {
            'key': SOLVECAPTCHA_API_KEY,
            'method': 'hcaptcha',
            'sitekey': sitekey,
            'pageurl': page_url,
            'json': 1
        }

        print("Sending request to SolveCaptcha API...")
        response = requests.post(in_url, data=payload, timeout=30)
        result = response.json()

        if result.get("status") != 1:
            print(f"Error submitting CAPTCHA: {result.get('request')}")
            print(f"Full API response: {result}")
            return None

        captcha_id = result.get("request")
        print(f"Got captcha_id: {captcha_id}")

        # Step 2: Poll for solution
        res_url = "https://api.solvecaptcha.com/res.php"
        max_attempts = 60  # 5 minutes max

        for attempt in range(max_attempts):
            params = {
                'key': SOLVECAPTCHA_API_KEY,
                'action': 'get',
                'id': captcha_id,
                'json': 1
            }

            res = requests.get(res_url, params=params, timeout=10)
            data = res.json()

            if data.get("status") == 1:
                print("hCaptcha solved successfully!")
                token = data.get("request")
                user_agent = data.get("useragent")
                print(f"Token: {token[:50]}...")
                print(f"User-Agent: {user_agent}")
                return {
                    'token': token,
                    'user_agent': user_agent
                }
            elif data.get("request") == "CAPCHA_NOT_READY":
                print(f"hCaptcha not ready yet, waiting... (attempt {attempt + 1}/{max_attempts})")
                time.sleep(5)
            else:
                print(f"Error getting solution: {data.get('request')}")
                return None

        print("hCaptcha solving timed out")
        return None

    except Exception as e:
        print(f"Error solving hCaptcha: {e}")
        return None

async def set_captcha_token(page, token):
    """Set the CAPTCHA token in hidden fields"""
    try:
        # Check for and create hidden fields if needed
        await page.evaluate("""
            // Check for h-captcha-response field
            if (!document.querySelector('[name="h-captcha-response"]')) {
                var input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'h-captcha-response';
                document.body.appendChild(input);
            }

            // Check for g-recaptcha-response field (compatibility)
            if (!document.querySelector('[name="g-recaptcha-response"]')) {
                var input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'g-recaptcha-response';
                document.body.appendChild(input);
            }
        """)

        # Set the token in both fields
        await page.evaluate(f"""
            document.getElementsByName('h-captcha-response')[0].value = '{token}';
            document.getElementsByName('g-recaptcha-response')[0].value = '{token}';
        """)

        print("CAPTCHA token set successfully")

    except Exception as e:
        print(f"Error setting CAPTCHA token: {e}")

async def show_visual_feedback(page):
    """Show visual feedback that CAPTCHA is solved"""
    try:
        await page.evaluate("""
            var banner = document.createElement('div');
            banner.innerText = 'hCaptcha Solved by SolveCaptcha!';
            banner.style.position = 'fixed';
            banner.style.top = '0';
            banner.style.left = '0';
            banner.style.width = '100%';
            banner.style.backgroundColor = 'green';
            banner.style.color = 'white';
            banner.style.fontSize = '20px';
            banner.style.fontWeight = 'bold';
            banner.style.textAlign = 'center';
            banner.style.zIndex = '9999';
            banner.style.padding = '10px';
            document.body.appendChild(banner);

            // Auto-remove after 10 seconds
            setTimeout(function() {
                if (banner.parentNode) {
                    banner.parentNode.removeChild(banner);
                }
            }, 10000);
        """)
        print("Visual feedback shown")
    except Exception as e:
        print(f"Error showing visual feedback: {e}")

async def handle_cookie_consent(page):
    """Handle cookie consent popup"""
    try:
        print('Checking for cookie consent popup...')

        manage_selectors = [
            'button[data-testid*="manage"]',
            'button[id*="manage"]',
            '.fc-button[data-testid*="manage"]'
        ]

        manage_clicked = False
        for selector in manage_selectors:
            try:
                manage_button = page.locator(selector).first
                if await manage_button.is_visible(timeout=2000):
                    print(f"Found 'Manage Options' button with selector: {selector}")
                    await manage_button.click()
                    await asyncio.sleep(random.uniform(1, 2))
                    manage_clicked = True
                    break
            except Exception as e:
                print(f"Error with manage selector {selector}: {e}")
                continue

        if manage_clicked:
            print("Managing cookie preferences...")

            await asyncio.sleep(random.uniform(1, 2))

            # Uncheck consent checkboxes
            consent_checkboxes = page.locator('input.fc-preference-consent.purpose:checked')
            for i in range(await consent_checkboxes.count()):
                try:
                    await consent_checkboxes.nth(i).click()
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                except Exception as e:
                    print(f"Error unchecking consent checkbox {i}: {e}")

            # Confirm choices
            confirm_selectors = [
                '.fc-button.fc-confirm-choices.fc-primary-button',
                'button[data-testid*="confirm"]'
            ]

            for selector in confirm_selectors:
                try:
                    confirm_button = page.locator(selector).first
                    if await confirm_button.is_visible(timeout=2000):
                        await confirm_button.click()
                        await asyncio.sleep(random.uniform(2, 4))
                        print("Cookie preferences configured")
                        return
                except Exception as e:
                    print(f"Error with confirm selector {selector}: {e}")
                    continue

        print("No cookie consent popup found or handled")
    except Exception as e:
        print(f"Cookie consent handling error: {e}")

async def main():
    print("IAAI hCaptcha Solver using SolveCaptcha API")
    print("=" * 50)

    # Check API key
    if not SOLVECAPTCHA_API_KEY:
        print("ERROR: SOLVECAPTCHA_API_KEY not set!")
        print("Please set it in your .env file or environment variables")
        return

    # Load credentials
    USERNAME = os.environ.get('IAAI_USERNAME')
    PASSWORD = os.environ.get('IAAI_PASSWORD')

    if not USERNAME or not PASSWORD:
        print("Warning: IAAI credentials not found - will navigate to login page")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)  # Keep visible for debugging
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Navigate to IAAI dashboard
            print("Navigating to IAAI dashboard...")
            response = await page.goto("https://www.iaai.com/Dashboard/Default", timeout=60000)
            print(f"Response status: {response.status if response else 'No response'}")

            await page.wait_for_load_state('domcontentloaded', timeout=30000)
            await asyncio.sleep(3)  # Wait for dynamic content

            # Handle cookie consent
            await handle_cookie_consent(page)

            # Check for hCaptcha
            print("Checking for hCaptcha...")
            captcha_detected = await detect_captcha(page)

            if captcha_detected:
                print("hCaptcha detected - attempting to solve...")

                # Extract sitekey
                sitekey = await extract_hcaptcha_sitekey(page)
                if not sitekey:
                    print("Could not extract hCaptcha sitekey")
                    await asyncio.sleep(30)  # Keep browser open for manual solving
                    await browser.close()
                    return

                # Solve hCaptcha
                page_url = page.url
                print(f"Page URL for CAPTCHA: {page_url}")
                solution = solve_hcaptcha(sitekey, page_url)

                if solution:
                    token = solution['token']

                    # Set token in page
                    await set_captcha_token(page, token)

                    # Show visual feedback
                    await show_visual_feedback(page)

                    print("hCaptcha solved successfully!")
                    print("Token injected into page")

                    # Check if we're logged in or need to login
                    current_url = page.url
                    if "login.iaai.com" in current_url or "Identity/Account/Login" in current_url:
                        print("Still on login page - CAPTCHA may need manual submission")
                        print("Please complete the login process manually")
                    else:
                        print("Successfully bypassed CAPTCHA!")

                    # Keep browser open for 60 seconds
                    print("Browser will remain open for 60 seconds...")
                    await asyncio.sleep(60)

                else:
                    print("Failed to solve hCaptcha")
                    print("Please solve the CAPTCHA manually in the browser window")
                    await asyncio.sleep(60)  # Keep browser open for manual solving

            else:
                print("No hCaptcha detected on this page")
                print("Keeping browser open for 120 seconds for manual inspection...")
                print("Please check the browser window and provide CAPTCHA details")
                await asyncio.sleep(120)

        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())