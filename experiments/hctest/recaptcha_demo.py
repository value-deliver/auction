import asyncio
import os

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from solvecaptcha import Solvecaptcha

# Load environment variables
load_dotenv()


async def main() -> None:
    # Get API key from environment
    api_key = os.getenv("SOLVECAPTCHA_API_KEY")
    if not api_key:
        print("SOLVECAPTCHA_API_KEY not found in environment")
        return

    # Create solver
    solver = Solvecaptcha(api_key)

    # Solve reCAPTCHA v2
    sitekey = "6Le-wvkSAAAAAPBMRTvw0Q4Muexq9bi0DJwx_mJ-"
    url = "https://www.google.com/recaptcha/api2/demo"

    try:
        result = solver.recaptcha(sitekey=sitekey, url=url)
        token = result['code']
        print(f"reCAPTCHA token: {token}")

        # Now use Playwright to set the token and submit
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(url)

            # Set the token in the hidden textarea using JavaScript
            await page.evaluate(f'document.querySelector(\'textarea[name="g-recaptcha-response"]\').value = "{token}";')

            # Submit the form
            await page.click('#recaptcha-demo-submit')

            # Wait a bit to see the result
            await page.wait_for_timeout(5000)

            # Check if success message appears or something
            # For demo, just print success
            print("Form submitted with token")

            await page.wait_for_timeout(10000)
            await browser.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())