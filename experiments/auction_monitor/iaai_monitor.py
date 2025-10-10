#!/usr/bin/env python3
"""
IAAI Auction Monitor - Monitors IAAI AuctionNow pages for real-time updates
Adapted from Copart monitor for IAAI's AuctionNow bidding interface
"""

import asyncio
import time
import os
import json
import random
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page, Browser, BrowserContext

from hcaptcha_challenger import AgentV, AgentConfig


class HcaptchaSolver:
    """Production-ready hCaptcha solver integration."""

    def __init__(self):
        """Initialize with production-ready configuration."""
        self.agent_config = AgentConfig(
            # API key loaded from environment/.env
            EXECUTION_TIMEOUT=120,    # 2 minutes for complex challenges
            RESPONSE_TIMEOUT=30,      # 30 seconds for API responses
            RETRY_ON_FAILURE=True,    # Auto-retry failed challenges

            # Optimized model selection
            IMAGE_CLASSIFIER_MODEL="gemini-2.5-flash",      # Fast binary classification
            SPATIAL_POINT_REASONER_MODEL="gemini-2.5-flash", # Fast point selection
            SPATIAL_PATH_REASONER_MODEL="gemini-2.5-pro",    # Accurate drag-drop

            # Production settings
            enable_challenger_debug=False,  # Disable debug logging in production
        )

    async def detect_captcha_in_frame(self, frame: Page, depth: int = 0) -> Optional[Page]:
        """Recursively detect CAPTCHA in a frame and its child frames, returning the frame containing CAPTCHA"""
        try:
            # Check for CAPTCHA iframes in this frame
            captcha_selectors = [
                "iframe[src*='hcaptcha.com']",
                "iframe[src*='newassets.hcaptcha.com']",
            ]

            for selector in captcha_selectors:
                try:
                    elements = frame.locator(selector)
                    count = await elements.count()
                    if count > 0:
                        print(f"Found {count} CAPTCHA iframes with selector: {selector}")
                        return frame
                except Exception:
                    continue

            # Check for iframes in this frame
            iframes = frame.locator('iframe')
            iframe_count = await iframes.count()
            if iframe_count > 0:
                print(f"Found {iframe_count} iframes in frame at depth {depth}")

            for i in range(iframe_count):
                try:
                    iframe = iframes.nth(i)
                    # Recursively check child frames
                    try:
                        element = await iframe.element_handle()
                        child_frame = await element.content_frame()
                    except Exception as e:
                        print(f"Error getting content frame for iframe {i}: {e}")
                        continue
                    if child_frame:
                        # Recurse into child frame
                        result = await self.detect_captcha_in_frame(child_frame, depth + 1)
                        if result:
                            return result

                except Exception as e:
                    print(f"Error checking iframe {i}: {e}")

            return None

        except Exception as e:
            print(f"Error in frame detection: {e}")
            return None

    async def solve_hcaptcha_if_present(self, page: Page) -> bool:
        """
        Check for and solve hCaptcha challenges on a page.

        Args:
            page: Playwright page object

        Returns:
            bool: True if hCaptcha was solved successfully or no hCaptcha found
        """
        try:
            # Use custom detection for initial CAPTCHA check
            captcha_frame = await self.detect_captcha_in_frame(page, 0)
            if captcha_frame:
                print("hCaptcha detected, initializing solver...")

                # Manually click the checkbox
                frame_locator = captcha_frame.frame_locator("iframe[title='Widget containing checkbox for hCaptcha security challenge']")
                checkbox = frame_locator.locator("#checkbox")
                await checkbox.click()
                print("Clicked checkbox")

                # Initialize AgentV and solve the challenge
                agent = AgentV(page=page, agent_config=self.agent_config)

                # Wait for and solve challenge
                await agent.wait_for_challenge()

                # Check result
                if agent.cr_list:
                    latest_result = agent.cr_list[-1]
                    success = latest_result.is_pass
                    print(f"hCaptcha result: {'SOLVED' if success else 'FAILED'}")
                    return success
                else:
                    print("No hCaptcha response received")
                    return False
            else:
                # No hCaptcha found, continue normally
                return True

        except Exception as e:
            print(f"hCaptcha solving error: {e}")
            return False


class WebsiteAutomationBot:
    """Bot for IAAI login and session management."""

    def __init__(self):
        self.hcaptcha_solver = HcaptchaSolver()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.state_file = "../hctest/browser_state.json"

    async def setup_browser(self, headless: bool = False, browser_args: Optional[List[str]] = None):
        """Setup browser with anti-detection measures."""
        if browser_args is None:
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-blink-features=AutomationControlled",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--disable-renderer-backgrounding",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-extensions",
                "--disable-default-apps"
            ]

        playwright = await async_playwright().start()

        self.browser = await playwright.chromium.launch(
            headless=headless,
            args=browser_args
        )

        if os.path.exists(self.state_file):
            print(f"Loading saved session from {self.state_file}")
            self.context = await self.browser.new_context(
                storage_state=self.state_file,
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )
        else:
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York"
            )

        return playwright

    async def login_with_hcaptcha_handling(
        self,
        url: str,
        username: str,
        password: str,
        selectors: Optional[Dict[str, str]] = None,
        close_page: bool = True
    ) -> Tuple[bool, Optional[Page]]:
        """
        Login to IAAI with automatic hCaptcha handling.

        Args:
            url: Login page URL
            username: Username/email
            password: Password
            selectors: Dict of selectors for form elements (email, password, submit)

        Returns:
            Tuple[bool, Optional[Page]]: (success, page) - page is returned if close_page=False
        """
        if selectors is None:
            selectors = {
                "email": 'input[name="Input.Email"]',
                "password": 'input[name="Input.Password"]',
                "submit": 'button[type="submit"]'
            }

        if not self.context:
            await self.setup_browser()

        page = await self.context.new_page()

        try:
            print(f"Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Fill login form
            await page.fill(selectors["email"], username)
            await page.fill(selectors["password"], password)

            # Click login button
            await page.click(selectors["submit"])

            await page.wait_for_timeout(3000)
            # Handle any hCaptcha that appears
            hcaptcha_success = await self.hcaptcha_solver.solve_hcaptcha_if_present(page)

            if hcaptcha_success:
                # Wait a bit for login to complete
                await page.wait_for_timeout(3000)

                # Check if login was successful based on session cookies
                cookies = await page.context.cookies()
                session_cookies = [c for c in cookies if 'session' in c['name'].lower() or 'auth' in c['name'].lower()]
                login_successful = len(session_cookies) > 0
                if login_successful:
                    print(f"Login successful - found {len(session_cookies)} session/auth cookies: {[c['name'] for c in session_cookies]}")
                else:
                    print("Login may have failed - no session/auth cookies found")

                if login_successful:
                    print("Login successful!")

                    # Handle IAAI-specific post-login redirect
                    await page.wait_for_timeout(5000)
                    print("Checking for Log In link to redirect to dashboard")
                    links = page.locator('a[href="/Dashboard/Default"][aria-label="Log In"]')
                    count = await links.count()
                    for i in range(count):
                        if await links.nth(i).is_visible():
                            await links.nth(i).click()
                            print(f"Clicked visible Log In link at index {i}")
                            # Wait for redirect to Dashboard
                            await page.wait_for_url("**/Dashboard/Default")
                            print("Redirected to Dashboard")
                            break

                    # Save session state for future use
                    await self.context.storage_state(path=self.state_file)
                    print(f"Session state saved to {self.state_file}")
                    return True, page if not close_page else None
                else:
                    print("Login may have failed - check page content")
                    return False, page if not close_page else None
            else:
                print("Failed to solve hCaptcha")
                return False, page if not close_page else None

        except Exception as e:
            print(f"Login automation error: {e}")
            return False, page if not close_page else None

        finally:
            if close_page:
                await page.close()

    async def cleanup(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()


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


class IAAIAuctionMonitor:
    """Monitors IAAI AuctionNow pages and extracts real-time data"""

    def __init__(self, socketio_instance=None):
        self.is_monitoring = False
        self.current_auction_data = None
        self.last_update = None
        self.browser = None
        self.page = None
        self.auction_frame = None
        self.throttler = RequestThrottler()
        self.socketio = socketio_instance
        self._frame_navigation_handler = None
        self._manual_bid_highlight_requested = False
        self._manual_plus_highlight_requested = False
        logging.basicConfig(filename='iaai_auction_monitor.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def start_monitoring(self, auction_url):
        """Start monitoring an auction with login"""
        self.is_monitoring = True

        try:
            # Load environment variables
            await self._load_env()

            # Initialize browser and login to IAAI
            await self._init_browser_and_login()

            # Navigate to the auction page
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
        print("Stopping IAAI auction monitoring and cleaning up listeners...")

        # Clean up MutationObservers in the page
        if self.page:
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

                    console.log('MutationObserver cleanup completed');
                })();"""

                # Try to inject cleanup JavaScript
                try:
                    self.page.evaluate(cleanup_js)
                    print("✅ MutationObserver cleanup completed")
                except Exception as e:
                    print(f"⚠️ Could not clean up MutationObservers: {e}")

            except Exception as e:
                print(f"⚠️ Error during cleanup: {e}")

        self.is_monitoring = False
        print("IAAI auction monitoring stopped")

    async def _load_env(self):
        """Load environment variables from all available .env files"""
        env_paths = ['../.env', '../hctest/.env', '../../experiments/.env']
        loaded_files = []

        for env_path in env_paths:
            print(f"Checking for .env file at: {env_path}")
            if os.path.exists(env_path):
                print(f"Found .env file at: {env_path}")
                loaded_files.append(env_path)
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # Only set if not already set (first file wins for duplicates)
                            if key not in os.environ:
                                os.environ[key] = value
                                print(f"Loaded env var: {key}")

                                # Map IAAI credentials to expected names
                                if key == 'IAAI_USERNAME':
                                    os.environ['USER_EMAIL'] = value
                                    print(f"Mapped IAAI_USERNAME to USER_EMAIL: {value}")
                                elif key == 'IAAI_PASSWORD':
                                    os.environ['PASSWORD'] = value
                                    print(f"Mapped IAAI_PASSWORD to PASSWORD: {'*' * len(value)}")
                                elif key == 'USER_EMAIL':
                                    print(f"Found USER_EMAIL: {value}")
                                elif key == 'PASSWORD':
                                    print(f"Found PASSWORD: {'*' * len(value)}")
                                elif key == 'LOGIN_URL':
                                    print(f"Found LOGIN_URL: {value[:50]}...")
            else:
                print(f"No .env file found at: {env_path}")

        print(f"Loaded environment variables from: {loaded_files}")

    async def _init_browser_and_login(self):
        """Initialize browser and login to IAAI"""
        print("Initializing browser and logging into IAAI...")

        # Get login credentials from environment
        login_url = os.getenv("LOGIN_URL", "https://login.iaai.com/Identity/Account/Login?ReturnUrl=%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3DAuctionCenterPortal%26redirect_uri%3Dhttps%253A%252F%252Fwww.iaai.com%252Fsignin-oidc%26response_type%3Dcode%26scope%3Dopenid%2520profile%2520email%2520phone%2520offline_access%2520BuyerProfileClaims%26code_challenge%3DaZOhwfZVTzvbOer65mWAoRrG7_YU3yC3QUzl4Q4QSbE%26code_challenge_method%3DS256%26response_mode%3Dform_post%26nonce%3D638951629817524796.MjE3ODI4NTktNmVhMC00NzQ4LThkZTMtNDU4YzI5ZWFkZmRlNzZhNGE4ZDMtNjFiMy00ZmM5LWE2YTctMzFmOWNlNmQ0Zjdm%26state%3DCfDJ8DRA0jV6pYhPksRz74aoaTjqCnxypg8wlSvUXrW-OCbBUHMR4PM3jgIpLNW3Mx5Biu_WJYY9FGdQrcSHQ90X7EgqzvA-jlFR9ucs0FKZWxXDg-N8dMbs-PZ0GDqLRtmC_b0YwueFfsHuBJC8Cj-btcblXekNb0jC8qkztaZHgiz-VKFLD2qJ0KON5ae44Nal76cbpUitHCRKkrg924rB5alPTos_4J2cN05c1ZFVn-UZdBVhak7GKHYPDkzl-aLxrb21yU6JzU7g8mTig_jOibi9WfzKoAiLMtSd8WcpaKvbrpEf9kyfLuT-_ZgmEA0h1El0frc2xeDsVUh3lF-N9tTlK8J_fMOu2lgfR5-NZiAsybDr2UTfhweC_4K2_Jlju1SGX7PnWBrvOerI4ecqSTn8v9mqx09m9pKtZR578M3dqP_SL8fyjmzaKgD9_EANl2HbKcirvhAOYX-dn1lo1ctFHXVvb4J_cvPPno_0bAOj")
        user_email = os.getenv("USER_EMAIL")
        password = os.getenv("PASSWORD")

        print(f"LOGIN_URL: {login_url}")
        print(f"USER_EMAIL: {user_email}")
        print(f"PASSWORD: {'*' * len(password) if password else None}")

        if not all([user_email, password]):
            print("Missing required environment variables: USER_EMAIL, PASSWORD")
            print(f"Available env vars: {list(os.environ.keys())}")
            raise Exception("Missing required environment variables: USER_EMAIL, PASSWORD")

        # Initialize the WebsiteAutomationBot for login
        self.automation_bot = WebsiteAutomationBot()

        # Login with hCaptcha handling
        print(f"Logging into IAAI with user: {user_email}")
        login_success, self.page = await self.automation_bot.login_with_hcaptcha_handling(
            url=login_url,
            username=user_email,
            password=password,
            close_page=False
        )

        if not login_success or not self.page:
            raise Exception("IAAI login failed")

    async def _navigate_to_auction(self, auction_url):
        """Navigate to the auction page"""
        print(f'Navigating to auction: {auction_url}')

        if not auction_url.startswith('http'):
            auction_url = f"https://www.iaai.com{auction_url}"

        print('Going to auction URL...')
        await self.page.goto(auction_url, timeout=60000)
        print('Waiting for page load...')
        await self.page.wait_for_load_state('load', timeout=30000)

        # Wait for LeaveAuctionConfirmationModal to appear (up to 20 seconds)
        modal_appeared = False
        try:
            await self.page.wait_for_selector('#LeaveAuctionConfirmationModal', timeout=20000)
            modal_appeared = True
            print("LeaveAuctionConfirmationModal appeared")
        except:
            try:
                await self.page.wait_for_selector('.LeaveAuctionConfirmationModal', timeout=20000)
                modal_appeared = True
                print("LeaveAuctionConfirmationModal appeared (class selector)")
            except:
                print("LeaveAuctionConfirmationModal did not appear within 20 seconds")

        if modal_appeared:
            print("LeaveAuctionConfirmationModal detected, clicking OK...")

            # Click OK button
            ok_selectors = [
                '#LeaveAuctionConfirmationOk',
                'button[data-actionname="LeaveAuctionConfirmationOk"]',
                '#LeaveAuctionConfirmationOkVCB',
                '.modal__footer button[data-actionname="LeaveAuctionConfirmationOk"]'
            ]

            for ok_sel in ok_selectors:
                try:
                    ok_button = self.page.locator(ok_sel).first
                    if await ok_button.is_visible(timeout=2000):
                        print(f"Found OK button with selector: {ok_sel}")
                        await ok_button.click()
                        print("Clicked OK on LeaveAuctionConfirmationModal")
                        await self.page.wait_for_timeout(3000)  # Wait for modal to close
                        break
                except Exception as e:
                    print(f"Failed to click OK button with selector {ok_sel}: {e}")
                    continue

        print(f'Page title after navigation: {await self.page.title()}')
        print(f'Current URL: {self.page.url}')

    async def _monitor_auction(self):
        """Main monitoring loop"""
        print('Starting IAAI auction monitoring...')

        # Initial data extraction
        auction_data = await self._extract_auction_data()
        self.current_auction_data = auction_data
        self.last_update = datetime.now().isoformat()

        print(f"Initial data: Item={auction_data['current_item']}, Status={auction_data['bid_status']}")

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
                # Sleep briefly to prevent busy waiting
                await asyncio.sleep(1)

                # Periodic health check
                current_time = time.time()
                if not hasattr(self, '_last_health_check') or current_time - self._last_health_check > 30:
                    self._last_health_check = current_time

                    try:
                        auction_data = await self._extract_auction_data()
                        self.current_auction_data = auction_data
                        self.last_update = datetime.now().isoformat()
                        print(f"Health check update: Item={auction_data['current_item']}, Status={auction_data['bid_status']}")

                    except Exception as extract_error:
                        print(f"Data extraction failed during health check: {extract_error}")

                # Check for manual highlight requests
                if self._manual_bid_highlight_requested:
                    try:
                        print("🔵 Processing manual bid highlight request in monitoring thread...")
                        await self._highlight_bid_button_manual_impl()
                        self._manual_bid_highlight_requested = False
                    except Exception as manual_error:
                        print(f"❌ Manual bid highlight failed: {manual_error}")

                if self._manual_plus_highlight_requested:
                    try:
                        print("🔴 Processing manual plus highlight request in monitoring thread...")
                        await self._highlight_plus_button_manual_impl()
                        self._manual_plus_highlight_requested = False
                    except Exception as manual_error:
                        print(f"❌ Manual plus highlight failed: {manual_error}")

            except Exception as e:
                print(f'Monitoring error: {str(e)}')
                await asyncio.sleep(5)

    async def _extract_auction_data(self):
        """Extract current auction data from the page"""
        data = {
            'auction_id': 'Unknown',
            'current_item': 'N/A',
            'stock_number': 'N/A',
            'asking_bid': 'N/A',
            'high_bidder_location': 'N/A',
            'bid_status': 'N/A',
            'status': 'unknown',
            'active_bidders': 0,
            'last_update': datetime.now().isoformat()
        }

        try:
            # Extract auction data from page
            await self._extract_data_from_page(data)

        except Exception as e:
            print(f"Error extracting auction data: {e}")

        return data

    async def _extract_data_from_page(self, data):
        """Extract auction data from the IAAI page"""
        try:
            # Current item
            item_selectors = [
                '.run-list__item-name',
                '.item-name',
                '[data-bind*="ItemName"]'
            ]

            for selector in item_selectors:
                try:
                    item_elem = self.page.locator(selector).first
                    if await item_elem.is_visible(timeout=1000):
                        data['current_item'] = await item_elem.text_content()
                        break
                except:
                    continue

            # Stock number
            stock_selectors = [
                '.stock-number .data-list__value',
                '[data-bind*="StockNumber"]'
            ]

            for selector in stock_selectors:
                try:
                    stock_elem = self.page.locator(selector).first
                    if await stock_elem.is_visible(timeout=1000):
                        stock_text = await stock_elem.text_content()
                        # Extract just the number
                        import re
                        match = re.search(r'(\d+)', stock_text)
                        if match:
                            data['stock_number'] = match.group(1)
                        break
                except:
                    continue

            # Asking bid
            asking_selectors = [
                '.bid-area__amount[data-askingamount]',
                '.asking-bid'
            ]

            for selector in asking_selectors:
                try:
                    asking_elem = self.page.locator(selector).first
                    if await asking_elem.is_visible(timeout=1000):
                        data['asking_bid'] = await asking_elem.text_content()
                        break
                except:
                    continue

            # High bidder location
            location_selectors = [
                '.high-bid__location',
                '.bidder-location'
            ]

            for selector in location_selectors:
                try:
                    location_elem = self.page.locator(selector).first
                    if await location_elem.is_visible(timeout=1000):
                        data['high_bidder_location'] = await location_elem.text_content()
                        break
                except:
                    continue

            # Bid status
            status_selectors = [
                '.run-list__state-name',
                '.auction-status'
            ]

            for selector in status_selectors:
                try:
                    status_elem = self.page.locator(selector).first
                    if await status_elem.is_visible(timeout=1000):
                        data['bid_status'] = await status_elem.text_content()
                        break
                except:
                    continue

        except Exception as e:
            print(f"Error extracting data from page: {e}")

    async def _setup_mutation_observer(self):
        """Set up MutationObserver for real-time DOM changes, specifically bid changes"""
        try:
            print('_setup_mutation_observer: Checking auction frame...')
            if not self.page:
                print('_setup_mutation_observer: No page found, skipping observer setup')
                return

            # Wait for auction content to load
            print('Waiting for auction content to load...')
            try:
                await self.page.locator('#auctionEvents').wait_for(timeout=30000)
                print('Auction content loaded (#auctionEvents found)')
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

                let lastItem = null;
                let lastBid = null;
                let lastStatus = null;
                let lastStockNumber = null;
                let mutationCount = 0;

                // Function to extract current bid, bidder, bid suggestion, and lot information
                function getCurrentAuctionInfo() {
                    // Get current item
                    let currentItem = null;
                    const itemSelectors = [
                        '.run-list__item-name',
                        '.item-name',
                        '[data-bind*="ItemName"]'
                    ];

                    for (const selector of itemSelectors) {
                        const itemElems = document.querySelectorAll(selector);
                        for (const itemElem of itemElems) {
                            if (itemElem && itemElem.textContent && itemElem.textContent.trim()) {
                                currentItem = itemElem.textContent.trim();
                                break;
                            }
                        }
                        if (currentItem) break;
                    }

                    // Get current bid (asking bid)
                    let currentBid = null;
                    const bidSelectors = [
                        '.bid-area__amount[data-askingamount]',
                        '.asking-bid'
                    ];

                    for (const selector of bidSelectors) {
                        const bidElems = document.querySelectorAll(selector);
                        for (const bidElem of bidElems) {
                            if (bidElem && bidElem.textContent && bidElem.textContent.trim()) {
                                currentBid = bidElem.textContent.trim();
                                break;
                            }
                        }
                        if (currentBid) break;
                    }

                    // Get bid status
                    let bidStatus = null;
                    const statusSelectors = [
                        '.run-list__state-name',
                        '.auction-status'
                    ];

                    for (const selector of statusSelectors) {
                        const statusElems = document.querySelectorAll(selector);
                        for (const statusElem of statusElems) {
                            if (statusElem && statusElem.textContent && statusElem.textContent.trim()) {
                                bidStatus = statusElem.textContent.trim();
                                break;
                            }
                        }
                        if (bidStatus) break;
                    }

                    // Get stock number
                    let stockNumber = null;
                    const stockSelectors = [
                        '.stock-number .data-list__value',
                        '[data-bind*="StockNumber"]'
                    ];

                    for (const selector of stockSelectors) {
                        const stockElems = document.querySelectorAll(selector);
                        for (const stockElem of stockElems) {
                            if (stockElem && stockElem.textContent && stockElem.textContent.trim()) {
                                const stockText = stockElem.textContent.trim();
                                // Extract just the number
                                const match = stockText.match(/(\\d+)/);
                                if (match) {
                                    stockNumber = match[1];
                                    break;
                                }
                            }
                        }
                        if (stockNumber) break;
                    }

                    return {
                        item: currentItem,
                        bid: currentBid,
                        status: bidStatus,
                        stockNumber: stockNumber,
                        timestamp: new Date().toISOString()
                    };
                }

                // Set up MutationObserver for the auction div
                const targetNode = document.querySelector('#auctionEvents') || document.body;
                if (targetNode) {
                    console.log('Found #auctionEvents, setting up observer');

                    const observer = new MutationObserver(function(mutations) {
                        mutationCount++;
                        console.log('Mutation detected #' + mutationCount);

                        const auctionInfo = getCurrentAuctionInfo();
                        if (auctionInfo && (auctionInfo.item || auctionInfo.bid || auctionInfo.status || auctionInfo.stockNumber)) {
                            // Check if bid or bidder changed
                            if (auctionInfo.item !== lastItem || auctionInfo.bid !== lastBid || auctionInfo.status !== lastStatus || auctionInfo.stockNumber !== lastStockNumber) {
                                console.log('BID_CHANGE:' + JSON.stringify(auctionInfo));
                                lastItem = auctionInfo.item;
                                lastBid = auctionInfo.bid;
                                lastStatus = auctionInfo.status;
                                lastStockNumber = auctionInfo.stockNumber;
                            }
                        }
                    });

                    observer.observe(targetNode, {
                        childList: true,
                        subtree: true,
                        characterData: true,
                        attributes: true,
                        attributeFilter: ['class', 'data-uname']
                    });

                    // Store observer reference for cleanup
                    window.auctionObservers.push(observer);

                    console.log('Bid change observer set up successfully');
                } else {
                    console.log('#auctionEvents not found, observer not set up');
                }
            })();"""

            # Inject the JavaScript into the page
            await self.page.evaluate(observer_js)
            print('Successfully injected JavaScript into IAAI page')

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

                # Update stored lot information if it changed
                if bid_data.get('item'):
                    self.current_auction_data['current_item'] = bid_data.get('item', 'N/A')
                if bid_data.get('stockNumber'):
                    self.current_auction_data['stock_number'] = bid_data.get('stockNumber', 'N/A')

                # Update current data
                self.current_auction_data.update({
                    'asking_bid': bid_data.get('bid', 'N/A'),
                    'bid_status': bid_data.get('status', 'N/A')
                })
                self.last_update = datetime.now().isoformat()

                print(f"Updated auction data - Item: {bid_data.get('item', 'N/A')}, Asking Bid: {bid_data.get('bid', 'N/A')}, Status: {bid_data.get('status', 'N/A')}")

                # Emit WebSocket event for bid change notification
                if self.socketio:
                    try:
                        # Emit the formatted message to display in web interface
                        self.socketio.emit('bid_change_notification', {
                            'message': f"🚨 BID CHANGE DETECTED: Item={bid_data.get('item', 'N/A')}, Asking Bid={bid_data.get('bid', 'N/A')}, Status={bid_data.get('status', 'N/A')} at {bid_data.get('timestamp', 'N/A')}",
                            'type': 'bid_change',
                            'timestamp': bid_data.get('timestamp', datetime.now().isoformat())
                        })

                        # Also emit regular auction update
                        self.socketio.emit('auction_update', {
                            'is_monitoring': self.is_monitoring,
                            'current_auction': self.current_auction_data,
                            'last_update': self.last_update,
                            'content_change': True,
                            'current_item': bid_data.get('item', 'N/A'),
                            'stock_number': bid_data.get('stockNumber', 'N/A'),
                            'asking_bid': bid_data.get('bid', 'N/A'),
                            'bid_status': bid_data.get('status', 'N/A')
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
                print(f"Real-time update: Item={auction_data.get('current_item', 'N/A')}, Status={auction_data.get('bid_status', 'N/A')}")

        except Exception as e:
            # Ignore non-auction-update console messages
            pass

    async def _highlight_bid_button_manual(self):
        """Manually highlight the bid button"""
        print("🔵 Manual IAAI bid button highlight requested")
        self._manual_bid_highlight_requested = True
        return True

    async def _highlight_bid_button_manual_impl(self):
        """Highlight the bid button"""
        print("🔵 Starting manual IAAI bid button highlight...")
        try:
            button_selectors = [
                'button[data-uname*="bid"]',
                '.bid-button',
                'button:has-text("Bid")',
                'button[class*="bid"]'
            ]

            for selector in button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if await button.is_visible(timeout=1000):
                        await button.evaluate("""
                            (element) => {
                                const originalStyles = {
                                    backgroundColor: element.style.backgroundColor,
                                    border: element.style.border,
                                    color: element.style.color
                                };

                                element.style.setProperty('background-color', '#0066ff', 'important');
                                element.style.setProperty('border', '3px solid #003399', 'important');
                                element.style.setProperty('color', '#ffffff', 'important');

                                setTimeout(() => {
                                    element.style.setProperty('background-color', originalStyles.backgroundColor, 'important');
                                    element.style.setProperty('border', originalStyles.border, 'important');
                                    element.style.setProperty('color', originalStyles.color, 'important');
                                }, 3000);
                            }
                        """)
                        print("🔵 Manual IAAI bid button highlight applied")
                        return True
                except:
                    continue

            print("❌ No IAAI bid button found")
            return False

        except Exception as e:
            print(f"❌ Manual IAAI bid button highlighting failed: {e}")
            return False

    async def _highlight_plus_button_manual(self):
        """Manually highlight the plus button"""
        print("🔴 Manual IAAI plus button highlight requested")
        self._manual_plus_highlight_requested = True
        return True

    async def find_bid_button(self, auction_url):
        """Complete bid button finder functionality - simplified version"""
        try:
            print(f"🔍 Starting bid button finder for auction: {auction_url}")

            # Load environment variables
            self._load_env()

            # Initialize browser if not already done
            if not self.browser:
                await self._init_browser()

            # Login to IAAI if not already logged in
            await self._login_to_iaai()

            # Navigate to auction
            if not auction_url.startswith('http'):
                auction_url = f"https://www.iaai.com{auction_url}"

            print('Going to auction URL...')
            await self.page.goto(auction_url, timeout=60000)
            print('Waiting for page load...')
            await self.page.wait_for_load_state('load', timeout=30000)

            print(f'Page title after navigation: {await self.page.title()}')
            print(f'Current URL: {self.page.url}')

            # Try to find bid button
            button_selectors = [
                'button[data-uname*="bid"]',
                '.bid-button',
                'button:has-text("Bid")',
                'button[class*="bid"]'
            ]

            for selector in button_selectors:
                try:
                    button = self.page.locator(selector).first
                    if await button.is_visible(timeout=5000):
                        print(f"✅ Found bid button with selector: {selector}")

                        # Highlight the button
                        await button.evaluate("""
                            (element) => {
                                const originalStyles = {
                                    backgroundColor: element.style.backgroundColor,
                                    border: element.style.border,
                                    color: element.style.color
                                };

                                element.style.setProperty('background-color', '#00ff00', 'important');
                                element.style.setProperty('border', '3px solid #ff0000', 'important');
                                element.style.setProperty('color', '#000000', 'important');

                                setTimeout(() => {
                                    element.style.setProperty('background-color', originalStyles.backgroundColor, 'important');
                                    element.style.setProperty('border', originalStyles.border, 'important');
                                    element.style.setProperty('color', originalStyles.color, 'important');
                                }, 3000);
                            }
                        """)

                        print("🎨 Bid button highlighted successfully")
                        await asyncio.sleep(5)  # Keep browser open to see highlight
                        return True
                except:
                    continue

            print("❌ No bid button found")
            return False

        except Exception as e:
            print(f"Bid button finder failed: {e}")
            return False

    async def _highlight_plus_button_manual_impl(self):
        """Highlight the plus button"""
        print("🔴 Starting manual IAAI plus button highlight...")
        try:
            plus_selectors = [
                'button[data-uname*="plus"]',
                'button[data-uname*="increase"]',
                '.plus-button',
                'button:has-text("+")',
                'button[class*="plus"]'
            ]

            for selector in plus_selectors:
                try:
                    button = self.page.locator(selector).first
                    if await button.is_visible(timeout=1000):
                        await button.click()
                        await button.evaluate("""
                            (element) => {
                                const originalStyles = {
                                    backgroundColor: element.style.backgroundColor,
                                    border: element.style.border,
                                    color: element.style.color
                                };

                                element.style.setProperty('background-color', '#ff4444', 'important');
                                element.style.setProperty('border', '3px solid #cc0000', 'important');
                                element.style.setProperty('color', '#ffffff', 'important');

                                setTimeout(() => {
                                    element.style.setProperty('background-color', originalStyles.backgroundColor, 'important');
                                    element.style.setProperty('border', originalStyles.border, 'important');
                                    element.style.setProperty('color', originalStyles.color, 'important');
                                }, 3000);
                            }
                        """)
                        print("🔴 Manual IAAI plus button highlight applied")
                        return True
                except:
                    continue

            print("❌ No IAAI plus button found")
            return False

        except Exception as e:
            print(f"❌ Manual IAAI plus button highlighting failed: {e}")
            return False
