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

    def __init__(self, socketio_instance=None):
        self.is_monitoring = False
        self.current_auction_data = None
        self.last_update = None
        self.browser = None
        self.page = None
        self.auction_frame = None
        self.throttler = RequestThrottler()
        self.socketio = socketio_instance
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
            print('About to call _setup_mutation_observer...')
            await self._setup_mutation_observer()
            print('_setup_mutation_observer completed')

            # Start monitoring loop
            await self._monitor_auction()

        except Exception as e:
            print(f'Monitoring failed: {str(e)}')
            self.is_monitoring = False
        finally:
            if self.browser:
                await self.browser.close()

    def stop_monitoring(self):
        """Stop monitoring and clean up listeners"""
        print("Stopping auction monitoring and cleaning up listeners...")

        # Clean up MutationObservers in the iframe
        if self.auction_frame and self.page:
            try:
                cleanup_js = """
                (function() {
                    console.log('Cleaning up MutationObservers...');

                    // Disconnect any existing observers
                    if (window.auctionObservers && window.auctionObservers.length > 0) {
                        window.auctionObservers.forEach(function(observer) {
                            if (observer && typeof observer.disconnect === 'function') {
                                observer.disconnect();
                                console.log('Disconnected observer');
                            }
                        });
                        window.auctionObservers = [];
                    }

                    // Also try to find and disconnect any remaining observers
                    // This is a fallback in case observers weren't stored properly
                    const auctionDiv = document.querySelector('.auctionrunningdiv-MACRO');
                    if (auctionDiv) {
                        // Note: We can't directly access the observer instances,
                        // but we can remove event listeners if any were added
                        console.log('Auction div found, cleanup complete');
                    }

                    console.log('MutationObserver cleanup completed');
                })();
                """

                # Try to inject cleanup JavaScript synchronously
                try:
                    # Use page.evaluate to run in the main frame context
                    self.page.evaluate(cleanup_js)
                    print("✅ MutationObserver cleanup completed")
                except Exception as e:
                    print(f"⚠️ Could not clean up MutationObservers: {e}")

            except Exception as e:
                print(f"⚠️ Error during cleanup: {e}")

        self.is_monitoring = False
        print("Auction monitoring stopped")

    async def place_bid(self, bid_amount):
        """Test bid button detection without actually placing a bid"""
        try:
            if not self.auction_frame:
                print("No auction frame available for bidding")
                return False

            print(f"Testing bid button detection for amount: ${bid_amount}")

            # First, set the bid amount in the input field
            bid_input_selector = 'input[name="bidAmount"], input[data-uname="bidAmount"]'
            try:
                bid_input = self.auction_frame.locator(bid_input_selector).first
                await bid_input.wait_for(timeout=5000)
                await bid_input.fill(str(bid_amount))
                print(f"Set bid amount to: ${bid_amount}")
                await asyncio.sleep(0.5)  # Brief pause
            except Exception as e:
                print(f"Failed to set bid amount: {e}")
                return False

            # Find the bid button (but don't click it)
            bid_button_selector = 'button[data-uname="bidCurrentLot"], button[data-id]'
            try:
                bid_button = self.auction_frame.locator(bid_button_selector).first
                await bid_button.wait_for(timeout=5000)
                print(f"✅ BID BUTTON FOUND with selector: {bid_button_selector}")

                # Highlight the Copart bid button by changing its style
                try:
                    original_text = await bid_button.text_content()
                    print(f"Original Copart button text: '{original_text}'")

                    await bid_button.evaluate("""
                        (element) => {
                            const originalText = element.textContent || element.innerText || 'Bid';
                            console.log('Highlighting Copart bid button, original text:', originalText);

                            // Store original styles
                            const originalStyles = {
                                backgroundColor: element.style.backgroundColor,
                                border: element.style.border,
                                boxShadow: element.style.boxShadow,
                                transform: element.style.transform,
                                color: element.style.color
                            };

                            // Apply bright highlighting
                            element.style.backgroundColor = '#00ff00';  // Bright green
                            element.style.border = '4px solid #ff0000';  // Red border
                            element.style.boxShadow = '0 0 20px rgba(255, 0, 0, 0.8)';  // Red glow
                            element.style.transform = 'scale(1.2)';  // Larger scale
                            element.style.color = '#000000';  // Black text for contrast
                            element.textContent = 'TEST BID SUCCESS!';

                            console.log('Copart bid button highlighted successfully');

                            // Reset after 5 seconds
                            setTimeout(() => {
                                console.log('Resetting Copart bid button to original state');
                                element.style.backgroundColor = originalStyles.backgroundColor;
                                element.style.border = originalStyles.border;
                                element.style.boxShadow = originalStyles.boxShadow;
                                element.style.transform = originalStyles.transform;
                                element.style.color = originalStyles.color;
                                element.textContent = originalText;
                                console.log('Copart bid button reset complete');
                            }, 5000);
                        }
                    """)
                    print("🎨 Copart bid button highlighted in bright green for 5 seconds")
                except Exception as highlight_error:
                    print(f"Could not highlight Copart bid button: {highlight_error}")
                    import traceback
                    traceback.print_exc()

                await asyncio.sleep(1)  # Brief pause to show the highlight
                print("🎯 Bid button detection test completed successfully")
                return True

            except Exception as e:
                print(f"❌ BID BUTTON NOT FOUND with selector: {bid_button_selector}")
                print(f"Error: {e}")
                return False

        except Exception as e:
            print(f"Bid button detection test failed: {e}")
            return False

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
        await self.page.wait_for_load_state('load', timeout=30000)

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

            # Set up network monitoring for cross-origin iframe communication
            await self._setup_network_monitoring()
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

        # Set up network monitoring for auction data
        await self._setup_network_monitoring()

    async def _monitor_auction(self):
        """Main monitoring loop with MutationObserver and network monitoring for real-time updates"""
        print('Starting auction monitoring...')

        # Initial data extraction
        auction_data = await self._extract_auction_data()
        self.current_auction_data = auction_data
        self.last_update = datetime.now().isoformat()

        print(f"Initial data: Bid={auction_data['current_bid']}, Bidder={auction_data['current_bidder']}, Time={auction_data['time_remaining']}, Status={auction_data['status']}")

        # Emit initial data via WebSocket
        if self.socketio:
            try:
                self.socketio.emit('auction_update', {
                    'is_monitoring': self.is_monitoring,
                    'current_auction': self.current_auction_data,
                    'last_update': self.last_update,
                    'content_change': False,
                    'initial_load': True
                })
                print("Initial WebSocket data emitted")
            except Exception as e:
                print(f"Failed to emit initial WebSocket data: {e}")

        # Keep monitoring active
        while self.is_monitoring:
            try:
                # Sleep briefly to prevent busy waiting, but rely on MutationObserver for updates
                await asyncio.sleep(1)

                # Periodic health check - extract data every 30 seconds as fallback
                current_time = time.time()
                if not hasattr(self, '_last_health_check') or current_time - self._last_health_check > 30:
                    self._last_health_check = current_time

                    try:
                        auction_data = await self._extract_auction_data()
                        self.current_auction_data = auction_data
                        self.last_update = datetime.now().isoformat()
                        print(f"Health check update: Bid={auction_data['current_bid']}, Time={auction_data['time_remaining']}")

                        # Check for recent network activity
                        await self._check_recent_network_activity()
                    except Exception as extract_error:
                        print(f"Data extraction failed during health check: {extract_error}")
                        # Try to reinitialize iframe access if it failed
                        if "destroyed" in str(extract_error).lower():
                            print("Execution context destroyed, attempting to reinitialize...")
                            try:
                                # Re-setup iframe access
                                await self._navigate_to_auction(self.page.url)
                                await self._setup_mutation_observer()
                            except Exception as reinit_error:
                                print(f"Failed to reinitialize iframe access: {reinit_error}")

            except Exception as e:
                print(f'Monitoring error: {str(e)}')
                # If it's an execution context destroyed error, try to recover
                if "destroyed" in str(e).lower() or "context" in str(e).lower():
                    print("Execution context error detected, attempting recovery...")
                    await asyncio.sleep(2)
                    try:
                        # Try to reinitialize the monitoring setup
                        await self._setup_mutation_observer()
                    except Exception as recovery_error:
                        print(f"Recovery failed: {recovery_error}")
                        await asyncio.sleep(10)  # Wait longer before retry
                else:
                    await asyncio.sleep(5)

    async def _check_recent_network_activity(self):
        """Check for recent network activity that might indicate auction updates"""
        try:
            if hasattr(self, 'websocket_messages') and self.websocket_messages:
                # Check for messages in the last 30 seconds
                recent_messages = [msg for msg in self.websocket_messages
                                 if (datetime.now() - datetime.fromisoformat(msg['timestamp'])).seconds < 30]

                if recent_messages:
                    print(f"Found {len(recent_messages)} recent WebSocket messages")
                    for msg in recent_messages[-3:]:  # Show last 3 messages
                        print(f"Recent WS: {msg['url']} - {str(msg['data'])[:100]}...")

        except Exception as e:
            print(f"Error checking recent network activity: {e}")

    async def _extract_auction_data(self):
        """Extract current auction data from the page"""
        data = {
            'auction_id': 'Unknown',
            'lot_title': 'N/A',
            'lot_number': 'N/A',
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

            # Extract auction ID from URL or page
            url = self.page.url
            if 'auctionDetails=' in url:
                data['auction_id'] = url.split('auctionDetails=')[1].split('&')[0]

            # Extract lot details from main page
            await self._extract_lot_details_from_main_page(data)

            # Check for auction status indicators on main page
            await self._check_main_page_auction_status(data)

            # Try to extract data from iframe if accessible
            if self.auction_frame:
                try:
                    await self._extract_data_from_iframe(data)
                except Exception as e:
                    print(f"Could not extract data from iframe: {e}")

            # Check network activity for auction data
            await self._check_network_auction_data(data)

        except Exception as e:
            print(f"Error extracting auction data: {e}")

        return data

    async def _extract_lot_details_from_main_page(self, data):
        """Extract lot title and number from iframe using Copart selectors"""
        try:
            if not self.auction_frame:
                print("No auction frame available for lot details extraction")
                return

            # Extract lot title using the provided Copart selector
            title_selectors = [
                '.titlelbl.ellipsis[title]',  # Copart lot title selector
                '.lot-title',
                '.vehicle-title',
                'h1',
                '[data-uname*="title"]'
            ]

            for selector in title_selectors:
                try:
                    title_elem = self.auction_frame.locator(selector).first
                    if await title_elem.is_visible(timeout=2000):
                        # Try to get title from 'title' attribute first, then text content
                        title_text = await title_elem.get_attribute('title')
                        if not title_text:
                            title_text = await title_elem.text_content()
                        if title_text and title_text.strip():
                            data['lot_title'] = title_text.strip()
                            print(f"Found lot title with selector {selector}: {data['lot_title']}")
                            break
                except Exception as e:
                    print(f"Error with title selector {selector}: {e}")
                    continue

            # Extract lot number using the provided Copart selector
            lot_number_selectors = [
                '.itempair .titlelbl.ellipsis[href*="lot/"]',  # Copart lot number selector
                '.lot-number',
                '.lot-num',
                '#LotNumber',
                'span[data-uname="lotdetailVinvalue"]',
                '[data-uname*="lot"]'
            ]

            for selector in lot_number_selectors:
                try:
                    lot_elem = self.auction_frame.locator(selector).first
                    if await lot_elem.is_visible(timeout=2000):
                        # For Copart selector, get the text content (the lot number)
                        lot_text = await lot_elem.text_content()
                        if lot_text and lot_text.strip():
                            # Extract just the numeric part
                            import re
                            lot_match = re.search(r'(\d+)', lot_text.strip())
                            if lot_match:
                                data['lot_number'] = lot_match.group(1)
                                print(f"Found lot number with selector {selector}: {data['lot_number']}")
                                break
                except Exception as e:
                    print(f"Error with lot number selector {selector}: {e}")
                    continue

        except Exception as e:
            print(f"Error extracting lot details from iframe: {e}")

    async def _check_main_page_auction_status(self, data):
        """Check main page for auction status indicators"""
        try:
            # Look for auction status messages on main page
            status_indicators = [
                'text="auction is live"',
                'text="auction in progress"',
                'text="bidding is open"',
                'text="auction running"',
                '.auction-status',
                '.live-auction'
            ]

            for indicator in status_indicators:
                try:
                    if indicator.startswith('text='):
                        elements = self.page.locator(indicator)
                    else:
                        elements = self.page.locator(indicator)

                    count = await elements.count()
                    if count > 0:
                        data['status'] = 'active'
                        print(f"Found auction status indicator: {indicator}")
                        break
                except:
                    continue

            # Check for "auction ended" or similar
            ended_indicators = [
                'text="auction has ended"',
                'text="auction closed"',
                'text="bidding closed"'
            ]

            for indicator in ended_indicators:
                try:
                    elements = self.page.locator(indicator)
                    count = await elements.count()
                    if count > 0:
                        data['status'] = 'ended'
                        print(f"Found auction ended indicator: {indicator}")
                        break
                except:
                    continue

        except Exception as e:
            print(f"Error checking main page auction status: {e}")

    async def _extract_data_from_iframe(self, data):
        """Extract auction data from iframe if accessible"""
        target = self.auction_frame

        # Current bid - look for SVG text elements in auctionrunningdiv-MACRO
        try:
            # First try the SVG text elements from the HTML structure
            bid_text_elem = target.locator('.auctionrunningdiv-MACRO text[fill="#0757ac"]').first
            if await bid_text_elem.is_visible(timeout=1000):
                bid_text = await bid_text_elem.text_content()
                if bid_text and bid_text.strip():
                    data['current_bid'] = bid_text.strip()
                    print(f"Found bid in SVG text: {data['current_bid']}")
            else:
                # Fallback to other selectors
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
        except Exception as e:
            print(f"Error extracting bid from iframe: {e}")

        # Current bidder - look for SVG text elements in auctionrunningdiv-MACRO
        try:
            # Look for black text elements in the auction div (excluding "Bid!")
            bidder_texts = target.locator('.auctionrunningdiv-MACRO text[fill="black"]')
            bidder_count = await bidder_texts.count()
            for i in range(bidder_count):
                bidder_text = await bidder_texts.nth(i).text_content()
                bidder_text = bidder_text.strip()
                if bidder_text and bidder_text != 'Bid!' and not bidder_text.startswith('$'):
                    data['current_bidder'] = bidder_text
                    print(f"Found bidder in SVG text: {data['current_bidder']}")
                    break
        except Exception as e:
            print(f"Error extracting bidder from iframe: {e}")
            # Fallback to other selectors
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

    async def _check_network_auction_data(self, data):
        """Check recent network activity for auction data"""
        try:
            # Check recent WebSocket messages for auction data
            if hasattr(self, 'websocket_messages') and self.websocket_messages:
                recent_messages = [msg for msg in self.websocket_messages
                                 if (datetime.now() - datetime.fromisoformat(msg['timestamp'])).seconds < 30]

                for msg in recent_messages:
                    try:
                        msg_data = msg['data']
                        if isinstance(msg_data, str):
                            msg_json = json.loads(msg_data)
                        else:
                            msg_json = msg_data

                        # Look for auction data in message
                        if 'bid' in str(msg_json).lower():
                            print(f"Found auction data in WebSocket: {msg_json}")
                            # Extract relevant data
                            if 'currentBid' in msg_json:
                                data['current_bid'] = str(msg_json['currentBid'])
                            if 'currentBidder' in msg_json:
                                data['current_bidder'] = str(msg_json['currentBidder'])
                            if 'timeRemaining' in msg_json:
                                data['time_remaining'] = str(msg_json['timeRemaining'])
                            if 'status' in msg_json:
                                data['status'] = str(msg_json['status'])

                    except:
                        continue

        except Exception as e:
            print(f"Error checking network auction data: {e}")

    async def _setup_network_monitoring(self):
        """Set up network monitoring to capture auction data from WebSocket/API calls"""
        try:
            print('Setting up network monitoring for auction data...')

            # Monitor WebSocket connections
            self.websocket_messages = []

            def handle_websocket_message(msg):
                try:
                    if 'g2auction.copart.com' in msg.url or 'auction' in msg.url.lower():
                        print(f'WebSocket message from {msg.url}: {msg}')
                        self.websocket_messages.append({
                            'url': msg.url,
                            'data': msg,
                            'timestamp': datetime.now().isoformat()
                        })
                except:
                    pass

            # Monitor network requests to auction domains
            def handle_request(request):
                try:
                    url = request.url
                    if 'g2auction.copart.com' in url or ('auction' in url.lower() and 'copart' in url.lower()):
                        print(f'Auction API request: {request.method} {url}')
                        if request.post_data:
                            print(f'Request data: {request.post_data}')
                except:
                    pass

            def handle_response(response):
                try:
                    url = response.url
                    if 'g2auction.copart.com' in url or ('auction' in url.lower() and 'copart' in url.lower()):
                        print(f'Auction API response: {response.status} {url}')
                        # Try to get response body for auction data
                        try:
                            content = response.text()
                            if content and ('bid' in content.lower() or 'auction' in content.lower()):
                                print(f'Response content: {content[:500]}...')
                        except:
                            pass
                except:
                    pass

            # Set up request/response monitoring on context to capture iframe requests
            self.context.on('request', handle_request)
            self.context.on('response', handle_response)

            print('Network monitoring setup complete')
            logging.info('Network monitoring setup complete - monitoring for auction API calls')

        except Exception as e:
            print(f'Failed to set up network monitoring: {e}')

    async def _setup_mutation_observer(self):
        """Set up MutationObserver to detect real-time DOM changes, specifically bid changes"""
        try:
            print('_setup_mutation_observer: Checking auction frame...')
            if not self.auction_frame:
                print('_setup_mutation_observer: No auction frame found, skipping observer setup')
                return

            # Wait for auction content to load
            print('Waiting for auction content to load...')
            try:
                await self.auction_frame.locator('.auctionrunningdiv-MACRO').wait_for(timeout=30000)
                print('Auction content loaded (.auctionrunningdiv-MACRO found)')
            except Exception as e:
                print(f'Auction content not loaded within 30 seconds: {e}')
                print('Proceeding with observer setup anyway...')

            # JavaScript code to set up MutationObserver for auctionrunningdiv-MACRO content changes
            observer_js = """
            (function() {
                console.log('Setting up auction content observer...');

                // Initialize global observer storage if not exists
                if (!window.auctionObservers) {
                    window.auctionObservers = [];
                }

                let lastBid = null;
                let lastBidder = null;
                let mutationCount = 0;

                // Function to extract current bid, bidder, bid suggestion, and lot information
                function getCurrentBidInfo() {
                    const auctionDiv = document.querySelector('.auctionrunningdiv-MACRO');
                    if (!auctionDiv) return null;

                    // Get bid amount from blue text elements
                    const bidElements = auctionDiv.querySelectorAll('text[fill="#0757ac"]');
                    let currentBid = null;
                    for (let elem of bidElements) {
                        const text = elem.textContent.trim();
                        if (text && text.startsWith('$')) {
                            currentBid = text;
                            break;
                        }
                    }

                    // Get bidder from black text elements (excluding "Bid!")
                    const bidderElements = auctionDiv.querySelectorAll('text[fill="black"]');
                    let currentBidder = null;
                    for (let elem of bidderElements) {
                        const text = elem.textContent.trim();
                        if (text && text !== 'Bid!' && !text.startsWith('$')) {
                            currentBidder = text;
                            break;
                        }
                    }

                    // Get bid suggestion from input field
                    const bidInput = document.querySelector('input[name="bidAmount"], input[data-uname="bidAmount"]');
                    let bidSuggestion = null;
                    if (bidInput) {
                        bidSuggestion = bidInput.value || bidInput.textContent;
                        if (bidSuggestion) {
                            bidSuggestion = bidSuggestion.trim();
                        }
                    }

                    // Extract lot title and number
                    let lotTitle = null;
                    let lotNumber = null;

                    // Extract lot title
                    const titleSelectors = [
                        '.titlelbl.ellipsis[title]',
                        '.lot-title',
                        '.vehicle-title',
                        'h1',
                        '[data-uname*="title"]'
                    ];

                    for (const selector of titleSelectors) {
                        const titleElem = document.querySelector(selector);
                        if (titleElem) {
                            const titleText = titleElem.getAttribute('title') || titleElem.textContent;
                            if (titleText && titleText.trim()) {
                                lotTitle = titleText.trim();
                                break;
                            }
                        }
                    }

                    // Extract lot number
                    const lotNumberSelectors = [
                        '.itempair .titlelbl.ellipsis[href*="lot/"]',
                        '.lot-number',
                        '.lot-num',
                        '#LotNumber',
                        'span[data-uname="lotdetailVinvalue"]',
                        '[data-uname*="lot"]'
                    ];

                    for (const selector of lotNumberSelectors) {
                        const lotElem = document.querySelector(selector);
                        if (lotElem) {
                            const lotText = lotElem.textContent;
                            if (lotText && lotText.trim()) {
                                const match = lotText.match(/(\d+)/);
                                if (match) {
                                    lotNumber = match[1];
                                    break;
                                }
                            }
                        }
                    }

                    return {
                        bid: currentBid,
                        bidder: currentBidder,
                        bidSuggestion: bidSuggestion,
                        lotTitle: lotTitle,
                        lotNumber: lotNumber,
                        timestamp: new Date().toISOString()
                    };
                }

                // Set up MutationObserver for the auction div
                const targetNode = document.querySelector('.auctionrunningdiv-MACRO');
                if (targetNode) {
                    console.log('Found .auctionrunningdiv-MACRO, setting up observer');

                    const observer = new MutationObserver(function(mutations) {
                        mutationCount++;
                        console.log('Mutation detected #' + mutationCount);

                        const bidInfo = getCurrentBidInfo();
                        if (bidInfo && bidInfo.bid && bidInfo.bidder) {
                            // Check if bid or bidder changed
                            if (bidInfo.bid !== lastBid || bidInfo.bidder !== lastBidder) {
                                console.log('BID_CHANGE:' + JSON.stringify(bidInfo));
                                lastBid = bidInfo.bid;
                                lastBidder = bidInfo.bidder;
                            }
                        }
                    });

                    observer.observe(targetNode, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true,
                        attributeFilter: ['fill', 'x', 'y', 'text-anchor']
                    });

                    // Store observer reference for cleanup
                    window.auctionObservers.push(observer);

                    console.log('Bid change observer set up successfully');
                } else {
                    console.log('auctionrunningdiv-MACRO not found, observer not set up');
                }
            })();
            """

            # Inject the JavaScript into the iframe
            # Try using FrameLocator's evaluate method (available in newer Playwright versions)
            try:
                await self.auction_frame.evaluate(observer_js)
                print('Successfully injected JavaScript into iframe')
            except AttributeError:
                print('FrameLocator.evaluate not available, trying alternative method')
                # Alternative: use page.evaluate to target the iframe
                try:
                    # Find the iframe and execute script in its context
                    frames = self.page.frames
                    target_frame = None
                    for frame in frames:
                        if 'g2auction.copart.com' in frame.url:
                            target_frame = frame
                            break

                    if target_frame:
                        await target_frame.evaluate(observer_js)
                        print('Successfully injected JavaScript into iframe via frame reference')
                    else:
                        print('Could not find target frame for JavaScript injection')
                except Exception as e:
                    print(f'Failed to inject JavaScript into iframe: {e}')
            except Exception as e:
                print(f'JavaScript injection failed: {e}')

            # Set up console message listener to capture updates
            self.page.on('console', self._handle_console_message)

            print('Bid change observer setup complete')
            logging.info('Bid change observer setup complete - monitoring for bid changes')

        except Exception as e:
            print(f'Failed to set up bid change observer: {e}')

    def _handle_console_message(self, msg):
        """Handle console messages from the page, including MutationObserver updates"""
        try:
            text = msg.text
            if text.startswith('BID_CHANGE:'):
                # Parse the bid change update
                json_data = text[11:]  # Remove 'BID_CHANGE:' prefix
                bid_data = json.loads(json_data)

                # Extract current lot information from the bid change data (sent by JavaScript)
                current_lot_title = bid_data.get('lotTitle', self.current_auction_data.get('lot_title', 'N/A'))
                current_lot_number = bid_data.get('lotNumber', self.current_auction_data.get('lot_number', 'N/A'))

                # Update stored lot information if it changed
                if current_lot_title != 'N/A':
                    self.current_auction_data['lot_title'] = current_lot_title
                if current_lot_number != 'N/A':
                    self.current_auction_data['lot_number'] = current_lot_number

                # Update current data
                bid_suggestion = bid_data.get('bidSuggestion', 'N/A')
                self.current_auction_data.update({
                    'current_bid': bid_data.get('bid', 'N/A'),
                    'current_bidder': bid_data.get('bidder', 'N/A'),
                    'bid_suggestion': bid_suggestion
                })
                self.last_update = datetime.now().isoformat()

                print(f"Updated auction data - Bid: {bid_data.get('bid', 'N/A')}, Suggestion: {bid_suggestion}")

                # Print bid change notification with suggestion
                bid_suggestion = bid_data.get('bidSuggestion', 'N/A')
                suggestion_text = f", Suggestion={bid_suggestion}" if bid_suggestion != 'N/A' else ""
                console_message = f"🚨 BID CHANGE DETECTED: Bid={bid_data.get('bid', 'N/A')}, Bidder={bid_data.get('bidder', 'N/A')}{suggestion_text} at {bid_data.get('timestamp', 'N/A')}"
                lot_message = f"   📋 Lot: {current_lot_title} (#{current_lot_number})"

                print(console_message)
                print(lot_message)

                # Emit WebSocket event for bid change notification
                if self.socketio:
                    try:
                        # Emit the formatted message to display in web interface
                        self.socketio.emit('bid_change_notification', {
                            'message': console_message + '\n' + lot_message,
                            'type': 'bid_change',
                            'timestamp': bid_data.get('timestamp', datetime.now().isoformat())
                        })

                        # Also emit regular auction update
                        self.socketio.emit('auction_update', {
                            'is_monitoring': self.is_monitoring,
                            'current_auction': self.current_auction_data,
                            'last_update': self.last_update,
                            'content_change': True,
                            'lot_title': current_lot_title,
                            'lot_number': current_lot_number,
                            'bid_suggestion': bid_suggestion
                        })
                        print("WebSocket events emitted for bid change")
                    except Exception as e:
                        print(f"Failed to emit WebSocket event: {e}")

            elif text.startswith('AUCTION_UPDATE:'):
                # Parse the general auction data update (fallback)
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