import pandas as pd
import asyncio
import random
from datetime import datetime
from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------
INPUT_FILE = "all_jobs_enriched.csv"   # <-- use your enriched file
OUTPUT_FILE = "all_enriched_jobs_updated.csv"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:118.0) Gecko/20100101 Firefox/118.0",
]

# ---------------- UTILS ----------------
async def jitter(page):
    """Random human-like wait (1–5 seconds)."""
    wait_time = random.uniform(1000, 5000)  # ms
    print(f"⏳ Jitter wait: {wait_time/1000:.2f} sec")
    await page.wait_for_timeout(wait_time)

# ---------------- SCRAPER ----------------
async def scrape_about(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        about = await page.locator("div.show-more-less-html__markup").all_text_contents()
        return " ".join(about).strip()
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

# ---------------- MAIN ----------------
async def main():
    df = pd.read_csv(INPUT_FILE)
    df_copy = df.copy()

    # Process only first 51 rows with missing about
    processed = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
        )
        page = await context.new_page()

        for i, row in df_copy.iterrows():
            if pd.notna(row["about"]) and str(row["about"]).strip() != "":
                continue  # skip already filled rows

            if processed >= 51:
                break  # stop after 51 updates

            url = row["job_link"]
            print(f"🔗 Scraping about ({processed+1}/51): {url}")

            about_text = await scrape_about(page, url)
            df_copy.at[i, "about"] = about_text

            processed += 1

            if processed % 10 == 0:  # save every 10 updates
                df_copy.to_csv(OUTPUT_FILE, index=False)
                print(f"💾 Progress saved at {processed} rows")

            await jitter(page)  # random pause
            await page.wait_for_timeout(random.randint(3000, 8000))  # base pause

        # Final save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"all_enriched_jobs_backup_{timestamp}.csv"
        df_copy.to_csv(OUTPUT_FILE, index=False)
        df_copy.to_csv(backup_file, index=False)
        print(f"Done! Updated first 51 abouts. Saved {OUTPUT_FILE} & {backup_file}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
