#!/usr/bin/env python3
"""
Copart Today's Auctions Test
This script performs an automated test to navigate to today's auctions and open the first auction:
1. Login to Copart
2. Navigate to today's auctions page
3. Open the first auction listing
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import json
import random
import os

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

async def login_to_copart(page):
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

async def search_vehicle(page, query):
    """Search for a vehicle on Copart"""
    print(f"Searching for: {query}")

    # Navigate to vehicle finder
    await page.goto("https://www.copart.com/vehicleFinder", timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Fill search input
    search_input = page.locator('input#input-search').first
    await search_input.fill(query)
    await asyncio.sleep(random.uniform(1, 2))

    # Click search button
    search_btn = page.locator('button.search-btn').first
    await search_btn.click()
    await asyncio.sleep(3)  # Wait for results

    print("Search completed")

async def get_first_lot_link(page):
    """Get the first lot link from search results"""
    lot_links = page.locator('.search_result_lot_number a')
    if await lot_links.count() > 0:
        first_link = lot_links.first
        href = await first_link.get_attribute('href')
        lot_number = await first_link.text_content()
        return href, lot_number.strip()
    return None, None

async def open_lot_details(page, lot_url):
    """Open lot details page and extract information"""
    if not lot_url.startswith('http'):
        lot_url = f"https://www.copart.com{lot_url}"
    print(f"Opening lot details: {lot_url}")
    await page.goto(lot_url, timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Extract lot details - adjust selectors as needed
    details = {}

    try:
        # Lot title
        title_elem = page.locator('.lot-title, .vehicle-title, h1').first
        details['title'] = await title_elem.text_content() if await title_elem.is_visible() else 'N/A'
    except:
        details['title'] = 'N/A'

    try:
        # Lot number
        lot_num_elem = page.locator('.lot-number, .lot-num, #LotNumber, span[data-uname="lotdetailVinvalue"]').first
        details['lot_number'] = await lot_num_elem.text_content() if await lot_num_elem.is_visible() else 'N/A'
    except:
        details['lot_number'] = 'N/A'

    try:
        # Current bid
        bid_elem = page.locator('.current-bid, .bid-amount, .bid-price').first
        details['current_bid'] = await bid_elem.text_content() if await bid_elem.is_visible() else 'N/A'
    except:
        details['current_bid'] = 'N/A'

    print("Lot Details:")
    for key, value in details.items():
        print(f"  {key}: {value}")

    return details

async def add_to_watchlist(page):
    """Add the current lot to watch list"""
    print("Adding to watch list...")

    # Look for add to watch list button - adjust selector as needed
    add_btn_selectors = [
        'button:contains("Add to Watch List")',
        'button:contains("Add to Watchlist")',
        'button:contains("Watch")',
        'a:contains("Add to Watch List")',
        'a:contains("Add to Watchlist")',
        '.add-watchlist-btn',
        '[data-uname*="watch"]',
        '.btn:contains("Add to Watch List")',
        '.btn:contains("Add to Watchlist")',
        '.btn-white.star-icon',
        'button[title="Add to watchlist"]',
        'button[aria-label="Add to watchlist"]'
    ]

    for selector in add_btn_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await asyncio.sleep(2)
                print("Added to watch list")
                return True
        except:
            continue

    print("Could not find add to watch list button")
    return False

async def check_watchlist_presence(page, lot_number):
    """Check if lot is present in watch list"""
    print("Checking watch list presence...")

    # Navigate to watch list
    await page.goto("https://www.copart.com/watchList", timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Get all lot numbers from watch list
    lot_links = page.locator('.search_result_lot_number a')
    watchlist_lots = []
    for i in range(await lot_links.count()):
        text = await lot_links.nth(i).text_content()
        lot_num = text.strip()
        if lot_num.isdigit():
            watchlist_lots.append(lot_num)

    print(f"Watch list lots: {watchlist_lots}")

    is_present = lot_number in watchlist_lots
    print(f"Lot {lot_number} {'is' if is_present else 'is not'} in watch list")
    return is_present

async def remove_from_watchlist(page, lot_url):
    """Remove lot from watch list by clicking remove on lot detail page"""
    print("Removing from watch list...")

    if not lot_url.startswith('http'):
        lot_url = f"https://www.copart.com{lot_url}"

    await page.goto(lot_url, timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Look for remove button on lot detail page
    remove_btn_selectors = [
        '.remove-watchlist-btn',
        'button:contains("Remove")',
        '[data-uname*="remove"]',
        '.btn-white.star-icon.in-wishlist',
        'button[title="Remove from watchlist"]',
        'button[aria-label="Remove"]',
        'button[desktoptext="Remove"]'
    ]

    for selector in remove_btn_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await asyncio.sleep(2)
                print("Removed from watch list")
                return True
        except:
            continue

    print("Could not find remove button")
    return False

async def navigate_to_todays_auctions_and_open_first(page):
    """Navigate to today's auctions page and open the first auction"""
    print("Navigating to today's auctions...")

    await page.goto("https://www.copart.com/todaysAuction", timeout=60000)
    await page.wait_for_load_state('networkidle', timeout=60000)

    # Wait a bit more for dynamic content
    await asyncio.sleep(5)

    # Try multiple selectors for auction links
    selectors = [
        'a[href*="auctionDashboard"]',
        '.btn.btn-green.joinsearch.small',
        'a[href*="/lot/"]',
        '.search_result_lot_number a',
        'a[href*="lotDetail"]',
        'a[href*="vehicle"]',
        '.lot-link',
        '.auction-item a'
    ]

    first_auction = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.is_visible(timeout=5000):
                first_auction = locator
                print(f"Found auction link with selector: {selector}")
                break
        except:
            continue

    if first_auction:
        href = await first_auction.get_attribute('href')
        print(f"Opening first auction: {href}")
        await first_auction.click()
        await page.wait_for_load_state('networkidle', timeout=60000)
        print("First auction opened successfully")
        return True
    else:
        # Debug: print all links on the page
        all_links = page.locator('a')
        count = await all_links.count()
        print(f"Total links found on page: {count}")
        for i in range(min(10, count)):  # Print first 10 links
            href = await all_links.nth(i).get_attribute('href')
            text = await all_links.nth(i).text_content()
            print(f"Link {i+1}: {text.strip()} -> {href}")
        print("No auctions found on today's auctions page")
        return False

async def run_tests():
    """Run the today's auctions test"""
    print("Starting Copart Today's Auctions Test")

    async with async_playwright() as p:
        os.environ.setdefault('DISPLAY', ':99')
        browser = await p.chromium.launch(headless=False)

        context = await browser.new_context()
        page = await context.new_page()

        try:
            # Login
            await login_to_copart(page)

            # Navigate to today's auctions and open first auction
            success = await navigate_to_todays_auctions_and_open_first(page)
            if success:
                print("Test passed - first auction opened successfully!")
            else:
                print("Test failed - could not open first auction")

        except Exception as e:
            print(f"Test failed with error: {e}")
        finally:
            await asyncio.sleep(30)
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_tests())