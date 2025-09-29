#!/usr/bin/env python3
"""
Auction Bid Button Finder
Tests if the bid button is present in a Copart auction dashboard
Usage: python auction_bid_button_finder.py <auction_id>
Example: python auction_bid_button_finder.py 366-A
"""

import asyncio
import json
import os
import sys
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

async def save_session_cookies(context):
    """Save authentication cookies for session persistence"""
    try:
        cookies = await context.cookies()
        with open('copart_session.json', 'w') as f:
            json.dump(cookies, f, indent=2)
        print('Session cookies saved')
    except Exception as e:
        print(f'Failed to save session cookies: {e}')

async def load_session_cookies(context):
    """Load saved session cookies"""
    try:
        if os.path.exists('copart_session.json'):
            with open('copart_session.json', 'r') as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print('Session cookies loaded')
            return True
    except Exception as e:
        print(f'Failed to load session cookies: {e}')
    return False

async def login_to_copart(page, context):
    """Login to Copart with session reuse"""
    USERNAME = os.environ.get('COPART_USERNAME')
    PASSWORD = os.environ.get('COPART_PASSWORD')

    if not USERNAME or not PASSWORD:
        raise ValueError("COPART_USERNAME and COPART_PASSWORD environment variables must be set")

    # Try to load saved session first
    if await load_session_cookies(context):
        print('Attempting to use saved session...')
        await page.goto("https://www.copart.com/dashboard", timeout=60000)
        await asyncio.sleep(2)

        # Check if we're logged in by checking if we stayed on dashboard (not redirected to login)
        current_url = page.url
        if 'login' not in current_url.lower():
            print('Successfully logged in using saved session')
            return
        else:
            print('Session expired - redirected to login, proceeding with fresh login')

    print('Logging in to Copart...')
    await page.goto("https://www.copart.com/login", timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Handle cookie consent
    try:
        await page.locator('button[data-testid*="manage"]').first.click(timeout=2000)
        await asyncio.sleep(1)
        consent_checkboxes = page.locator('input.fc-preference-consent.purpose:checked')
        for i in range(await consent_checkboxes.count()):
            await consent_checkboxes.nth(i).click()
        await page.locator('.fc-button.fc-confirm-choices').first.click(timeout=2000)
        await asyncio.sleep(2)
    except:
        pass

    await page.fill('input[name="username"]', USERNAME)
    await page.fill('input[name="password"]', PASSWORD)
    await page.locator('button[data-uname="loginSigninmemberbutton"]').first.click(timeout=30000)
    await page.wait_for_url(lambda url: url != "https://www.copart.com/login", timeout=30000)
    print("Login successful!")

    # Save session cookies for future use
    await save_session_cookies(context)

async def main():
    if len(sys.argv) != 2:
        print("Usage: python auction_bid_button_finder.py <auction_id>")
        print("Example: python auction_bid_button_finder.py 366-A")
        sys.exit(1)

    auction_id = sys.argv[1]
    load_env()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await login_to_copart(page, context)
            
            auction_url = f"https://www.copart.com/auctionDashboard?auctionDetails={auction_id}"
            print(f'Navigating to: {auction_url}')
            await page.goto(auction_url, timeout=60000)
            await page.wait_for_load_state('load', timeout=30000)
            print(f'Current URL after navigation: {page.url}')
            print(f'Page title: {await page.title()}')
            # Take screenshot for debugging
            await page.screenshot(path='debug_auction_page.png')
            print('Screenshot saved as debug_auction_page.png')

            # Wait for iframe to be present in DOM
            print('Waiting for auction iframe to load...')
            await page.wait_for_selector('iframe[src*="g2auction.copart.com"]', timeout=30000)
            print('Iframe element found in DOM')

            # Find iframe
            target_frame = None
            frames = page.frames
            for frame in frames:
                if 'g2auction.copart.com' in frame.url:
                    target_frame = frame
                    break

            if not target_frame:
                print("❌ Auction iframe not found by URL")
                # Try to find any iframe and wait for it to load
                try:
                    all_iframes = page.locator('iframe')
                    iframe_count = await all_iframes.count()
                    print(f"Found {iframe_count} iframes on page")
                    if iframe_count > 0:
                        # Wait for first iframe to load
                        first_iframe = all_iframes.first
                        await page.wait_for_timeout(5000)  # Wait 5 seconds
                        frames = page.frames
                        for frame in frames:
                            if frame != page.main_frame and frame.url:
                                print(f"Frame URL: {frame.url}")
                                if 'g2auction' in frame.url:
                                    target_frame = frame
                                    break
                except Exception as e:
                    print(f"Error checking iframes: {e}")
                if not target_frame:
                    return

            print(f"✅ Found auction iframe: {target_frame.url}")
            # Wait for frame content to load
            await target_frame.wait_for_load_state('domcontentloaded', timeout=60000)
            print("Frame content loaded")

            # Debug: Print iframe HTML snippet to check for nested iframes
            iframe_html = await target_frame.content()
            print(f"Target frame HTML snippet: {iframe_html[:2000]}")

            # Debug: Check iframes
            iframe_count = await page.locator('iframe[src*="g2auction.copart.com"]').count()
            print(f"📊 Iframes with g2auction src found: {iframe_count}")

            # Check for sub-iframes in the target_frame
            sub_iframes = await target_frame.locator('iframe').all()
            print(f"📊 Sub-iframes in auction iframe: {len(sub_iframes)}")

            button_frame = target_frame  # Default to target_frame
            bid_button_found = False

            for i, sub_iframe_locator in enumerate(sub_iframes):
                try:
                    sub_frame = await sub_iframe_locator.content_frame()
                    if sub_frame:
                        print(f"  Sub-iframe {i}: {sub_frame.url}")
                        # Try to find button in sub_frame
                        bid_button = sub_frame.locator('button[data-uname="bidCurrentLot"]')
                        try:
                            await bid_button.wait_for(timeout=5000)
                            print("✅ Found bid button in sub-iframe")
                            button_frame = sub_frame
                            bid_button_found = True
                            break
                        except PlaywrightTimeoutError:
                            print("❌ Bid button not in sub-iframe")
                except Exception as e:
                    print(f"Error accessing sub-iframe {i}: {e}")

            if not bid_button_found:
                print("Checking for bid button in main auction iframe...")
                bid_button = target_frame.locator('button[data-uname="bidCurrentLot"]')
                try:
                    await bid_button.wait_for(timeout=30000)
                    print("✅ Bid button found in main auction iframe")
                except PlaywrightTimeoutError:
                    print("❌ Bid button not found in main auction iframe either")
                    return

            # Check count
            count = await bid_button.count()
            print(f"📊 Bid button elements found: {count}")

            if count > 0:
                bid_button = bid_button.first
                is_visible = await bid_button.is_visible(timeout=2000)
                print(f"👁️ Button visibility: {is_visible}")

                button_text = await bid_button.text_content()
                print(f"📋 Button text: '{button_text}'")

                button_outer_html = await bid_button.evaluate('element => element.outerHTML')
                print(f"📋 Button outer HTML: '{button_outer_html}'")

                # Highlight the bid button by changing its color
                try:
                    print("🎨 Highlighting bid button...")
                    await bid_button.evaluate("""
                        (element) => {
                            console.log('🎨 Starting bid button highlighting...');
                            const originalStyles = {
                                backgroundColor: element.style.backgroundColor,
                                border: element.style.border,
                                color: element.style.color,
                                background: element.style.background
                            };
                            console.log('Original styles stored:', originalStyles);

                            // Apply bright highlighting
                            element.style.setProperty('background-color', '#00ff00', 'important');
                            element.style.setProperty('border', '3px solid #ff0000', 'important');
                            element.style.setProperty('color', '#000000', 'important');
                            element.style.setProperty('font-weight', 'bold', 'important');

                            console.log('✅ Bid button highlighting applied');

                            // Reset after 3 seconds
                            setTimeout(() => {
                                console.log('🔄 Resetting bid button to original state...');
                                element.style.setProperty('background-color', originalStyles.backgroundColor, 'important');
                                element.style.setProperty('border', originalStyles.border, 'important');
                                element.style.setProperty('color', originalStyles.color, 'important');
                                element.style.setProperty('font-weight', '', 'important');
                                console.log('✅ Bid button reset complete');
                            }, 3000);
                        }
                    """)
                    print("🎨 Bid button highlighting script executed successfully")
                except Exception as e:
                    print(f"❌ Could not highlight bid button: {e}")

                # Keep browser open to see the color change
                print("🔍 Browser will remain open for 10 seconds to view the color change...")
                await asyncio.sleep(10)
                print("🔍 Closing browser...")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())