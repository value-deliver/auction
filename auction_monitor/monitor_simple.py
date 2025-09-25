#!/usr/bin/env python3
"""
Simplified Auction Monitor - Monitors Copart auction pages for real-time updates
Without WebSocket dependency
"""

import asyncio
import time
import os
import json
import random
import logging
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class RequestThrottler:
    """Throttle requests to avoid rate limiting"""
    def __init__(self, requests_per_minute=30):
        self.requests_per_minute = requests_per_minute
        self.request_times = []

    async def throttle(self):
        """Ensure we don't exceed rate limits"""
        now = time.time()
        # Remove old requests
        self.request_times = [t for t in self.request_times if now - t < 60]

        if len(self.request_times) >= self.requests_per_minute:
            # Wait until we can make another request
            wait_time = 60 - (now - self.request_times[0])
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.request_times.append(now)

class AuctionMonitor:
    """Monitors Copart auction pages and extracts real-time data"""

    def __init__(self):
        self.is_monitoring = False
        self.current_auction_data = None
        self.last_update = None
        self.browser = None
        self.page = None
        self.auction_frame = None
        self.throttler = RequestThrottler()
        logging.basicConfig(filename='auction_monitor.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def start_monitoring(self, auction_url):
        """Start monitoring an auction"""
        self.is_monitoring = True

        try:
            # Load environment variables
            self._load_env()

            # Initialize browser
            await self._init_browser()

            # Login to Copart
            await self._login_to_copart()

            # Navigate to auction
            await self._navigate_to_auction(auction_url)

            # Set up MutationObserver for real-time DOM changes
            await self._setup_mutation_observer()

            # Start monitoring loop
            await self._monitor_auction()

        except Exception as e:
            print(f'Monitoring failed: {str(e)}')
            self.is_monitoring = False
        finally:
            if self.browser:
                await self.browser.close()

    def stop_monitoring(self):
        """Stop monitoring"""
        self.is_monitoring = False

    def _load_env(self):
        """Load environment variables"""
        if os.path.exists('../.env'):
            with open('../.env', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()

    async def _init_browser(self):
        """Initialize Playwright browser with realistic fingerprinting"""
        playwright = await async_playwright().start()

        # Browser launch with minimal anti-detection measures
        self.browser = await playwright.chromium.launch(
            headless=False  # Keep visible for debugging
        )

        # Create context similar to copart_login.py - minimal configuration to avoid detection
        self.context = await self.browser.new_context()

        self.page = await self.context.new_page()

        # Log console messages to file for debugging
        self.page.on('console', lambda msg: logging.info(f'Console: {msg.text}'))


    async def _human_like_delay(self, min_delay=1, max_delay=3):
        """Add human-like delays between actions"""
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def _simulate_human_behavior(self):
        """Simulate realistic user behavior"""
        # Random mouse movements
        await self.page.mouse.move(random.randint(100, 800), random.randint(100, 600))
        await self._human_like_delay(0.5, 1.5)

        # Random scrolling
        if random.random() > 0.7:
            await self.page.evaluate("window.scrollTo(0, window.innerHeight / 4)")
            await self._human_like_delay(1, 2)

    async def _check_for_captcha(self):
        """Check if CAPTCHA is present on the page"""
        captcha_selectors = [
            '[class*="captcha"]',
            '[id*="captcha"]',
            '.hcaptcha',
            '.recaptcha',
            '[data-sitekey]',
            'iframe[src*="recaptcha"]'
        ]

        for selector in captcha_selectors:
            try:
                element = self.page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    logging.warning(f'CAPTCHA detected with selector: {selector}')
                    return True
            except:
                continue

        return False

    async def _handle_captcha_if_present(self):
        """Handle CAPTCHA if detected"""
        if await self._check_for_captcha():
            logging.error('CAPTCHA detected - pausing monitoring')
            # Could implement notification system here
            # For now, just log and continue (CAPTCHA solving would require manual intervention)
            await asyncio.sleep(300)  # Wait 5 minutes before retrying
            return True
        return False

    async def _save_session_cookies(self):
        """Save authentication cookies for session persistence"""
        try:
            cookies = await self.context.cookies()
            with open('copart_session.json', 'w') as f:
                json.dump(cookies, f, indent=2)
            logging.info('Session cookies saved')
        except Exception as e:
            logging.warning(f'Failed to save session cookies: {e}')

    async def _load_session_cookies(self):
        """Load saved session cookies"""
        try:
            if os.path.exists('copart_session.json'):
                with open('copart_session.json', 'r') as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                logging.info('Session cookies loaded')
                return True
        except Exception as e:
            logging.warning(f'Failed to load session cookies: {e}')
        return False

    async def _login_to_copart(self):
        """Login to Copart using credentials with enhanced anti-detection"""
        import random  # Ensure random is imported
        print('_login_to_copart method called')

        # Try to load saved session first
        if await self._load_session_cookies():
            print('Attempting to use saved session...')
            await self.page.goto("https://www.copart.com/dashboard", timeout=60000)
            await self._human_like_delay(2, 4)

            # Check if we're logged in
            try:
                # Look for dashboard elements or user menu
                dashboard_elements = ['.dashboard', '.user-menu', '[data-uname*="user"]', '.member-info']
                logged_in = False
                for selector in dashboard_elements:
                    try:
                        element = self.page.locator(selector).first
                        if await element.is_visible(timeout=3000):
                            logged_in = True
                            print('Successfully logged in using saved session')
                            return
                    except:
                        continue

                if not logged_in:
                    print('Saved session expired, proceeding with fresh login')
            except Exception as e:
                print(f'Session check failed: {e}, proceeding with fresh login')

        USERNAME = os.environ.get('COPART_USERNAME')
        PASSWORD = os.environ.get('COPART_PASSWORD')

        if not USERNAME or not PASSWORD:
            raise ValueError("COPART_USERNAME and COPART_PASSWORD environment variables must be set")

        print('Logging in to Copart...')
        print(f'Username: {USERNAME[:3]}***, Password length: {len(PASSWORD)}')

        # Navigate to login page with human-like behavior
        print('Navigating to login page...')
        await self.page.goto("https://www.copart.com/login", timeout=60000)
        await self._human_like_delay(2, 4)
        await self._simulate_human_behavior()

        print(f'Page URL after navigation: {self.page.url}')
        await self.page.wait_for_load_state('networkidle', timeout=60000)
        print('Page loaded, title:', await self.page.title())

        # Debug: Take screenshot and log page content
        try:
            await self.page.screenshot(path='debug_login_page.png')
            print('Screenshot saved as debug_login_page.png')
        except Exception as e:
            print(f'Failed to take screenshot: {e}')

        # Check if we're already logged in
        current_url = self.page.url
        if 'dashboard' in current_url or 'member' in current_url:
            print('Already logged in, skipping login process')
            return

        # Check for different login URLs
        if 'login' not in current_url:
            print(f'Redirected to non-login page: {current_url}')
            # Try alternative login URL
            print('Trying alternative login URL...')
            await self.page.goto("https://www.copart.com/loginForm", timeout=60000)
            await self._human_like_delay(2, 4)
            print(f'Alternative login URL: {self.page.url}')
            if 'login' not in self.page.url:
                print('Still not on login page, trying member login...')
                await self.page.goto("https://www.copart.com/memberLogin", timeout=60000)
                await self._human_like_delay(2, 4)
                print(f'Member login URL: {self.page.url}')

        # Handle cookie consent if present
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
                    manage_button = self.page.locator(selector).first
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
                    all_buttons = self.page.locator('button')
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
                    consent_checkboxes = self.page.locator('input.fc-preference-consent.purpose:checked')
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
                        confirm_button = self.page.locator(selector).first
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
                        all_buttons = self.page.locator('button')
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

        # Wait for login form with multiple selector attempts
        print('Waiting for login form...')
        print(f'Current page title: {await self.page.title()}')
        print(f'Current URL: {self.page.url}')

        login_selectors = [
            'input[name="username"]',
            'input[id*="username"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="user" i]',
            'input[type="email"]',
            '#username',
            '.username-input'
        ]

        login_form_found = False
        for selector in login_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=5000)
                print(f'Login form found with selector: {selector}')
                login_form_found = True
                break
            except Exception as e:
                print(f'Login selector {selector} not found: {e}')
                continue

        if not login_form_found:
            print('No login form found with any selector')
            # Debug: check page content
            content = await self.page.content()
            print(f'Page content length: {len(content)}')
            if 'username' in content.lower() or 'login' in content.lower():
                print('Login-related content found in page')
            else:
                print('No login-related content found in page')

            # Try to find any input fields
            inputs = await self.page.query_selector_all('input')
            print(f'Found {len(inputs)} input fields on page')
            for i, inp in enumerate(inputs[:5]):  # Check first 5 inputs
                inp_type = await inp.get_attribute('type')
                inp_name = await inp.get_attribute('name')
                inp_id = await inp.get_attribute('id')
                print(f'Input {i}: type={inp_type}, name={inp_name}, id={inp_id}')

            print('Continuing despite missing form...')

        # Fill login form
        print('Filling login form...')
        await self.page.click('input[name="username"]')
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self.page.fill('input[name="username"]', USERNAME)
        await asyncio.sleep(random.uniform(2, 5))

        await self.page.click('input[name="password"]')
        await asyncio.sleep(random.uniform(0.5, 1.5))
        await self.page.fill('input[name="password"]', PASSWORD)
        await asyncio.sleep(random.uniform(2, 5))

        # Submit login
        print('Submitting login...')
        login_btn = self.page.locator('button[data-uname="loginSigninmemberbutton"]').first
        await login_btn.hover()
        await asyncio.sleep(random.uniform(3, 5))
        await login_btn.click(timeout=random.randint(10000, 30000))

        # Wait for login success
        print('Waiting for login success...')
        try:
            await self.page.wait_for_url(lambda url: url != "https://www.copart.com/login", timeout=30000)
            print("Login successful!")
            print(f'Current URL: {self.page.url}')

            # Add pause after login before navigating (like copart_login.py)
            print('Pausing after login to appear more human-like...')
            await asyncio.sleep(random.uniform(5, 10))

            # Save session cookies for future use
            await self._save_session_cookies()

        except Exception as e:
            print(f'Login may have failed: {e}')
            print(f'Current URL: {self.page.url}')
            # Check for error messages
            error_selectors = ['.alert-error', '.alert-danger', '.error-message']
            for selector in error_selectors:
                try:
                    error_elem = self.page.locator(selector).first
                    if await error_elem.is_visible(timeout=2000):
                        error_text = await error_elem.text_content()
                        print(f'Login error: {error_text}')
                except:
                    continue
            raise e

    async def _navigate_to_auction(self, auction_url):
        """Navigate to the auction page with enhanced debugging"""
        print(f'Navigating to auction: {auction_url}')

        if not auction_url.startswith('http'):
            auction_url = f"https://www.copart.com{auction_url}"

        print('Going to auction URL...')
        await self.page.goto(auction_url, timeout=60000)
        print('Waiting for page load...')
        await self.page.wait_for_load_state('networkidle', timeout=60000)

        print(f'Page title after navigation: {await self.page.title()}')
        print(f'Current URL: {self.page.url}')

        # Debug: Check page content and iframes
        content = await self.page.content()
        print(f'Page content length: {len(content)}')
        if 'iframe' in content.lower():
            print('Page contains iframes')
        else:
            print('Page does NOT contain iframes')

        # Check for iframes
        frames = self.page.frames
        print(f'Number of frames: {len(frames)}')
        for i, frame in enumerate(frames[1:], 1):  # skip main frame
            print(f'Frame {i}: {frame.url}')

        # Try to find auction iframe with different selectors
        iframe_selectors = [
            'iframe[src*="g2auction.copart.com"]',
            'iframe[src*="auction"]',
            'iframe',
        ]

        self.auction_frame = None
        for selector in iframe_selectors:
            try:
                print(f'Trying iframe selector: {selector}')
                frame_locator = self.page.frame_locator(selector)
                print(f'Created frame locator for: {selector}')
                # Test if frame exists by trying to get an element
                test_element = frame_locator.locator('body')
                print(f'Waiting for iframe body element...')
                await test_element.wait_for(timeout=5000)
                self.auction_frame = frame_locator
                print(f'Found auction iframe with selector: {selector}')
                break
            except Exception as e:
                print(f'Frame selector {selector} failed: {e}')
                continue

        if self.auction_frame is None:
            print('No auction iframe found, checking if auction is live...')
            # Check if this is a live auction page
            if 'auctionDetails=' in self.page.url:
                print('On auction details page, but no iframe found')
                # Maybe the auction interface loads differently
                # Check for any auction-related content on main page
                auction_content = await self.page.locator('text="auction"').count()
                print(f'Found {auction_content} auction-related text elements')
            else:
                print('Not on auction page')

            # Take screenshot for debugging
            try:
                await self.page.screenshot(path='debug_auction_page.png')
                print('Screenshot saved as debug_auction_page.png')
            except Exception as e:
                print(f'Failed to take screenshot: {e}')

            return  # Exit early if no iframe found

        # Check if element exists before waiting
        element = self.auction_frame.locator('.auctionrunningdiv-MACRO')
        count = await element.count()
        logging.info(f'Element .auctionrunningdiv-MACRO count in frame before wait: {count}')

        # Wait for auction content to load (but don't fail if not found)
        print('Waiting for auction content to load...')
        try:
            await self.auction_frame.locator('.auctionrunningdiv-MACRO').wait_for(timeout=10000)  # Reduced timeout
            print('Auction content loaded - live auction detected!')
            logging.info('Auction content loaded - MutationObserver can be set up')
        except Exception as e:
            print(f'Auction content not loaded within 10 seconds: {e}')
            print('Auction may not be live yet, proceeding with monitoring...')
            logging.info(f'Auction content wait failed: {e}')
            # Check element count
            element = self.auction_frame.locator('.auctionrunningdiv-MACRO')
            count = await element.count()
            logging.info(f'Element .auctionrunningdiv-MACRO count in frame: {count}')
            if count == 0:
                print('No auction elements found - auction is not live')
            else:
                print(f'Found {count} auction elements')

    async def _monitor_auction(self):
        """Main monitoring loop with MutationObserver for real-time updates"""
        print('Starting auction monitoring...')

        # Initial data extraction
        auction_data = await self._extract_auction_data()
        self.current_auction_data = auction_data
        self.last_update = datetime.now().isoformat()

        print(f"Initial data: Bid={auction_data['current_bid']}, Bidder={auction_data['current_bidder']}, Time={auction_data['time_remaining']}, Status={auction_data['status']}")

        # Keep monitoring active
        while self.is_monitoring:
            try:
                # Sleep briefly to prevent busy waiting, but rely on MutationObserver for updates
                await asyncio.sleep(1)

                # Periodic health check - extract data every 30 seconds as fallback
                current_time = time.time()
                if not hasattr(self, '_last_health_check') or current_time - self._last_health_check > 30:
                    self._last_health_check = current_time

                    auction_data = await self._extract_auction_data()
                    self.current_auction_data = auction_data
                    self.last_update = datetime.now().isoformat()
                    print(f"Health check update: Bid={auction_data['current_bid']}, Time={auction_data['time_remaining']}")

            except Exception as e:
                print(f'Monitoring error: {str(e)}')
                await asyncio.sleep(5)

    async def _extract_auction_data(self):
        """Extract current auction data from the page"""
        data = {
            'auction_id': 'Unknown',
            'current_bid': 'N/A',
            'current_bidder': 'N/A',
            'time_remaining': 'N/A',
            'active_bidders': 0,
            'status': 'unknown',
            'last_update': datetime.now().isoformat()
        }

        try:
            # Check if page is closed
            if self.page.is_closed():
                print("Page is closed, returning default data")
                return data

            # Use auction frame if available, otherwise main page
            target = self.auction_frame if self.auction_frame else self.page

            # Extract auction ID from URL or page
            url = self.page.url
            if 'auctionDetails=' in url:
                data['auction_id'] = url.split('auctionDetails=')[1].split('&')[0]

            # Current bid
            bid_selectors = ['.current-bid', '.bid-amount', '.bid-price', '[data-uname*="bid"]', 'input[name="bidAmount"]']
            for selector in bid_selectors:
                try:
                    bid_elem = target.locator(selector).first
                    if await bid_elem.is_visible(timeout=1000):
                        if selector == 'input[name="bidAmount"]':
                            value = await bid_elem.get_attribute('value')
                            if value:
                                data['current_bid'] = value
                            else:
                                data['current_bid'] = await bid_elem.text_content()
                        else:
                            data['current_bid'] = await bid_elem.text_content()
                        print(f"Found bid with selector {selector}: {data['current_bid']}")
                        break
                    else:
                        print(f"Bid selector {selector} not visible")
                except Exception as e:
                    print(f"Error with bid selector {selector}: {e}")
                    continue

            # Current bidder
            bidder_selectors = ['.current-bidder', '.bidder-name', '.winning-bidder']
            for selector in bidder_selectors:
                try:
                    bidder_elem = target.locator(selector).first
                    if await bidder_elem.is_visible(timeout=1000):
                        data['current_bidder'] = await bidder_elem.text_content()
                        print(f"Found bidder with selector {selector}: {data['current_bidder']}")
                        break
                    else:
                        print(f"Bidder selector {selector} not visible")
                except Exception as e:
                    print(f"Error with bidder selector {selector}: {e}")
                    continue

            # Time remaining - look for countdown timers and circular progress
            time_selectors = [
                '.time-remaining', '.countdown', '.time-left', '[data-uname*="time"]',
                '.countdown-timer', '.auction-timer', '.time-display',
                '[class*="countdown"]', '[class*="timer"]'
            ]
            for selector in time_selectors:
                try:
                    time_elem = target.locator(selector).first
                    if await time_elem.is_visible(timeout=1000):
                        time_text = await time_elem.text_content()
                        if time_text and time_text.strip():
                            data['time_remaining'] = time_text.strip()
                            print(f"Found time with selector {selector}: {data['time_remaining']}")
                            break
                    else:
                        print(f"Time selector {selector} not visible")
                except Exception as e:
                    print(f"Error with time selector {selector}: {e}")
                    continue

            # Also check for circular progress indicators (SVG circles)
            try:
                # Look for SVG circles that might represent countdown timers
                circles = self.page.locator('circle')
                circle_count = await circles.count()
                for i in range(circle_count):
                    circle = circles.nth(i)
                    # Check if this circle has countdown-related attributes
                    cx = await circle.get_attribute('cx')
                    cy = await circle.get_attribute('cy')
                    r = await circle.get_attribute('r')
                    if cx and cy and r:  # This looks like a countdown circle
                        # Try to find associated text
                        parent = circle.locator('xpath=ancestor::*[contains(@class, "countdown") or contains(@class, "timer")]').first
                        if await parent.is_visible(timeout=500):
                            countdown_text = await parent.text_content()
                            if countdown_text and 'time' in countdown_text.lower():
                                data['time_remaining'] = countdown_text.strip()
                                break
            except:
                pass

            # Active bidders count
            bidders_selectors = ['.active-bidders', '.bidder-count', '.bidders-online']
            for selector in bidders_selectors:
                try:
                    bidders_elem = target.locator(selector).first
                    if await bidders_elem.is_visible(timeout=1000):
                        bidders_text = await bidders_elem.text_content()
                        # Extract number from text
                        import re
                        numbers = re.findall(r'\d+', bidders_text)
                        if numbers:
                            data['active_bidders'] = int(numbers[0])
                            print(f"Found bidders with selector {selector}: {data['active_bidders']}")
                        break
                    else:
                        print(f"Bidders selector {selector} not visible")
                except Exception as e:
                    print(f"Error with bidders selector {selector}: {e}")
                    continue

            # Auction status
            status_selectors = ['.auction-status', '.status', '.auction-state']
            for selector in status_selectors:
                try:
                    status_elem = target.locator(selector).first
                    if await status_elem.is_visible(timeout=1000):
                        status_text = await status_elem.text_content()
                        if 'active' in status_text.lower() or 'running' in status_text.lower():
                            data['status'] = 'active'
                        elif 'ended' in status_text.lower() or 'finished' in status_text.lower():
                            data['status'] = 'ended'
                        elif 'paused' in status_text.lower():
                            data['status'] = 'paused'
                        print(f"Found status with selector {selector}: {data['status']}")
                        break
                    else:
                        print(f"Status selector {selector} not visible")
                except Exception as e:
                    print(f"Error with status selector {selector}: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting auction data: {e}")

        return data

    async def _setup_mutation_observer(self):
        """Set up MutationObserver to detect real-time DOM changes in auctionrunningdiv-MACRO"""
        try:
            if not self.auction_frame:
                print('No auction frame found, skipping observer setup')
                return

            # Wait for auction content to load
            print('Waiting for auction content to load...')
            try:
                await self.auction_frame.locator('.auctionrunningdiv-MACRO').wait_for(timeout=30000)
                print('Auction content loaded (.auctionrunningdiv-MACRO found)')
            except Exception as e:
                print(f'Auction content not loaded within 30 seconds: {e}')
                print('Proceeding with observer setup anyway...')

            # JavaScript code to set up MutationObserver
            observer_js = """
            (function() {
                // Function to extract current auction data
                function extractAuctionData() {
                    const data = {
                        current_bid: 'N/A',
                        current_bidder: 'N/A',
                        time_remaining: 'N/A',
                        status: 'unknown'
                    };

                    // Extract bid from auctionrunningdiv-MACRO
                    const auctionDiv = document.querySelector('.auctionrunningdiv-MACRO');
                    if (auctionDiv) {
                        // Extract bid amount from SVG text
                        const bidText = auctionDiv.querySelector('text[fill="#0757ac"]');
                        if (bidText) {
                            data.current_bid = bidText.textContent.trim();
                        }

                        // Extract bidder/location from SVG text
                        const bidderTexts = auctionDiv.querySelectorAll('text[fill="black"]');
                        bidderTexts.forEach(text => {
                            const content = text.textContent.trim();
                            if (content && content !== 'Bid!' && !content.includes('$')) {
                                data.current_bidder = content;
                            }
                        });
                    }

                    // Extract time remaining from various possible locations
                    const timeSelectors = [
                        '.time-remaining', '.countdown', '.time-left', '[data-uname*="time"]',
                        '.countdown-timer', '.auction-timer', '.time-display',
                        '[class*="countdown"]', '[class*="timer"]'
                    ];

                    for (const selector of timeSelectors) {
                        const elem = document.querySelector(selector);
                        if (elem && elem.textContent && elem.textContent.trim()) {
                            data.time_remaining = elem.textContent.trim();
                            break;
                        }
                    }

                    return data;
                }

                // Set up MutationObserver
                const targetNode = document.querySelector('.auctionrunningdiv-MACRO');
                if (targetNode) {
                    const observer = new MutationObserver(function(mutations) {
                        let shouldUpdate = false;

                        mutations.forEach(function(mutation) {
                            // Check if the mutation affects text content or attributes
                            if (mutation.type === 'childList' || mutation.type === 'characterData' ||
                                (mutation.type === 'attributes' && mutation.attributeName === 'value')) {
                                shouldUpdate = true;
                            }
                        });

                        if (shouldUpdate) {
                            const newData = extractAuctionData();
                            // Send data back to Python via console.log (captured by Playwright)
                            console.log('AUCTION_UPDATE:' + JSON.stringify(newData));
                        }
                    });

                    // Start observing
                    observer.observe(targetNode, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true,
                        attributeFilter: ['value']
                    });

                    console.log('MutationObserver set up for auctionrunningdiv-MACRO');
                } else {
                    console.log('auctionrunningdiv-MACRO not found, MutationObserver not set up');
                }
            })();
            """

            # Inject the JavaScript into the iframe
            await self.auction_frame.evaluate(observer_js)

            # Set up console message listener to capture updates
            self.page.on('console', self._handle_console_message)

            print('MutationObserver setup complete')
            logging.info('MutationObserver setup complete - monitoring for real-time updates')

        except Exception as e:
            print(f'Failed to set up MutationObserver: {e}')

    def _handle_console_message(self, msg):
        """Handle console messages from the page, including MutationObserver updates"""
        try:
            text = msg.text
            if text.startswith('AUCTION_UPDATE:'):
                # Parse the auction data update
                json_data = text[15:]  # Remove 'AUCTION_UPDATE:' prefix
                auction_data = json.loads(json_data)

                # Update current data
                self.current_auction_data.update(auction_data)
                self.last_update = datetime.now().isoformat()

                # Print update for debugging
                print(f"Real-time update: Bid={auction_data.get('current_bid', 'N/A')}, Bidder={auction_data.get('current_bidder', 'N/A')}, Time={auction_data.get('time_remaining', 'N/A')}")

        except Exception as e:
            # Ignore non-auction-update console messages
            pass