import os
from serpapi import GoogleSearch


def fetch_jobs(
    keyword: str,
    location: str,
    page_token: str | None = None
) -> dict:
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise RuntimeError("SERPAPI_API_KEY not found in environment")

    params = {
        "engine": "google_jobs",
        "q": keyword,
        "location": location,
        "hl": "en",
        "gl": "in",
        "google_domain": "google.com",
        "api_key": api_key
    }

    if page_token:
        params["next_page_token"] = page_token

    search = GoogleSearch(params)
    result = search.get_dict()

    if not result:
        raise RuntimeError("Empty response from SerpAPI")

    if "error" in result:
        raise RuntimeError(result["error"])

    return result
