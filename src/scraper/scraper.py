import asyncio
import httpx
from bs4 import BeautifulSoup
from ..core.config import env_settings

BASE_URL = env_settings.SCRAPING_BASE_URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}

# Track duplicate URLs.
seen_url = set()


async def get_soup(client: httpx.AsyncClient, url: str) -> BeautifulSoup | None:
    """
    Fetch a URL asynchronously and parse the response HTML into a BeautifulSoup object.

    Args:
        client: httpx.AsyncClient instance.
        url: The URL to fetch.

    Returns:
        A BeautifulSoup object if the request succeeds, otherwise None.
    """

    try:
        print("BASE URL FETCHING: ", url)

        # Exit early for redundant URLs.
        if not url.startswith("https://help.zipboard.co"):
            return None
        if url in seen_url:
            print(f"Already seen {url}, skipping to avoid duplicates.")
            return None

        seen_url.add(url)
        response = await client.get(url, headers=HEADERS)

        # Back off and try again if rate-limited.
        if response.status_code == 429:
            print("⚠️ Rate limited. Backing off...")
            await asyncio.sleep(4)
            return await get_soup(client, url)

        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None
