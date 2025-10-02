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
from datetime import date, datetime
import math
import base64
import httpx
import urllib
import hashlib
from json import dumps

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

# hCaptcha Challenger integration
try:
    from hcaptcha_challenger.agents.playwright.control import Radagon
    from hcaptcha_challenger import ModelHub
    HCAPTCHA_CHALLENGER_AVAILABLE = True
    print("hcaptcha-challenger available")
except ImportError as e:
    HCAPTCHA_CHALLENGER_AVAILABLE = False
    print(f"hcaptcha-challenger not available: {e}")
    print("Install with: pip install hcaptcha-challenger")
    print("Or run with: python -m pip install hcaptcha-challenger")

# Configuration
SOLVECAPTCHA_API_KEY = os.environ.get('SOLVECAPTCHA_API_KEY')
if not SOLVECAPTCHA_API_KEY:
    print("Warning: SOLVECAPTCHA_API_KEY not found in environment variables")
    print("Set it in your .env file or environment")

PROXY = os.environ.get('PROXY')
if not PROXY:
    print("Warning: PROXY not found - will use SolveCaptcha API if available")
    print("Set PROXY in your .env file for free hCaptcha bypass (format: ip:port or user:pass@ip:port)")

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

# hCaptcha bypass headers and functions (from https://github.com/avengy/hcaptcha-bypass-discord)
headers = {
    "Host": "hcaptcha.com",
    "Connection": "keep-alive",
    "sec-ch-ua": 'Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92',
    "Accept": "application/json",
    "sec-ch-ua-mobile": "?0",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
    "Content-type": "application/json; charset=utf-8",
    "Origin": "https://newassets.hcaptcha.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://newassets.hcaptcha.com/",
    "Accept-Language": "en-US,en;q=0.9"
}

def N_Data(req) -> str:
    try:
        """
        this part takes the req value inside the getsiteconfig and converts it into our hash, we need this for the final step.
        (thanks to h0nde for this function btw, you can find the original code for this at the top of the file.)
        """
        x = "0123456789/:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

        req = req.split(".")

        req = {
            "header": json.loads(
                base64.b64decode(
                    req[0] +
                    "=======").decode("utf-8")),
            "payload": json.loads(
                base64.b64decode(
                    req[1] +
                    "=======").decode("utf-8")),
            "raw": {
                "header": req[0],
                "payload": req[1],
                "signature": req[2]}}

        def a(r):
            for t in range(len(r) - 1, -1, -1):
                if r[t] < len(x) - 1:
                    r[t] += 1
                    return True
                r[t] = 0
            return False

        def i(r):
            t = ""
            for n in range(len(r)):
                t += x[r[n]]
            return t

        def o(r, e):
            n = e
            hashed = hashlib.sha1(e.encode())
            o = hashed.hexdigest()
            t = hashed.digest()
            e = None
            n = -1
            o = []
            for n in range(n + 1, 8 * len(t)):
                e = t[math.floor(n / 8)] >> n % 8 & 1
                o.append(e)
            a = o[:r]

            def index2(x, y):
                if y in x:
                    return x.index(y)
                return -1
            return 0 == a[0] and index2(a, 1) >= r - 1 or -1 == index2(a, 1)

        def get():
            for e in range(25):
                n = [0 for i in range(e)]
                while a(n):
                    u = req["payload"]["d"] + "::" + i(n)
                    if o(req["payload"]["s"], u):
                        return i(n)

        result = get()
        hsl = ":".join([
            "1",
            str(req["payload"]["s"]),
            datetime.now().isoformat()[:19]
            .replace("T", "")
            .replace("-", "")
            .replace(":", ""),
            req["payload"]["d"],
            "",
            result
        ])
        return hsl
    except Exception as e:
        print(e)
        return False

def REQ_Data(host, sitekey, proxy):
    try:
        r = httpx.get(f"https://hcaptcha.com/checksiteconfig?host={host}&sitekey={sitekey}&sc=1&swa=1", headers=headers, proxies={"https://": f"http://{proxy}"}, timeout=4)
        if r.json()["pass"]:
            return r.json()["c"]
        else:
            return False
    except:
        return False

def Get_Captcha(host, sitekey, n, req, proxy):
    try:
        json_data = {
            "sitekey": sitekey,
            "v": "b1129b9",
            "host": host,
            "n": n,
            'motiondata': '{"st":1628923867722,"mm":[[203,16,1628923874730],[155,42,1628923874753],[137,53,1628923874770],[122,62,1628923874793],[120,62,1628923875020],[107,62,1628923875042],[100,61,1628923875058],[93,60,1628923875074],[89,59,1628923875090],[88,59,1628923875106],[87,59,1628923875131],[87,59,1628923875155],[84,56,1628923875171],[76,51,1628923875187],[70,47,1628923875203],[65,44,1628923875219],[63,42,1628923875235],[62,41,1628923875251],[61,41,1628923875307],[58,39,1628923875324],[54,38,1628923875340],[49,36,1628923875363],[44,36,1628923875380],[41,35,1628923875396],[40,35,1628923875412],[38,35,1628923875428],[38,35,1628923875444],[37,35,1628923875460],[37,35,1628923875476],[37,35,1628923875492]],"mm-mp":13.05084745762712,"md":[[37,35,1628923875529]],"md-mp":0,"mu":[[37,35,1628923875586]],"mu-mp":0,"v":1,"topLevel":{"st":1628923867123,"sc":{"availWidth":1680,"availHeight":932,"width":1680,"height":1050,"colorDepth":30,"pixelDepth":30,"availLeft":0,"availTop":23},"nv":{"vendorSub":"","productSub":"20030107","vendor":"Google Inc.","maxTouchPoints":0,"userActivation":{},"doNotTrack":null,"geolocation":{},"connection":{},"webkitTemporaryStorage":{},"webkitPersistentStorage":{},"hardwareConcurrency":12,"cookieEnabled":true,"appCodeName":"Mozilla","appName":"Netscape","appVersion":"5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36","platform":"MacIntel","product":"Gecko","userAgent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36","language":"en-US","languages":["en-US","en"],"onLine":true,"webdriver":false,"serial":{},"scheduling":{},"xr":{},"mediaCapabilities":{},"permissions":{},"locks":{},"usb":{},"mediaSession":{},"clipboard":{},"credentials":{},"keyboard":{},"mediaDevices":{},"storage":{},"serviceWorker":{},"wakeLock":{},"deviceMemory":8,"hid":{},"presentation":{},"userAgentData":{},"bluetooth":{},"managed":{},"plugins":["internal-pdf-viewer","mhjfbmdgcfjbbpaeojofohoefgiehjai","internal-nacl-plugin"]},"dr":"https://discord.com/","inv":false,"exec":false,"wn":[[1463,731,2,1628923867124],[733,731,2,1628923871704]],"wn-mp":4580,"xy":[[0,0,1,1628923867125]],"xy-mp":0,"mm":[[1108,233,1628923867644],[1110,230,1628923867660],[1125,212,1628923867678],[1140,195,1628923867694],[1158,173,1628923867711],[1179,152,1628923867727],[1199,133,1628923867744],[1221,114,1628923867768],[1257,90,1628923867795],[1272,82,1628923867811],[1287,76,1628923867827],[1299,71,1628923867844],[1309,68,1628923867861],[1315,66,1628923867877],[1326,64,1628923867894],[1331,62,1628923867911],[1336,60,1628923867927],[1339,58,1628923867944],[1343,56,1628923867961],[1345,54,1628923867978],[1347,53,1628923867994],[1348,52,1628923868011],[1350,51,1628923868028],[1354,49,1628923868045],[1366,44,1628923868077],[1374,41,1628923868094],[1388,36,1628923868110],[1399,31,1628923868127],[1413,25,1628923868144],[1424,18,1628923868161],[1436,10,1628923868178],[1445,3,1628923868195],[995,502,1628923871369],[722,324,1628923874673],[625,356,1628923874689],[523,397,1628923874705],[457,425,1628923874721]],"mm-mp":164.7674418604651},"session":[],"widgetList":["0a1l5c3yudk4"],"widgetId":"0a1l5c3yudk4","href":"https://discord.com/register","prev":{"escaped":false,"passed":false,"expiredChallenge":false,"expiredResponse":false}}',
            "hl": "en",
            "c": dumps(req)
        }

        data = urllib.parse.urlencode(json_data)
        headers_post = {
            "Host": "hcaptcha.com",
            "Connection": "keep-alive",
            "sec-ch-ua": 'Chromium";v="92", " Not A;Brand";v="99", "Google Chrome";v="92',
            "Accept": "application/json",
            "sec-ch-ua-mobile": "?0",
            "Content-length": str(len(data)),
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36",
            "Content-type": "application/x-www-form-urlencoded",
            "Origin": "https://newassets.hcaptcha.com",
            "Sec-Fetch-Site": "same-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": "https://newassets.hcaptcha.com/",
            "Accept-Language": "en-US,en;q=0.9"
        }

        cookies = {"hc_accessibility": "wAHi1MOKSosBLK6HVeeBzfbaQknsYZOOkIB/s3TXYK3NzxiIzJ3HzV6uQOMlyTSI1GIVz9AazrmLIgl7NAufVofFaQDhnTL9CNyhqVwlaibJmi6mQrr377HrCaTI7VCWxo1kniMjJDOEz4X29+NH5awd4jH6hPyKIOZhNjWuMrNSKu6ZFLuRSgOiy4c+0idoOSRYiOiX9HK8KkQaHk8EfkR05vRrjPBkaNVKqg1RcpcfREQ06gIS9YzkItTt+2z/aHHZU1rAdJTyJ8oijsq2Mis23zqp9EWQ52H4oWEstionkOct9Z8NgybESmrdNsowi3NXNOoVwWoU4ZEwGCbjG8eO+2HnSP1vPKUi6tT7Z39E2eCMAJJDn9dyenkOuFRcOMmFiMIIIFsTUniyM7EhvSWxWDFvI+4zbx/+TP5pQClZJcLbXinpw1SMk3GVT3S6EG2n/DyLQ0/p3+/CJYbr7sVjdeRLQBGyCMvaOPy+dvaRH+mszz58EoV35sq9835SPRD17jNym9E="}
        r = httpx.post(f"https://hcaptcha.com/getcaptcha?s={sitekey}", cookies=cookies, data=data, headers=headers_post, timeout=4, proxies={"https://": f"http://{proxy}"})

        return r.json()
    except Exception as e:
        print(e)
        return False

def bypass(sitekey, host, proxy):
    try:
        req = REQ_Data(sitekey=sitekey, host=host, proxy=proxy)
        req["type"] = "hsl"
        n = N_Data(req["req"])
        res = Get_Captcha(sitekey=sitekey, host=host, proxy=proxy, n=n, req=req)
        if "generated_pass_UUID" in res:
            captcha = res["generated_pass_UUID"]
            return captcha
        else:
            return False
    except:
        return False

async def solve_hcaptcha_with_challenger(page, site_key, page_url):
    """Solve hCaptcha using hcaptcha-challenger library"""
    if not HCAPTCHA_CHALLENGER_AVAILABLE:
        print("hcaptcha-challenger not available, falling back to other methods")
        return False

    try:
        print("Solving hCaptcha with hcaptcha-challenger (local AI)...")

        # First, check if there's already a challenge active
        challenge_selectors = [
            '.rc-imageselect',
            '.rc-image-tile',
            '.challenge-container',
            '[aria-describedby*="rc-imageselect"]'
        ]

        challenge_active = False
        for selector in challenge_selectors:
            try:
                if await page.locator(selector).is_visible(timeout=1000):
                    challenge_active = True
                    print(f"Challenge already active: {selector}")
                    break
            except:
                continue

        # If no challenge is active, click the checkbox to trigger one
        if not challenge_active:
            print("No active challenge found, clicking hCaptcha checkbox to trigger challenge...")

            # hCaptcha checkbox selectors (more comprehensive)
            checkbox_selectors = [
                '.h-captcha',  # Click the hCaptcha div directly
                '.h-captcha iframe',  # Click the hCaptcha iframe directly
                '[data-sitekey]',  # Click any element with sitekey
                '[data-sitekey] iframe',  # Any iframe within sitekey element
                'iframe[src*="hcaptcha"]',  # hCaptcha iframe by src
                '.recaptcha-checkbox-border',  # Fallback to reCAPTCHA selectors
                '.rc-anchor-checkbox',
                '[role="checkbox"]',
                '.recaptcha-checkbox'
            ]

            checkbox_clicked = False
            for selector in checkbox_selectors:
                try:
                    print(f"Trying checkbox selector: {selector}")
                    element = page.locator(selector).first

                    # Check if element is visible and clickable
                    if await element.is_visible(timeout=2000):
                        print(f"Found clickable element with selector: {selector}")
                        await element.click()
                        print(f"Clicked element with selector: {selector}")
                        checkbox_clicked = True
                        await asyncio.sleep(3)  # Wait for challenge to appear
                        break

                except Exception as e:
                    print(f"Error with selector {selector}: {e}")
                    continue

            if not checkbox_clicked:
                print("Could not find or click hCaptcha checkbox/iframe")
                print("Try clicking the checkbox manually in the browser to test the solver")
                # Don't return False here - let the solver run anyway in case challenge appears

        # Initialize ModelHub and Radagon solver
        modelhub = ModelHub()
        solver = Radagon(page=page, modelhub=modelhub)

        # The solver should automatically handle the hCaptcha challenge
        print("Radagon solver initialized - solving hCaptcha challenge...")

        # Wait for the solver to complete (it handles the challenge automatically)
        await asyncio.sleep(5)  # Give more time for solving

        # Check if we got a token (hCaptcha sets h-captcha-response)
        try:
            token_check = await page.evaluate("document.querySelector('[name=\"h-captcha-response\"]')?.value || null")
        except Exception as js_error:
            print(f"JavaScript evaluation error: {js_error}")
            token_check = None

        if token_check and len(token_check) > 10:
            print(f"hcaptcha-challenger solved! Token found: {token_check[:50]}...")
            return token_check  # Return the token directly
        else:
            print("No token found after solving attempt")
            # Check if challenge is still present
            challenge_still_active = False
            for selector in challenge_selectors:
                try:
                    if await page.locator(selector).is_visible(timeout=1000):
                        challenge_still_active = True
                        break
                except:
                    continue

            if challenge_still_active:
                print("Challenge still active - solver may need more time or failed")
            else:
                print("Challenge completed but no token found - possible solver issue")
            return False

    except Exception as e:
        print(f"Error solving hCaptcha with challenger: {e}")
        return False

async def solve_hcaptcha(sitekey, page_url, page):
    """Solve hCaptcha using challenger (primary), free bypass (secondary), or SolveCaptcha API (fallback)"""
    # Try hCaptcha Challenger first (local, free, fast)
    if HCAPTCHA_CHALLENGER_AVAILABLE:
        print("Trying hCaptcha Challenger (local AI solver)...")
        try:
            token = await solve_hcaptcha_with_challenger(page, sitekey, page_url)
            if token:
                print("hCaptcha solved successfully with hCaptcha Challenger!")
                print(f"Token: {token[:50]}...")
                return {
                    'token': token,
                    'user_agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"
                }
        except Exception as e:
            print(f"Error with hCaptcha Challenger: {e}")

    # Try free bypass if proxy available
    if PROXY:
        print(f"Attempting free hCaptcha bypass with proxy: {PROXY}")
        try:
            host = "www.iaai.com"  # Extract domain from page_url if needed
            token = bypass(sitekey, host, PROXY)
            if token:
                print("hCaptcha solved successfully with free bypass!")
                print(f"Token: {token[:50]}...")
                return {
                    'token': token,
                    'user_agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36"  # From bypass headers
                }
            else:
                print("Free bypass failed, falling back to SolveCaptcha API")
        except Exception as e:
            print(f"Error with free bypass: {e}, falling back to SolveCaptcha API")

    # Fallback to SolveCaptcha API
    if not SOLVECAPTCHA_API_KEY:
        print("No SolveCaptcha API key available and other methods failed")
        return None

    try:
        print(f"Solving hCaptcha with sitekey: {sitekey} using SolveCaptcha API")

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
                solution = await solve_hcaptcha(sitekey, page_url, page)

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