#!/usr/bin/env python3
"""
Copart Bid Script
This script automates bidding on a Copart lot by:
1. Taking a lot number as parameter
2. Navigating to the lot page
3. Finding current bid and bid increment
4. Calculating and placing a bid (current + increment)
5. Staying on the page
"""

import argparse
import asyncio
import json
import os
import random
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

def load_env():
    """Load environment variables from .env file"""
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

async def login_to_copart(page, context):
    """Login to Copart using credentials from environment variables"""
    USERNAME = os.environ.get('COPART_USERNAME')
    PASSWORD = os.environ.get('COPART_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("COPART_USERNAME and COPART_PASSWORD environment variables must be set")

    print("Logging in to Copart...")

    # Navigate to login page
    await page.goto("https://www.copart.com/login", timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Handle cookie consent if present
    try:
        # Try to find and click manage options
        manage_selectors = [
            'button[data-testid*="manage"]',
            'button:contains("Manage")',
            '.fc-button[data-testid*="manage"]'
        ]
        for selector in manage_selectors:
            try:
                manage_btn = page.locator(selector).first
                if await manage_btn.is_visible(timeout=2000):
                    await manage_btn.click()
                    await asyncio.sleep(random.uniform(1, 2))
                    break
            except:
                continue

        # Uncheck consent checkboxes
        consent_checkboxes = page.locator('input.fc-preference-consent.purpose:checked')
        for i in range(await consent_checkboxes.count()):
            await consent_checkboxes.nth(i).click()
            await asyncio.sleep(random.uniform(0.1, 0.3))

        # Confirm choices
        confirm_selectors = ['.fc-button.fc-confirm-choices', 'button:contains("Confirm")']
        for selector in confirm_selectors:
            try:
                confirm_btn = page.locator(selector).first
                if await confirm_btn.is_visible(timeout=2000):
                    await confirm_btn.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    break
            except:
                continue
    except Exception as e:
        print(f"Cookie consent handling: {e}")

    # Wait for login form
    await page.wait_for_selector('input[name="username"]', timeout=62000)

    # Fill login form
    await page.click('input[name="username"]')
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await page.fill('input[name="username"]', USERNAME)
    await asyncio.sleep(random.uniform(2, 5))

    await page.click('input[name="password"]')
    await asyncio.sleep(random.uniform(0.5, 1.5))
    await page.fill('input[name="password"]', PASSWORD)
    await asyncio.sleep(random.uniform(2, 5))

    # Submit login
    login_btn = page.locator('button[data-uname="loginSigninmemberbutton"]').first
    await login_btn.hover()
    await asyncio.sleep(random.uniform(3, 5))
    await login_btn.click(timeout=random.randint(10000, 30000))

    # Wait for login success
    await page.wait_for_url(lambda url: url != "https://www.copart.com/login", timeout=30000)
    print("Login successful!")

    # Save session cookies for future use
    try:
        cookies = await context.cookies()
        with open('copart_session.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        print('Session cookies saved')
    except Exception as e:
        print(f'Failed to save session cookies: {e}')

def extract_amount(text):
    """Extract numeric amount from text (e.g., '$1,250.00' or '($50.00 Bid increment)' -> 1250.00)"""
    if not text:
        return 0.0

    # Look for dollar amount patterns like $50.00 or ($50.00)
    dollar_match = re.search(r'\$([0-9,]+\.?\d*)', text.strip())
    if dollar_match:
        try:
            # Remove commas and convert to float
            amount_str = dollar_match.group(1).replace(',', '')
            return float(amount_str)
        except ValueError:
            pass

    # Fallback: Remove $ and commas, then convert to float
    cleaned = re.sub(r'[$,]', '', text.strip())
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

async def place_bid_on_lot(page, lot_number):
    """Navigate to lot page and place a bid"""
    lot_url = f"https://www.copart.com/lot/{lot_number}"
    print(f"Navigating to lot: {lot_url}")

    await page.goto(lot_url, timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Wait a bit for dynamic content
    await asyncio.sleep(3)

    # Find current bid
    current_bid = 0.0
    current_bid_selectors = [
        '.current-bid-amount',
        '.current-bid',
        '.bid-amount',
        '.currentBid',
        '[data-uname*="currentBid"]',
        '.bid-price',
        'span:contains("Current Bid") + span',
        '.lot-current-bid'
    ]

    for selector in current_bid_selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                text = await elem.text_content()
                current_bid = extract_amount(text)
                if current_bid > 0:
                    print(f"Found current bid: ${current_bid:.2f}")
                    break
        except:
            continue

    if current_bid == 0:
        print("Warning: Could not find current bid amount")

    # Find bid increment
    bid_increment = 0.0
    increment_selectors = [
        '.dynamic-bid-inc',
        '.bid-increment',
        '.minimum-bid-increment',
        '.bidIncrement',
        '[data-uname*="increment"]',
        '.increment-amount'
    ]

    for selector in increment_selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                text = await elem.text_content()
                print(f"Found element with selector '{selector}': '{text}'")
                bid_increment = extract_amount(text)
                print(f"Extracted bid increment: ${bid_increment:.2f}")
                if bid_increment > 0:
                    print(f"Using bid increment: ${bid_increment:.2f}")
                    break
        except Exception as e:
            print(f"Error with selector '{selector}': {e}")
            continue

    if bid_increment == 0:
        print("Warning: Could not find bid increment on the page")
        print("Cannot proceed with bidding without knowing the increment amount")
        return False

    # Calculate new bid (round to whole dollars)
    new_bid = round(current_bid + bid_increment)
    print(f"Calculated new bid: ${new_bid}")

    # Find bid input field
    bid_input_selectors = [
        'input#your-max-bid',
        'input[name="maxBid"]',
        '.bid_amount_input',
        'input[name="bidAmount"]',
        'input#bidAmount',
        'input.bid-input',
        'input[data-uname*="bid"]',
        '.bid-input input',
        'input[placeholder*="bid"]',
        'input[placeholder*="Bid"]'
    ]

    bid_input = None
    for selector in bid_input_selectors:
        try:
            input_elem = page.locator(selector).first
            if await input_elem.is_visible(timeout=2000):
                bid_input = input_elem
                print(f"Found bid input with selector: {selector}")
                break
        except:
            continue

    if not bid_input:
        print("Error: Could not find bid input field")
        return False

    # Clear and fill bid input
    await bid_input.click()
    await bid_input.fill('')
    await asyncio.sleep(0.5)
    await bid_input.fill(str(int(new_bid)))
    print(f"Entered bid amount: ${int(new_bid)}")

    # Find and click bid button
    bid_button_selectors = [
        'button:contains("Increase bid")',
        '.btn-yellow-norm',
        'button[ng-click*="openIncreaseBidModal"]',
        'button[aria-label="Bid now"]',
        'button:contains("Place Bid")',
        'button:contains("Bid Now")',
        'button:contains("Bid now")',
        'button.bid-btn',
        'button[data-uname*="placeBid"]',
        '.place-bid-btn',
        '.bid-button',
        'button:contains("Submit Bid")'
    ]

    bid_button = None
    for selector in bid_button_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                bid_button = btn
                print(f"Found bid button with selector: {selector}")
                break
        except:
            continue

    if not bid_button:
        print("Error: Could not find bid button")
        return False

    # Click bid button
    await bid_button.click()
    print("Clicked bid button")

    # Wait for confirmation dialog to appear
    await asyncio.sleep(2)

    # Look for confirm bid button
    confirm_button_selectors = [
        'button:contains("Confirm your bid")',
        'button[ng-click*="increaseBidForLot"]',
        '.btn-yellow-norm',
        'button.btn:contains("Confirm")'
    ]

    confirm_button = None
    for selector in confirm_button_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=5000):
                confirm_button = btn
                print(f"Found confirm button with selector: {selector}")
                break
        except:
            continue

    if confirm_button:
        await confirm_button.click()
        print("Clicked confirm bid button")
    else:
        print("Warning: Could not find confirm bid button")

    # Wait a bit for bid submission
    await asyncio.sleep(2)

    # Check for success/error messages
    try:
        success_selectors = [
            '.bid-success',
            '.alert-success',
            ':contains("Bid placed successfully")',
            ':contains("Bid submitted")'
        ]
        for selector in success_selectors:
            try:
                success_elem = page.locator(selector).first
                if await success_elem.is_visible(timeout=3000):
                    print("Bid placed successfully!")
                    break
            except:
                continue
    except:
        pass

    # Stay on the page as requested
    print("Staying on the lot page...")
    return True

async def main():
    parser = argparse.ArgumentParser(description='Place a bid on a Copart lot')
    parser.add_argument('lot_number', help='The lot number to bid on')
    args = parser.parse_args()

    print(f"Starting bid on lot: {args.lot_number}")

    async with async_playwright() as p:
        os.environ.setdefault('DISPLAY', ':99')
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context()
        page = await context.new_page()

        # Try to load saved session first
        session_loaded = False
        try:
            if os.path.exists('copart_session.json'):
                with open('copart_session.json', 'r') as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                print('Session cookies loaded')
                session_loaded = True
        except Exception as e:
            print(f'Failed to load session cookies: {e}')

        try:
            # Check if already logged in by trying to access a protected page
            already_logged_in = False
            if session_loaded:
                print("Checking if session is still valid...")
                # Try to access the lot page directly - if session is valid, we should stay on the lot page
                # If session is invalid, we'll be redirected to login
                test_url = f"https://www.copart.com/lot/{args.lot_number}"
                await page.goto(test_url, timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=60000)
                await asyncio.sleep(2)

                current_url = page.url
                # Check if we were redirected to login page
                if "login" in current_url.lower() or "signin" in current_url.lower():
                    print("Session expired - redirected to login page")
                    already_logged_in = False
                else:
                    # Check for bid-related elements to confirm we're on a lot page
                    bid_selectors = [
                        'input#your-max-bid',
                        'input[name="maxBid"]',
                        '.bid_amount_input',
                        'button:contains("Increase bid")',
                        '.btn-yellow-norm'
                    ]

                    for selector in bid_selectors:
                        try:
                            elem = page.locator(selector).first
                            if await elem.is_visible(timeout=2000):
                                print("Session is valid - found bidding elements on lot page")
                                already_logged_in = True
                                break
                        except:
                            continue

                    if not already_logged_in:
                        print("Session may be expired - no bidding elements found")

            # Login only if not already logged in
            if not already_logged_in:
                await login_to_copart(page, context)

            # Place bid
            success = await place_bid_on_lot(page, args.lot_number)
            if success:
                print("Bid process completed successfully!")
            else:
                print("Bid process failed")

            # Keep browser open for 30 seconds to stay on page
            await asyncio.sleep(30)

        except Exception as e:
            print(f"Error during bidding: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())