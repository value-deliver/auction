#!/usr/bin/env python3
"""
Simple script to navigate to IAAI.com and click the Log In link.
"""

import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navigating to https://www.iaai.com")
        await page.goto("https://www.iaai.com", wait_until="domcontentloaded")

        await page.wait_for_timeout(50000)
        print("Waiting for Log In link and clicking...")

        links = page.locator('a[href="/Dashboard/Default"][aria-label="Log In"]')
        count = await links.count()
        for i in range(count):
            if await links.nth(i).is_visible():
                await links.nth(i).click()
                print(f"Clicked visible link at index {i}")
                break
            else:
                print("No visible Log In link found")

        print("Waiting for Log In link and clicking...")
        
        # Keep the browser open for a bit to see the result
        await page.wait_for_timeout(5000)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())