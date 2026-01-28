import asyncio
import random
from playwright.async_api import async_playwright

# Some common User-Agents (rotate them)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:118.0) Gecko/20100101 Firefox/118.0",
]

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,  # keep visible to avoid detection
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-gpu",
            ]
        )

        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )

        # Rotate headers
        headers = {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.google.com/",
            "DNT": "1",  # Do Not Track
        }
        await context.set_extra_http_headers(headers)

        page = await context.new_page()

        # Go to target site
        url = "https://in.linkedin.com/jobs/view/full-stack-developer-at-persistent-systems-4205909192?position=7&pageNum=0&refId=%2BQORexgpoD%2BSb3zAsqQy0w%3D%3D&trackingId=bZjvDi95hy155YF7QK3m6g%3D%3D"
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Check if status is 200 but body is empty
        body_text = await page.evaluate("document.body.innerText")
        if response.status == 200 and len(body_text.strip()) == 0:
            print("⚠️ Bot detected → Page is empty despite 200 status code")
        else:
            print("✅ Page loaded fine")

        # Pause for inspector testing
        await page.pause()

        # Example locator test
        try:
            quote = await page.locator(".quote").first.text_content()
            print("First quote:", quote)
        except Exception:
            print("❌ Could not locate element → Possibly blocked")

        await browser.close()

asyncio.run(run())