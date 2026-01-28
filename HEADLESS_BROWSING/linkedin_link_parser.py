import pandas as pd
import asyncio
import random
import time
from datetime import datetime
from playwright.async_api import async_playwright

# ---------------- CONFIG ----------------
INPUT_FILE = "all_jobs.csv"
OUTPUT_FILE = "all_jobs_enriched.csv"

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
async def scrape_job(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)

        job_title = await page.locator("h1").first.text_content()
        about = await page.locator("div.show-more-less-html__markup").all_text_contents()
        about_text = " ".join(about).strip()

        # Extract paragraphs for classification
        skills, experience = "", ""
        paragraphs = about_text.split("\n")
        for para in paragraphs:
            p = para.lower().strip()
            if p.startswith("skills") or p.startswith("qualifications"):
                skills = para
            elif p.startswith("experience") or p.startswith("requirements"):
                experience = para

        # Employment type
        try:
            employment_type = await page.get_by_role("heading", name="Employment type").locator("xpath=..").inner_text()
        except Exception:
            employment_type = ""

        return {
            "job_title": job_title,
            "about": about_text,
            "skills": skills,
            "experience": experience,
            "employment_type": employment_type,
        }

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return {
            "job_title": "",
            "about": "",
            "skills": "",
            "experience": "",
            "employment_type": "",
        }

# ---------------- MAIN ----------------
async def main():
    df = pd.read_csv(INPUT_FILE)
    df_copy = df.copy()

    new_cols = ["job_title", "about", "skills", "experience", "employment_type"]
    for col in new_cols:
        if col not in df_copy.columns:
            df_copy[col] = None

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
            if i < 50:  # ⬅️ Skip first 50 jobs
                continue

            url = row["job_link"]
            print(f"🔗 Scraping ({i+1}/{len(df_copy)}): {url}")

            job_data = await scrape_job(page, url)
            for col, val in job_data.items():
                df_copy.at[i, col] = val

            # Save progress every 5 jobs
            if (i + 1) % 5 == 0:
                df_copy.to_csv(OUTPUT_FILE, index=False)
                print(f"💾 Progress saved at row {i+1}")

            # Random waits
            await jitter(page)  # 1–5 sec jitter
            await page.wait_for_timeout(random.randint(3000, 8000))  # 3–8 sec base delay

        # Final save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"all_jobs_enriched_{timestamp}.csv"
        df_copy.to_csv(OUTPUT_FILE, index=False)
        df_copy.to_csv(backup_file, index=False)
        print(f"✅ All done! Saved {OUTPUT_FILE} and backup {backup_file}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
