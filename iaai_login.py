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
import requests

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

async def detect_incapsula_captcha(page):
    """Detect Incapsula CAPTCHA iframes specifically"""
    try:
        print("Checking for Incapsula CAPTCHA iframes...")

        # Incapsula-specific CAPTCHA iframe selectors
        incapsula_captcha_selectors = [
            'iframe[src*="incapsula"]',
            'iframe[id*="incapsula"]',
            'iframe[src*="challenge"]',
            'iframe[src*="captcha"]',
            'iframe[src*="recaptcha"]',
            'iframe[src*="hcaptcha"]',
            '.incapsula-challenge',
            '#incapsula-iframe',
            'iframe[title*="challenge"]',
            'iframe[title*="captcha"]'
        ]

        for selector in incapsula_captcha_selectors:
            try:
                iframe = page.locator(selector).first
                if await iframe.is_visible(timeout=2000):
                    src = await iframe.get_attribute('src')
                    print(f"Incapsula CAPTCHA iframe found: {selector}")
                    if src:
                        print(f"CAPTCHA iframe src: {src}")
                    return True
            except:
                continue

        # Check for Incapsula CAPTCHA text indicators
        page_text = await page.inner_text('body')
        incapsula_captcha_indicators = [
            "checking your browser",
            "please wait while we are checking",
            "security check in progress",
            "verifying your connection",
            "please complete the security check",
            "incapsula",
            "imperva"
        ]

        page_text_lower = page_text.lower()
        for indicator in incapsula_captcha_indicators:
            if indicator in page_text_lower:
                print(f"Incapsula CAPTCHA text detected: '{indicator}'")
                return True

        return False

    except Exception as e:
        print(f"Error detecting Incapsula CAPTCHA: {e}")
        return False

async def detect_captcha(page):
    """Detect if a CAPTCHA is present on the page"""
    try:
        print("Scanning page for CAPTCHA elements...")

        # First check for Incapsula blocks (more serious than CAPTCHAs)
        incapsula_detected = await detect_incapsula_block(page)
        if incapsula_detected:
            print("Incapsula WAF block detected - checking for Incapsula CAPTCHA iframes...")
            # Check for Incapsula-specific CAPTCHA iframes
            incapsula_captcha_found = await detect_incapsula_captcha(page)
            if incapsula_captcha_found:
                return "incapsula_captcha"
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

async def solve_captcha(page, captcha_type="standard"):
    """Attempt to solve CAPTCHA using 2Captcha service"""
    try:
        # Get CAPTCHA solving API key from environment
        api_key = os.environ.get('TWOCAPTCHA_API_KEY')
        if not api_key:
            print("No 2Captcha API key found. Set TWOCAPTCHA_API_KEY environment variable.")
            print("Get API key from: https://2captcha.com/")
            return False

        if captcha_type == "incapsula_captcha":
            print("Attempting to solve Incapsula CAPTCHA...")
            return await solve_incapsula_captcha(page, api_key)
        else:
            print("Attempting to solve standard CAPTCHA...")
            return await solve_standard_captcha(page, api_key)

    except Exception as e:
        print(f"Error solving CAPTCHA: {e}")
        return False

async def solve_standard_captcha(page, api_key):
    """Solve standard CAPTCHA types"""
    try:
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

        success = await solve_grid_captcha(page, captcha_element, task_text, captcha_base64, api_key)

        if success:
            print("CAPTCHA solved successfully!")
            return True
        else:
            print("CAPTCHA solving failed")
            return False

    except Exception as e:
        print(f"Error solving standard CAPTCHA: {e}")
        return False

async def solve_incapsula_captcha(page, api_key):
    """Solve Incapsula-specific CAPTCHAs"""
    try:
        print("Solving Incapsula CAPTCHA...")

        # First, try to detect if it's a reCAPTCHA or hCaptcha within Incapsula iframe
        captcha_info = await detect_captcha_in_iframe(page)

        if captcha_info:
            captcha_type, site_key, iframe_url = captcha_info
            print(f"Detected {captcha_type} in Incapsula iframe")

            if captcha_type in ['recaptcha', 'hcaptcha']:
                return await solve_recaptcha_captcha(page, api_key, site_key, iframe_url, captcha_type)
            else:
                print(f"Unsupported Incapsula CAPTCHA type: {captcha_type}")
                return False
        else:
            # Fallback: try to solve as image-based CAPTCHA
            print("No recognizable CAPTCHA type found in iframe, trying image-based solving...")
            return await solve_incapsula_image_captcha(page, api_key)

    except Exception as e:
        print(f"Error solving Incapsula CAPTCHA: {e}")
        return False

async def detect_captcha_in_iframe(page):
    """Detect CAPTCHA type within Incapsula iframe"""
    try:
        # Find Incapsula iframe
        iframe_selectors = [
            'iframe[src*="incapsula"]',
            'iframe[id*="incapsula"]',
            'iframe[src*="challenge"]',
            'iframe[src*="captcha"]'
        ]

        iframe_element = None
        iframe_url = None

        for selector in iframe_selectors:
            try:
                iframe = page.locator(selector).first
                if await iframe.is_visible(timeout=2000):
                    iframe_element = iframe
                    iframe_url = await iframe.get_attribute('src')
                    print(f"Found Incapsula iframe: {iframe_url}")
                    break
            except:
                continue

        if not iframe_element:
            return None

        # Try to detect reCAPTCHA
        try:
            recaptcha_element = page.locator('.g-recaptcha, [data-sitekey]').first
            if await recaptcha_element.is_visible(timeout=1000):
                site_key = await recaptcha_element.get_attribute('data-sitekey')
                if site_key:
                    return ('recaptcha', site_key, iframe_url)
        except:
            pass

        # Try to detect hCaptcha
        try:
            hcaptcha_element = page.locator('.h-captcha, [data-sitekey]').first
            if await hcaptcha_element.is_visible(timeout=1000):
                site_key = await hcaptcha_element.get_attribute('data-sitekey')
                if site_key:
                    return ('hcaptcha', site_key, iframe_url)
        except:
            pass

        return None

    except Exception as e:
        print(f"Error detecting CAPTCHA in iframe: {e}")
        return None

async def solve_recaptcha_captcha(page, api_key, site_key, page_url, captcha_type):
    """Solve reCAPTCHA or hCaptcha using 2Captcha"""
    try:
        print(f"Solving {captcha_type} with site key: {site_key}")

        # Submit to 2Captcha
        submit_url = "http://2captcha.com/in.php"
        submit_data = {
            'key': api_key,
            'method': 'userrecaptcha' if captcha_type == 'recaptcha' else 'hcaptcha',
            'sitekey': site_key,
            'pageurl': page_url or page.url,
            'json': 1
        }

        submit_response = requests.post(submit_url, data=submit_data, timeout=30)
        submit_result = submit_response.json()

        if submit_result.get('status') != 1:
            print(f"Failed to submit {captcha_type}: {submit_result}")
            return False

        task_id = submit_result['request']
        print(f"{captcha_type} submitted successfully. Task ID: {task_id}")

        # Poll for result
        result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
        max_attempts = 60

        for attempt in range(max_attempts):
            try:
                result_response = requests.get(result_url, timeout=10)
                result_data = result_response.json()

                if result_data.get('status') == 1:
                    token = result_data['request']
                    print(f"{captcha_type} solved! Token: {token[:50]}...")

                    # Inject the token into the page
                    if captcha_type == 'recaptcha':
                        await page.evaluate(f"""
                            document.querySelector('[name="g-recaptcha-response"]').value = '{token}';
                            if (window.grecaptcha) {{
                                grecaptcha.getResponse = function() {{ return '{token}'; }};
                            }}
                        """)
                    else:  # hcaptcha
                        await page.evaluate(f"""
                            document.querySelector('[name="h-captcha-response"]').value = '{token}';
                            if (window.hcaptcha) {{
                                hcaptcha.getResponse = function() {{ return '{token}'; }};
                            }}
                        """)

                    # Try to submit the form
                    submit_selectors = [
                        'button[type="submit"]',
                        '.captcha-submit',
                        'input[type="submit"]',
                        'button[id*="submit"]'
                    ]

                    for selector in submit_selectors:
                        try:
                            submit_btn = page.locator(selector).first
                            if await submit_btn.is_visible(timeout=2000):
                                await submit_btn.click()
                                print(f"Submitted {captcha_type} solution")
                                await asyncio.sleep(3)  # Wait for processing
                                return True
                        except:
                            continue

                    print(f"Could not find submit button for {captcha_type}")
                    return False

                elif result_data.get('request') == 'CAPCHA_NOT_READY':
                    print(f"{captcha_type} not ready yet, waiting... (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(1)
                    continue

                else:
                    print(f"{captcha_type} solving failed: {result_data}")
                    return False

            except Exception as e:
                print(f"Error polling {captcha_type} result: {e}")
                await asyncio.sleep(1)
                continue

        print(f"{captcha_type} solving timed out")
        return False

    except Exception as e:
        print(f"Error solving {captcha_type}: {e}")
        return False

async def solve_incapsula_image_captcha(page, api_key):
    """Solve Incapsula image-based CAPTCHAs"""
    try:
        print("Attempting to solve Incapsula image CAPTCHA...")

        # Look for image elements within Incapsula iframe
        image_selectors = [
            'img[src*="captcha"]',
            'img[alt*="captcha"]',
            '.captcha-image',
            'img[id*="challenge"]'
        ]

        captcha_image = None
        for selector in image_selectors:
            try:
                img = page.locator(selector).first
                if await img.is_visible(timeout=2000):
                    captcha_image = img
                    print(f"Found CAPTCHA image with selector: {selector}")
                    break
            except:
                continue

        if not captcha_image:
            print("Could not find Incapsula CAPTCHA image")
            return False

        # Take screenshot of the image
        try:
            captcha_screenshot = await captcha_image.screenshot(type='png')
            if not captcha_screenshot:
                print("Could not capture CAPTCHA image screenshot")
                return False
        except Exception as e:
            print(f"Error taking CAPTCHA image screenshot: {e}")
            return False

        # Convert to base64
        captcha_base64 = base64.b64encode(captcha_screenshot).decode('utf-8')

        # Submit to 2Captcha as base64 image
        submit_url = "http://2captcha.com/in.php"
        submit_data = {
            'key': api_key,
            'method': 'base64',
            'body': captcha_base64,
            'json': 1
        }

        submit_response = requests.post(submit_url, data=submit_data, timeout=30)
        submit_result = submit_response.json()

        if submit_result.get('status') != 1:
            print(f"Failed to submit Incapsula image CAPTCHA: {submit_result}")
            return False

        task_id = submit_result['request']
        print(f"Incapsula image CAPTCHA submitted successfully. Task ID: {task_id}")

        # Poll for result
        result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
        max_attempts = 60

        for attempt in range(max_attempts):
            try:
                result_response = requests.get(result_url, timeout=10)
                result_data = result_response.json()

                if result_data.get('status') == 1:
                    solution = result_data['request']
                    print(f"Incapsula image CAPTCHA solved! Solution: {solution}")

                    # Apply the solution (this depends on how Incapsula presents the input)
                    # Could be text input, coordinates, etc.
                    return await apply_incapsula_solution(page, solution)

                elif result_data.get('request') == 'CAPCHA_NOT_READY':
                    print(f"Incapsula CAPTCHA not ready yet, waiting... (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(1)
                    continue

                else:
                    print(f"Incapsula CAPTCHA solving failed: {result_data}")
                    return False

            except Exception as e:
                print(f"Error polling Incapsula CAPTCHA result: {e}")
                await asyncio.sleep(1)
                continue

        print("Incapsula CAPTCHA solving timed out")
        return False

    except Exception as e:
        print(f"Error solving Incapsula image CAPTCHA: {e}")
        return False

async def apply_incapsula_solution(page, solution):
    """Apply the Incapsula CAPTCHA solution"""
    try:
        # Try different input methods that Incapsula might use

        # Method 1: Text input field
        text_inputs = [
            'input[type="text"]',
            'input[name*="captcha"]',
            'input[id*="captcha"]',
            'input[name*="response"]',
            'input[id*="response"]'
        ]

        for selector in text_inputs:
            try:
                input_field = page.locator(selector).first
                if await input_field.is_visible(timeout=1000):
                    await input_field.fill(solution)
                    print(f"Filled text input with solution: {selector}")

                    # Try to submit
                    submit_selectors = [
                        'button[type="submit"]',
                        'input[type="submit"]',
                        'button[id*="submit"]',
                        '.submit-button'
                    ]

                    for submit_sel in submit_selectors:
                        try:
                            submit_btn = page.locator(submit_sel).first
                            if await submit_btn.is_visible(timeout=1000):
                                await submit_btn.click()
                                print("Submitted Incapsula CAPTCHA solution")
                                return True
                        except:
                            continue

                    break
            except:
                continue

        # Method 2: If it's coordinate-based (clicking on image)
        if ',' in solution:
            try:
                coordinates = [int(coord.strip()) for coord in solution.split(',')]
                # This would require knowing the image layout
                print("Coordinate-based solution detected but not implemented")
                return False
            except:
                pass

        print("Could not apply Incapsula CAPTCHA solution")
        return False

    except Exception as e:
        print(f"Error applying Incapsula solution: {e}")
        return False

async def solve_grid_captcha(page, captcha_element, task_text, image_base64, api_key):
    """Solve grid-based CAPTCHA (select specific images) using 2Captcha API"""
    try:
        print("Submitting CAPTCHA to 2Captcha service...")

        # Submit CAPTCHA task to 2Captcha
        submit_url = "http://2captcha.com/in.php"
        submit_data = {
            'key': api_key,
            'method': 'base64',
            'body': image_base64,
            'textinstructions': task_text,
            'json': 1
        }

        try:
            submit_response = requests.post(submit_url, data=submit_data, timeout=30)
            submit_result = submit_response.json()

            if submit_result.get('status') != 1:
                print(f"Failed to submit CAPTCHA: {submit_result}")
                return False

            task_id = submit_result['request']
            print(f"CAPTCHA submitted successfully. Task ID: {task_id}")

        except Exception as e:
            print(f"Error submitting CAPTCHA to 2Captcha: {e}")
            return False

        # Poll for result (up to 60 seconds)
        result_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={task_id}&json=1"
        max_attempts = 60

        for attempt in range(max_attempts):
            try:
                result_response = requests.get(result_url, timeout=10)
                result_data = result_response.json()

                if result_data.get('status') == 1:
                    solution = result_data['request']
                    print(f"CAPTCHA solved! Solution: {solution}")
                    # Apply the solution
                    return await apply_captcha_solution(page, captcha_element, solution)

                elif result_data.get('request') == 'CAPCHA_NOT_READY':
                    print(f"CAPTCHA not ready yet, waiting... (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(1)
                    continue

                else:
                    print(f"CAPTCHA solving failed: {result_data}")
                    return False

            except Exception as e:
                print(f"Error polling CAPTCHA result: {e}")
                await asyncio.sleep(1)
                continue

        print("CAPTCHA solving timed out")
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
        # Browser launch with minimal anti-detection measures (like monitor_simple.py)
        browser = await p.chromium.launch(
            headless=False  # Keep visible for debugging
        )

        # Create context similar to monitor_simple.py - minimal configuration to avoid detection
        context = await browser.new_context()

        page = await context.new_page()

        # Try to load saved session first (like monitor_simple.py)
        session_loaded = False
        try:
            if os.path.exists('iaai_session.json'):
                with open('iaai_session.json', 'r') as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                print('Session cookies loaded')
                session_loaded = True
        except Exception as e:
            print(f'Failed to load session cookies: {e}')

        try:
            # Navigate to IAAI dashboard first, which will redirect to login if not authenticated
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"Navigating to IAAI dashboard (attempt {attempt + 1}/{max_retries})...")
                    response = await page.goto("https://www.iaai.com/Dashboard/Default", timeout=60000)  # 2 minutes
                    print(f"Response status: {response.status if response else 'No response'}")
                    print("Waiting for page to load...")
                    await page.wait_for_load_state('domcontentloaded', timeout=30000)
                    # Wait a bit more for dynamic content and potential redirect
                    await asyncio.sleep(5)  # Increased wait time for CAPTCHA to load

                    # Check for CAPTCHA immediately after navigation
                    print("Checking for CAPTCHA on dashboard page...")
                    captcha_detected = await detect_captcha(page)
                    if captcha_detected:
                        print(f"CAPTCHA detected: {captcha_detected} - attempting to solve...")
                        captcha_solved = await solve_captcha(page, captcha_detected)
                        if captcha_solved:
                            print("CAPTCHA solved successfully!")
                            # Wait for page to reload after CAPTCHA
                            await asyncio.sleep(3)
                        else:
                            print("CAPTCHA solving failed - manual intervention required")
                            print("Please solve the CAPTCHA in the browser window")
                            await asyncio.sleep(120)  # 2 minutes for manual solving

                    # Check if we were redirected to login page
                    current_url = page.url
                    if "login.iaai.com" in current_url or "Identity/Account/Login" in current_url:
                        print("Successfully redirected to login page")
                        break
                    elif "dashboard" in current_url.lower() and "iaai.com" in current_url:
                        print("Already authenticated - staying on dashboard")
                        print("Checking for CAPTCHA iframes on dashboard...")

                        # Wait a bit more for dynamic content to load
                        await asyncio.sleep(5)

                        # Look for CAPTCHA iframes that might appear after login
                        captcha_iframes = page.locator('iframe')
                        iframe_count = await captcha_iframes.count()
                        print(f"Found {iframe_count} iframes on dashboard")

                        captcha_found = False
                        for i in range(iframe_count):
                            try:
                                iframe = captcha_iframes.nth(i)
                                src = await iframe.get_attribute('src')
                                if src and ('captcha' in src.lower() or 'challenge' in src.lower()):
                                    print(f"CAPTCHA iframe found: {src}")
                                    captcha_found = True
                                    break
                            except:
                                continue

                        if captcha_found:
                            print("CAPTCHA iframe detected on dashboard - manual intervention required")
                            print("Please solve the CAPTCHA in the browser window")
                            # Keep browser open for manual CAPTCHA solving
                            await asyncio.sleep(120)  # 2 minutes for manual solving
                        else:
                            print("No CAPTCHA iframes found on dashboard - login successful!")

                        break
                    else:
                        print(f"Unexpected URL after dashboard navigation: {current_url}")
                        # If we're not on login page or dashboard, try direct navigation to login
                        if attempt == max_retries - 1:
                            print("Trying direct navigation to login page...")
                            response = await page.goto("https://login.iaai.com/Identity/Account/Login", timeout=60000)
                            await page.wait_for_load_state('domcontentloaded', timeout=30000)
                            await asyncio.sleep(2)
                        break

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

            # Check if this is an OAuth redirect page
            current_url = page.url
            if '/connect/authorize' in current_url:
                print("Detected OAuth authorization page, waiting for redirect to login form...")
                # Wait for redirect to actual login form
                try:
                    await page.wait_for_url(lambda url: '/connect/authorize' not in url and 'login' in url, timeout=10000)
                    print(f"Redirected to login form: {page.url}")
                    # Re-check content after redirect
                    content = await page.content()
                    print(f'Page content length after redirect: {len(content)}')
                    if 'email' in content.lower():
                        print("Email field found after redirect")
                    else:
                        print("Email field still not found after redirect")
                except Exception as e:
                    print(f"No redirect to login form occurred: {e}")
                    print("OAuth flow may require different handling")

            # Handle cookie consent if present (like monitor_simple.py)
            print('Checking for cookie consent popup...')
            try:
                # Step 1: Look for "Manage Options" button to open detailed preferences
                manage_options_selectors = [
                    'button[data-testid*="manage"]',
                    'button[id*="manage"]',
                    '.fc-button[data-testid*="manage"]'
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
                    except Exception as e:
                        print(f"Error with manage selector {selector}: {e}")
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
                        'button[data-testid*="confirm"]'
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
                        except Exception as e:
                            print(f"Error with confirm selector {selector}: {e}")
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
                print(f"Cookie consent handling error: {e}")

            # Wait for the login form to load (dynamic elements)
            await page.wait_for_selector('input[name="Input.Email"]', timeout=62000)

            # Fill login form (simplified approach like monitor_simple.py)
            print('Filling login form...')
            await page.click('input[name="Input.Email"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.fill('input[name="Input.Email"]', USERNAME)
            await asyncio.sleep(random.uniform(2, 5))

            await page.click('input[name="Input.Password"]')
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.fill('input[name="Input.Password"]', PASSWORD)
            await asyncio.sleep(random.uniform(2, 5))

            # Submit login (simplified approach like monitor_simple.py)
            print('Submitting login...')
            login_btn = page.locator('button[type="submit"]').first
            await login_btn.hover()
            await asyncio.sleep(random.uniform(3, 5))
            await login_btn.click(timeout=random.randint(10000, 30000))

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
                    print("Login successful!")
                    print(f'Current URL: {current_url}')

                    # Check if we're on dashboard and look for CAPTCHA iframes
                    if "dashboard" in current_url.lower() or "iaai.com" in current_url:
                        print("On dashboard page, checking for CAPTCHA iframes...")

                        # Look for CAPTCHA iframes that might appear after login
                        captcha_iframes = page.locator('iframe')
                        iframe_count = await captcha_iframes.count()
                        print(f"Found {iframe_count} iframes on dashboard")

                        captcha_found = False
                        for i in range(iframe_count):
                            try:
                                iframe = captcha_iframes.nth(i)
                                src = await iframe.get_attribute('src')
                                if src and ('captcha' in src.lower() or 'challenge' in src.lower()):
                                    print(f"CAPTCHA iframe found: {src}")
                                    captcha_found = True
                                    break
                            except:
                                continue

                        if captcha_found:
                            print("CAPTCHA iframe detected on dashboard - manual intervention required")
                            print("Please solve the CAPTCHA in the browser window")
                            # Keep browser open for manual CAPTCHA solving
                            await asyncio.sleep(120)  # 2 minutes for manual solving
                        else:
                            print("No CAPTCHA iframes found on dashboard")

                    # Add pause after login before navigating (like monitor_simple.py)
                    print('Pausing after login to appear more human-like...')
                    await asyncio.sleep(random.uniform(5, 10))

                    # Save session cookies for future use (like monitor_simple.py)
                    try:
                        cookies = await context.cookies()
                        with open('iaai_session.json', 'w') as f:
                            json.dump(cookies, f, indent=2)
                        print('Session cookies saved')
                    except Exception as e:
                        print(f'Failed to save session cookies: {e}')

                else:
                    print("Login may have failed. Check for errors.")

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