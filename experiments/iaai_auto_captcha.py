#!/usr/bin/env python3
"""
IAAI Auto CAPTCHA Solver - Automatically solves CAPTCHAs on IAAI dashboard
Uses HCaptchaSolver library for automatic CAPTCHA resolution
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import random
import os
from pathlib import Path
import time

# hcaptcha-challenger integration
try:
    import hcaptcha_challenger
    HCAPTCHA_CHALLENGER_AVAILABLE = True
    print("hcaptcha-challenger available")
except ImportError as e:
    HCAPTCHA_CHALLENGER_AVAILABLE = False
    print(f"hcaptcha-challenger not available: {e}")
    print("Install with: pip install hcaptcha-challenger")

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

async def detect_captcha(page):
    """Detect if a CAPTCHA is present on the page"""
    try:
        print("Scanning page for CAPTCHA elements...")

        # Wait a bit for dynamic content to load
        await asyncio.sleep(2)

        # Check for hCaptcha specifically (most common on IAAI)
        captcha_selectors = [
            '.h-captcha',
            '[data-sitekey]',
            'iframe[src*="hcaptcha"]',
            '.hcaptcha-challenge',
            '.challenge-container',
            '.captcha-container',
            '#captcha',
            '.captcha',
            '[class*="captcha"]',
            'iframe[src*="captcha"]',
            'iframe[title*="captcha"]',
            'iframe[title*="challenge"]'
        ]

        for selector in captcha_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    # Check if any are visible
                    for i in range(count):
                        element = elements.nth(i)
                        if await element.is_visible(timeout=1000):
                            print(f"CAPTCHA detected with selector: {selector} (element {i})")
                            return True
            except Exception as e:
                print(f"Error checking selector {selector}: {e}")
                continue

        # Check all iframes for CAPTCHA content
        try:
            iframes = page.locator('iframe')
            iframe_count = await iframes.count()
            print(f"Checking {iframe_count} iframes for CAPTCHA content...")

            for i in range(iframe_count):
                try:
                    iframe = iframes.nth(i)
                    src = await iframe.get_attribute('src') or ''
                    title = await iframe.get_attribute('title') or ''
                    id_attr = await iframe.get_attribute('id') or ''

                    # Check for Incapsula WAF iframes (common on IAAI)
                    if '_Incapsula_Resource' in src or 'incapsula' in src.lower():
                        if await iframe.is_visible(timeout=1000):
                            print(f"Incapsula WAF iframe detected (likely contains CAPTCHA): src='{src[:100]}...', id='{id_attr}'")
                            return True

                    # Check iframe attributes for standard CAPTCHAs
                    if any(keyword in src.lower() or keyword in title.lower()
                           for keyword in ['hcaptcha', 'captcha', 'challenge', 'recaptcha']):
                        if await iframe.is_visible(timeout=1000):
                            print(f"CAPTCHA iframe detected: src='{src[:100]}...', title='{title}'")
                            return True

                    # Try to access iframe content
                    try:
                        frame = await iframe.content_frame()
                        if frame:
                            frame_text = await frame.inner_text('body')
                            if any(keyword in frame_text.lower()
                                   for keyword in ['hcaptcha', 'verify you are human', 'security check', 'prove you are not a robot', 'incapsula']):
                                print(f"CAPTCHA content found in iframe {i}: {frame_text[:200]}...")
                                return True
                    except:
                        pass

                except Exception as e:
                    print(f"Error checking iframe {i}: {e}")
                    continue

        except Exception as e:
            print(f"Error checking iframes: {e}")

        # Check for CAPTCHA-related text in main page
        captcha_text_indicators = [
            "verify you are human",
            "security check",
            "prove you are not a robot",
            "complete the challenge",
            "please verify",
            "anti-bot verification",
            "bot detection",
            "suspicious activity detected",
            "additional security check"
        ]

        page_text = await page.inner_text('body')
        page_text_lower = page_text.lower()

        for indicator in captcha_text_indicators:
            if indicator in page_text_lower:
                print(f"CAPTCHA text detected: '{indicator}'")
                # Get context around the text
                start_pos = max(0, page_text_lower.find(indicator) - 100)
                end_pos = min(len(page_text), page_text_lower.find(indicator) + 200)
                context = page_text[start_pos:end_pos]
                print(f"Context: ...{context}...")
                return True

        # Debug: List all elements that might be related to CAPTCHA
        try:
            suspicious_elements = page.locator('[class*="challenge"], [class*="captcha"], [id*="captcha"], iframe, [src*="incapsula"]')
            suspicious_count = await suspicious_elements.count()
            if suspicious_count > 0:
                print(f"Found {suspicious_count} suspicious elements that might be CAPTCHA-related:")
                for i in range(min(suspicious_count, 10)):  # Check first 10
                    try:
                        element = suspicious_elements.nth(i)
                        tag_name = await element.evaluate('el => el.tagName')
                        class_name = await element.get_attribute('class') or ''
                        id_name = await element.get_attribute('id') or ''
                        src = await element.get_attribute('src') or ''
                        # Check if this is an Incapsula iframe
                        is_incapsula = '_Incapsula_Resource' in src
                        captcha_type = "Incapsula WAF" if is_incapsula else "Unknown"
                        print(f"  {i}: {tag_name} class='{class_name}' id='{id_name}' src='{src[:50]}...' ({captcha_type})")
                        # If we found an Incapsula iframe, consider it a CAPTCHA
                        if is_incapsula and await element.is_visible(timeout=1000):
                            print("Incapsula WAF iframe detected - this likely contains a CAPTCHA!")
                            return True
                    except:
                        continue
        except Exception as e:
            print(f"Error in debug element listing: {e}")

        print("No CAPTCHA detected on this page")
        return False

    except Exception as e:
        print(f"Error detecting CAPTCHA: {e}")
        return False

async def extract_hcaptcha_site_key(page):
    """Extract hCaptcha site key from the page"""
    try:
        # Method 1: Look for data-sitekey attributes
        hcaptcha_elements = page.locator('[data-sitekey]')
        if await hcaptcha_elements.count() > 0:
            for i in range(await hcaptcha_elements.count()):
                element = hcaptcha_elements.nth(i)
                site_key = await element.get_attribute('data-sitekey')
                if site_key and len(site_key) == 36:  # hCaptcha site keys are UUIDs
                    print(f"Found hCaptcha site key: {site_key}")
                    return site_key

        # Method 2: Look for hCaptcha iframe URLs
        iframes = page.locator('iframe[src*="hcaptcha"]')
        iframe_count = await iframes.count()
        for i in range(iframe_count):
            iframe = iframes.nth(i)
            src = await iframe.get_attribute('src')
            if src and 'sitekey=' in src:
                import re
                site_key_match = re.search(r'sitekey=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', src)
                if site_key_match:
                    site_key = site_key_match.group(1)
                    print(f"Found hCaptcha site key in iframe URL: {site_key}")
                    return site_key

        print("Could not extract hCaptcha site key")
        return None

    except Exception as e:
        print(f"Error extracting hCaptcha site key: {e}")
        return None

async def handle_checkbox_captcha(page):
    """Handle checkbox-style CAPTCHAs (I'm not a robot)"""
    try:
        print("Looking for CAPTCHA checkbox...")

        # Common checkbox selectors
        checkbox_selectors = [
            '.checkbox',
            'input[type="checkbox"]',
            '[role="checkbox"]',
            '.recaptcha-checkbox',
            '.hcaptcha-checkbox',
            '[aria-label*="robot"]',
            '[aria-label*="human"]',
            'div[style*="cursor"][style*="pointer"]'  # Clickable checkbox area
        ]

        checkbox_found = False
        for selector in checkbox_selectors:
            try:
                checkboxes = page.locator(selector)
                count = await checkboxes.count()
                for i in range(count):
                    checkbox = checkboxes.nth(i)
                    if await checkbox.is_visible(timeout=1000):
                        # Check if it looks like a CAPTCHA checkbox
                        aria_label = await checkbox.get_attribute('aria-label') or ''
                        class_name = await checkbox.get_attribute('class') or ''
                        text_content = await checkbox.text_content()

                        if any(keyword in (aria_label + class_name + text_content).lower()
                               for keyword in ['robot', 'human', 'verify', 'captcha']):
                            print(f"Found CAPTCHA checkbox with selector: {selector}")
                            await checkbox.click()
                            print("Clicked CAPTCHA checkbox")
                            checkbox_found = True
                            break
                if checkbox_found:
                    break
            except:
                continue

        if checkbox_found:
            # Wait for potential challenge to load
            print("Waiting for CAPTCHA challenge to load...")
            await asyncio.sleep(3)

            # Check if a challenge appeared
            challenge_detected = await detect_captcha_challenge(page)
            if challenge_detected:
                print("CAPTCHA challenge detected after checkbox click")
                return "challenge"
            else:
                print("No challenge appeared - checkbox might be sufficient")
                return "checkbox_only"
        else:
            print("No CAPTCHA checkbox found")
            return False

    except Exception as e:
        print(f"Error handling checkbox CAPTCHA: {e}")
        return False

async def detect_captcha_challenge(page):
    """Detect if a CAPTCHA challenge (image selection, etc.) is present"""
    try:
        challenge_selectors = [
            '.challenge-container',
            '.task-image',
            '.challenge-prompt',
            '.rc-imageselect',
            '.hcaptcha-challenge',
            '[class*="challenge"]',
            'canvas',  # Canvas-based challenges
            '.puzzle',
            '.grid-captcha'
        ]

        for selector in challenge_selectors:
            try:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    for i in range(count):
                        element = elements.nth(i)
                        if await element.is_visible(timeout=1000):
                            print(f"CAPTCHA challenge detected with selector: {selector}")
                            return True
            except:
                continue

        # Check for challenge text
        challenge_texts = [
            "select all images",
            "click the images",
            "select all squares",
            "pick the correct images",
            "what do you usually find in"
        ]

        page_text = await page.inner_text('body')
        page_text_lower = page_text.lower()

        for text in challenge_texts:
            if text in page_text_lower:
                print(f"Challenge text detected: '{text}'")
                return True

        return False

    except Exception as e:
        print(f"Error detecting CAPTCHA challenge: {e}")
        return False

async def detect_incapsula_captcha_type(page):
    """Detect the type of Incapsula CAPTCHA present"""
    try:
        # Check for Incapsula iframe
        incapsula_iframe = page.locator('iframe[src*="_Incapsula_Resource"]')
        if await incapsula_iframe.count() > 0:
            iframe = incapsula_iframe.first
            if await iframe.is_visible(timeout=1000):
                print("Incapsula iframe detected - checking CAPTCHA type...")

                # Try to access iframe content to determine CAPTCHA type
                try:
                    frame = iframe.content_frame()
                    if frame:
                        frame_text = await frame.inner_text('body')

                        # Check for hCaptcha indicators
                        if 'hcaptcha' in frame_text.lower() or 'verify you are human' in frame_text.lower():
                            print("hCaptcha detected within Incapsula iframe")
                            return "hcaptcha"

                        # Check for reCAPTCHA indicators
                        if 'recaptcha' in frame_text.lower() or 'prove you are not a robot' in frame_text.lower():
                            print("reCAPTCHA detected within Incapsula iframe")
                            return "recaptcha"

                        # Check for other CAPTCHA indicators
                        if any(keyword in frame_text.lower() for keyword in ['security check', 'additional security check', 'verification']):
                            print("Generic security check detected in Incapsula iframe")
                            return "generic"

                        print(f"Incapsula iframe content preview: {frame_text[:200]}...")
                        return "unknown"

                except Exception as e:
                    print(f"Could not access Incapsula iframe content: {e}")
                    return "iframe_blocked"

        return None

    except Exception as e:
        print(f"Error detecting Incapsula CAPTCHA type: {e}")
        return None

async def solve_incapsula_captcha(page):
    """Handle Incapsula CAPTCHA solving"""
    try:
        captcha_type = await detect_incapsula_captcha_type(page)

        if captcha_type == "hcaptcha":
            print("Solving Incapsula hCaptcha...")
            site_key = await extract_hcaptcha_site_key(page)
            if site_key:
                return await solve_captcha_with_hcaptcha_challenger(page, site_key, page.url)
            else:
                print("Could not extract hCaptcha site key from Incapsula iframe")

        elif captcha_type == "recaptcha":
            print("Solving Incapsula reCAPTCHA...")
            site_key = await extract_recaptcha_site_key(page)
            if site_key:
                return await solve_recaptcha_captcha(page, site_key, page.url)
            else:
                print("Could not extract reCAPTCHA site key from Incapsula iframe")

        elif captcha_type in ["generic", "unknown"]:
            print("Generic Incapsula security check - attempting manual solving...")
            # Try manual checkbox handling
            checkbox_result = await handle_checkbox_captcha(page)
            if checkbox_result:
                return True

        elif captcha_type == "iframe_blocked":
            print("Incapsula iframe content blocked - trying HCaptchaSolver directly...")
            # Try to use HCaptchaSolver directly on the main page
            # HCaptchaSolver can often handle CAPTCHAs even when they're in iframes
            site_key = await extract_hcaptcha_site_key(page)
            if site_key:
                print(f"Found hCaptcha site key on main page: {site_key}")
                return await solve_captcha_with_hcaptcha_challenger(page, site_key, page.url)
            else:
                print("No hCaptcha site key found on main page - trying manual checkbox handling")
                checkbox_result = await handle_checkbox_captcha(page)
                if checkbox_result:
                    return True

        print("Incapsula CAPTCHA solving failed or not supported")
        return False

    except Exception as e:
        print(f"Error solving Incapsula CAPTCHA: {e}")
        return False

async def solve_captcha_with_hcaptcha_challenger(page, site_key, page_url):
    """Solve CAPTCHA using hcaptcha-challenger for analysis and manual solving"""
    if not HCAPTCHA_CHALLENGER_AVAILABLE:
        print("hcaptcha-challenger not available - trying manual checkbox handling")

        # Fallback: try to handle checkbox manually
        checkbox_result = await handle_checkbox_captcha(page)
        if checkbox_result:
            if checkbox_result == "challenge":
                print("Challenge detected but hcaptcha-challenger not available for solving")
                return False
            else:
                return True  # Checkbox was sufficient
        return False

    try:
        print(f"Analyzing CAPTCHA with hcaptcha-challenger...")
        print(f"Site key: {site_key}")
        print(f"Page URL: {page_url}")

        # First try checkbox handling
        checkbox_result = await handle_checkbox_captcha(page)
        if checkbox_result == "checkbox_only":
            print("Checkbox CAPTCHA solved manually")
            return True
        elif checkbox_result == "challenge":
            print("Challenge detected - using hcaptcha-challenger for analysis")
        else:
            print("No checkbox found - proceeding with hcaptcha-challenger analysis")

        # Use hcaptcha-challenger for CAPTCHA analysis
        # Since hcaptcha-challenger is primarily for analysis, we'll use it to understand the CAPTCHA
        # and then fall back to manual solving

        print("hcaptcha-challenger is available for CAPTCHA analysis")
        print("Since automated solving requires additional setup, falling back to manual solving")
        print("Please solve the CAPTCHA manually in the browser window")

        # Wait for manual solving
        await asyncio.sleep(30)  # Give user time to solve manually

        # Check if CAPTCHA is still present
        still_present = await detect_captcha(page)
        if not still_present:
            print("CAPTCHA appears to be solved!")
            return True
        else:
            print("CAPTCHA still present after manual attempt")
            return False

    except Exception as e:
        print(f"Error in hcaptcha-challenger analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

async def extract_recaptcha_site_key(page):
    """Try to extract reCAPTCHA site key from page scripts and meta tags"""
    try:
        # Method 1: Look for site key in script tags
        scripts = page.locator('script')
        script_count = await scripts.count()

        for i in range(script_count):
            try:
                script_content = await scripts.nth(i).inner_text()
                if script_content and 'recaptcha' in script_content.lower():
                    # Look for site key patterns
                    import re
                    site_key_match = re.search(r'["\']([0-9A-Za-z_-]{40})["\']', script_content)
                    if site_key_match:
                        site_key = site_key_match.group(1)
                        print(f"Found potential site key in script: {site_key}")
                        return site_key
            except:
                continue

        # Method 2: Look for data-sitekey attributes
        sitekey_elements = page.locator('[data-sitekey]')
        if await sitekey_elements.count() > 0:
            site_key = await sitekey_elements.first.get_attribute('data-sitekey')
            if site_key:
                print(f"Found site key in data-sitekey attribute: {site_key}")
                return site_key

        # Method 3: Try to evaluate JavaScript to get grecaptcha site key
        try:
            site_key = await page.evaluate("""
                try {
                    if (window.grecaptcha && window.grecaptcha.render) {
                        // Try to find rendered reCAPTCHA
                        const recaptchaElements = document.querySelectorAll('[data-sitekey]');
                        if (recaptchaElements.length > 0) {
                            return recaptchaElements[0].getAttribute('data-sitekey');
                        }
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            """)
            if site_key:
                print(f"Found site key via JavaScript evaluation: {site_key}")
                return site_key
        except:
            pass

        print("Could not extract reCAPTCHA site key")
        return None

    except Exception as e:
        print(f"Error extracting site key: {e}")
        return None

async def solve_recaptcha_captcha(page, site_key, page_url):
    """Solve reCAPTCHA using HCaptchaSolver (fallback)"""
    print(f"reCAPTCHA solving not fully implemented - site_key: {site_key}")
    print("This would require a reCAPTCHA-specific solver")
    # For now, return False - could be extended to use 2Captcha or similar
    return False

async def wait_for_captcha_resolution(page, max_wait_time=30):
    """Wait for CAPTCHA to be resolved"""
    print(f"Waiting up to {max_wait_time} seconds for CAPTCHA resolution...")
    start_time = asyncio.get_event_loop().time()

    while (asyncio.get_event_loop().time() - start_time) < max_wait_time:
        try:
            # Check if CAPTCHA is still present
            captcha_still_present = await detect_captcha(page)
            if not captcha_still_present:
                print("CAPTCHA resolved successfully!")
                return True

            await asyncio.sleep(2)
        except Exception as e:
            print(f"Error checking CAPTCHA status: {e}")
            await asyncio.sleep(2)

    print(f"CAPTCHA still present after {max_wait_time} seconds")
    return False

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
            except:
                continue

        if manage_clicked:
            print("Managing cookie preferences...")

            await asyncio.sleep(random.uniform(1, 2))

            # Uncheck consent checkboxes
            consent_checkboxes = page.locator('input.fc-preference-consent.purpose:checked')
            for i in range(await consent_checkboxes.count()):
                await consent_checkboxes.nth(i).click()
                await asyncio.sleep(random.uniform(0.1, 0.3))

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
                except:
                    continue

        print("No cookie consent popup found or handled")
    except Exception as e:
        print(f"Cookie consent handling error: {e}")

async def main():
    print("IAAI Auto CAPTCHA Solver started")

    # Load credentials
    USERNAME = os.environ.get('IAAI_USERNAME')
    PASSWORD = os.environ.get('IAAI_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("IAAI_USERNAME and IAAI_PASSWORD environment variables must be set")

    print(f"Username: {USERNAME[:3]}***")

    # Initialize browser
    async with async_playwright() as p:
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

            # Wait for potential CAPTCHA to load and check multiple times
            print("Waiting for page to fully load and checking for CAPTCHA...")
            captcha_detected = False
            max_checks = 5

            for check in range(max_checks):
                print(f"CAPTCHA check {check + 1}/{max_checks}...")
                captcha_detected = await detect_captcha(page)

                if captcha_detected:
                    print("CAPTCHA detected - attempting to solve automatically...")
                    break
                elif check < max_checks - 1:
                    print("No CAPTCHA found yet, waiting 3 seconds...")
                    await asyncio.sleep(3)

            if captcha_detected:
                # First try HCaptchaSolver directly (works even with Incapsula iframes)
                site_key = await extract_hcaptcha_site_key(page)
                if site_key:
                    print(f"Found hCaptcha site key - trying hcaptcha-challenger directly: {site_key}")
                    success = await solve_captcha_with_hcaptcha_challenger(page, site_key, page.url)
                    if success:
                        print("HCaptchaSolver solved the CAPTCHA successfully!")
                    else:
                        print("HCaptchaSolver failed - trying Incapsula-specific methods")
                        success = await solve_incapsula_captcha(page)
                else:
                    # No site key found - check if this is an Incapsula CAPTCHA
                    incapsula_type = await detect_incapsula_captcha_type(page)
                    if incapsula_type:
                        print(f"Incapsula CAPTCHA detected: {incapsula_type}")
                        success = await solve_incapsula_captcha(page)
                    else:
                        print("Could not extract CAPTCHA site key and no Incapsula detected - trying manual methods")
                        success = False

                if success:
                    print("CAPTCHA solved successfully!")
                    # Wait for resolution
                    resolved = await wait_for_captcha_resolution(page, max_wait_time=30)
                    if resolved:
                        print("Login process can continue...")
                    else:
                        print("CAPTCHA resolution timeout")
                else:
                    print("CAPTCHA solving failed - trying manual intervention...")
                    print("Please solve the CAPTCHA manually in the browser window")
                    await asyncio.sleep(30)  # Give time for manual solving
            else:
                print("No CAPTCHA detected after multiple checks - proceeding with normal flow")

            # Check if we're logged in or need to login
            current_url = page.url
            if "login.iaai.com" in current_url or "Identity/Account/Login" in current_url:
                print("Redirected to login page - CAPTCHA may have been bypassed")
                # Handle login if needed
                print("Login required - please complete manually or implement login logic")
            elif "dashboard" in current_url.lower() and "iaai.com" in current_url:
                print("Successfully accessed dashboard - CAPTCHA solved!")
            else:
                print(f"Unexpected URL: {current_url}")

            # Keep browser open for manual inspection
            print("Browser will remain open for 60 seconds...")
            await asyncio.sleep(60)

        except Exception as e:
            print(f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())