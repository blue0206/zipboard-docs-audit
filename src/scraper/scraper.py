import asyncio
import httpx
from urllib.parse import urljoin
from typing import List
from bs4 import BeautifulSoup, Tag
from ..models.scraping_schema import Article, ArticleContent, Category, Collection
from ..core.config import env_settings

BASE_URL = env_settings.SCRAPING_BASE_URL
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
}

# Limit concurrent requests to fetch article (default = 2).
semaphore = asyncio.Semaphore(env_settings.SCRAPING_CONCURRENT_REQUESTS)
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


async def scrape_article(
    client: httpx.AsyncClient, url: str, name: str
) -> Article | None:
    """
    Scrape a single help article page and extract structured content.

    This function parses the article DOM sequentially and converts headings,
    paragraphs, callouts, videos, images, tables, and lists into normalized
    ArticleContent blocks suitable for LLM ingestion and spreadsheet export.

    Args:
        client: httpx.AsyncClient instance.
        url: URL of the article page.
        name: The name of the article.

    Returns:
        An Article object containing structured content and metadata,
        or None if the article cannot be retrieved or parsed.

    Extracted Metadata:
        - Article ID (derived from URL)
        - Title
        - Last updated timestamp
        - Word count
        - Presence flags for images, videos, and tables

    Notes:
        - The function respects rate-limiting by using a semaphore and adding delays.
    """

    async with semaphore:
        await asyncio.sleep(0.5)
        article_soup = await get_soup(client, url)
        if not article_soup:
            print(f"Failed to retrieve {name} article url.")
            return None

        article = article_soup.select_one("article#fullArticle")
        if not article:
            print(f"No article content found for {name}.")
            return None

        article_contents: List[ArticleContent] = []

        # Extract title.
        title = article.select_one("h1.title")
        title = title.get_text(strip=True) if title else "No Title"

        # Extract timestamp.
        timestamp = article_soup.select_one("time.lu")
        timestamp = timestamp.get("datetime", "Unknown") if timestamp else "Unknown"

        # Init bool vars for image/table/video presence.
        has_videos = False
        has_images = False
        has_tables = False

        # Traverse article DOM and accumulate the article content.
        for node in article.children:
            if not isinstance(node, Tag):
                continue

            # Extract heading.
            if node.name in ["h1", "h2", "h3"]:
                article_contents.append(
                    ArticleContent(
                        type="heading",
                        level=int(node.name[1]),
                        text=node.get_text(),
                        id=node.get("id", ""),  # type: ignore
                    )
                )
            # Extract image (defensively checked both <div> and <p> tags)
            elif (node.name == "p" or node.name == "div") and node.find("img"):
                has_images = True

                img = node.find("img")
                article_contents.append(
                    ArticleContent(
                        type="image",
                        src=urljoin(url, img.get("src", "")),  # type: ignore
                        alt=img.get("alt", ""),  # type: ignore
                    )
                )
            # Extract image from <img> tag (defensive check)
            elif node.name == "img":
                has_images = True

                article_contents.append(
                    ArticleContent(
                        type="image",
                        src=urljoin(url, node.get("src", "")),  # type: ignore
                        alt=node.get("alt", ""),  # type: ignore
                    )
                )
            # Extract paragraphs (main article content)
            elif node.name == "p":
                text = node.get_text(strip=True)
                if text:
                    article_contents.append(ArticleContent(type="paragraph", text=text))
            # Extract green callout box
            elif node.name == "div" and "callout-green" in node.get("class", []):  # type: ignore
                text = node.get_text(strip=True)
                article_contents.append(
                    ArticleContent(
                        type="callout",
                        text=text,
                        variant="info",
                    )
                )
            # Extract red callout box
            elif node.name == "div" and "callout-red" in node.get("class", []):  # type: ignore
                text = node.get_text(strip=True)
                article_contents.append(
                    ArticleContent(
                        type="callout",
                        text=text,
                        variant="warn",
                    )
                )
            # Extract video
            elif node.name == "div" and "video" in node.get("class", []):  # type: ignore
                has_videos = True

                iframe = node.find("iframe")
                if iframe and iframe.get("src"):
                    article_contents.append(
                        ArticleContent(
                            type="video",
                            src=iframe["src"],  # type: ignore
                            platform="youtube",
                        )
                    )
            # Extract video not inside a div
            elif node.name == "iframe":
                has_videos = True

                if node.get("src"):
                    article_contents.append(
                        ArticleContent(
                            type="video",
                            src=node["src"],  # type: ignore
                            platform="youtube",
                        )
                    )
            # Extract table contents
            elif node.name == "table":
                has_tables = True

                headers: List[str] = []
                first_row = node.find("tr")
                if first_row:
                    headers = [
                        cell.get_text(strip=True)
                        for cell in first_row.find_all(["th", "td"])
                    ]

                rows: List[List[str]] = []
                for tr in node.find_all("tr")[1:]:
                    row: List[str] = [
                        td.get_text(strip=True) for td in tr.find_all("td")
                    ]
                    if row:
                        rows.append(row)

                article_contents.append(
                    ArticleContent(type="table", headers=headers, rows=rows)
                )
            # Extract lists items
            elif node.name in ["ul", "ol"]:
                items: List[str] = [
                    item.get_text(" ", strip=True)
                    for item in node.find_all("li", recursive=False)
                ]

                article_contents.append(
                    ArticleContent(type="list", ordered=node.name == "ol", items=items)
                )

        word_count = sum(
            len(block.text.split()) if block.text else 0 for block in article_contents
        )

        # Extract article id from URL (e.g. '295' in /article/295-how-integrate-zipboard-lambdatest)
        article_id = (
            url.split("/")[-1].split("-")[0] if "-" in url.split("/")[-1] else "Unknown"
        )

        return Article(
            article_id=article_id,
            article_title=title,
            url=url,
            content=article_contents,
            last_updated=timestamp,  # type: ignore
            word_count=word_count,
            has_screenshots=has_images,
            has_videos=has_videos,
            has_tables=has_tables,
        )


async def scrape_category(
    client: httpx.AsyncClient, url: str, name: str
) -> Category | None:
    """
    Scrape a help category page and recursively scrape all articles within it.

    Args:
        client: httpx.AsyncClient instance.
        url: URL of the category page.
        name: The name of the category.

    Returns:
        A Category object containing metadata and a list of scraped Article objects,
        or None if the category page cannot be retrieved.

    Notes:
        - Article links are resolved relative to the category URL.
        - Categories without valid articles are skipped.
        - The articles are scraped concurrently.
    """

    category_soup = await get_soup(client, url)
    if not category_soup:
        print(f"Failed to retrieve {name} category url.")
        return None

    # Extract title.
    title = category_soup.select_one("h1")
    title = title.get_text(strip=True) if title else "No Title"

    # Extract description.
    description = category_soup.select_one("p.descrip")
    description = description.get_text(strip=True) if description else None

    # Extract paylods for each article in the category by retrieving the HTML content
    # from the article links on the category page and parsing it.
    tasks = []
    article_links = category_soup.select("a[href*='/article/']")
    category_articles: List[Article] = []

    for link in article_links:
        article_url = urljoin(url, link["href"])  # type: ignore
        article_name = link.get_text(strip=True)

        tasks.append(scrape_article(client, article_url, article_name))

    category_articles = await asyncio.gather(*tasks)
    category_articles = [
        article for article in category_articles if article is not None
    ]

    # Extract category ID from URL (e.g. '293' in /category/293-lambdatest-integration)
    category_id = (
        url.split("/")[-1].split("-")[0] if "-" in url.split("/")[-1] else "Unknown"
    )

    return Category(
        category_id=category_id,
        category_title=title,
        category_description=description,
        articles=category_articles,
        total_articles=len(category_articles),
    )


async def scrape_collection(
    client: httpx.AsyncClient, url: str, name: str
) -> Collection | None:
    """
    Scrape a collection page and recursively scrape all categories under it.

    Args:
        client: httpx.AsyncClient instance.
        url: URL of the collection page.
        name: The name of the collection.

    Returns:
        A Collection object containing all categories and their articles,
        or None if the collection page cannot be retrieved.

    Notes:
        - Though async, the categories are scraped sequentially to avoid rate-limiting as there are many categories.
        - We do not use a semaphore for categories because ultimately we need the article content to be scraped concurrently.
        - Concurrent scraping of categories with semaphore is almost redundant as articles already use a semaphore and can only be fetched 2 at a time (and almost all categories have multiple articles).
    """

    collection_soup = await get_soup(client, url)
    if not collection_soup:
        print(f"Failed to retrieve {name} collection url.")
        return None

    # Extract payloads (article + category details) for each category
    # in the collection using category URLs found on the collection page.
    category_links = collection_soup.select("a[href*='/category/']")
    categories: List[Category] = []

    for link in category_links:
        category_url = urljoin(url, link["href"])  # type: ignore
        category_name = link.get_text(strip=True)

        category_payload = await scrape_category(client, category_url, category_name)
        if category_payload:
            categories.append(category_payload)

    # Extract collection ID from URL (e.g. '366' in /collection/366-zipboard-users)
    collection_id = (
        url.split("/")[-1].split("-")[0] if "-" in url.split("/")[-1] else "Unknown"
    )

    return Collection(
        collection_id=collection_id,
        collection_title=name,
        categories=categories,
        total_categories=len(categories),
    )


async def run_scraper() -> List[Collection]:
    """
    Entry point for scraping the entire zipBoard help docs.

    This function:
        - Fetches the base help docs page
        - Discovers all collections
        - Recursively scrapes categories and articles
        - Returns a fully structured representation of the documentation

    Returns:
        A list of Collection objects representing the complete help docs.

    Notes:
        - Since collections are few (3), they are scraped concurrently.
        - The scraper respects rate-limiting by controlling concurrency and adding delays.
    """

    collections: List[Collection] = []
    async with httpx.AsyncClient(follow_redirects=True) as client:
        print("Starting scraper....")
        soup = await get_soup(client, BASE_URL)
        if not soup:
            print("Failed to retrieve the Base URL.")
            return []

        # Extract collection links from the base url page and scrape them concurrently.
        collection_links = soup.select("a[href*='/collection/']")
        tasks = []

        for link in collection_links:
            collection_url = urljoin(BASE_URL, link["href"])  # type: ignore
            collection_name = link.get_text(strip=True)

            tasks.append(scrape_collection(client, collection_url, collection_name))

        payloads = await asyncio.gather(*tasks)
        collections.extend([payload for payload in payloads if payload is not None])

    # Clear seen_url for future runs.
    seen_url.clear()
    return collections
