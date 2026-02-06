from typing import List, Literal, Optional
from pydantic import BaseModel


# Represents a block of content (NOT total content) of a scraped article
# in a structured format.
class ArticleContent(BaseModel):
    type: Literal["heading", "callout", "paragraph", "video", "image", "table", "list"]
    text: Optional[str] = None  # Text content
    level: Optional[int] = None  # for headings
    id: Optional[str] = None  # HTML id attribute
    variant: Optional[Literal["info", "warn"]] = None  # callout variant
    platform: Optional[Literal["youtube", "loom"]] = None  # video platform
    src: Optional[str] = None  # video or image source URL
    alt: Optional[str] = None  # image alt text
    headers: Optional[List[str]] = None  # for tables
    rows: Optional[List[List[str]]] = None  # for tables
    items: Optional[List[str]] = None  # for lists
    ordered: Optional[bool] = None  # for lists, true if ordered list


# Represents the scraped and processed data of an entire article.
class Article(BaseModel):
    article_id: str
    article_title: str
    url: str
    last_updated: str
    word_count: int
    has_screenshots: bool
    has_videos: bool
    has_tables: bool
    content: List[ArticleContent]


# Represents the scraped and processed data of a Category.
class Category(BaseModel):
    category_id: str
    category_title: str
    total_articles: int
    category_description: Optional[str]
    articles: List[Article]


# Represents the scraped and processed data of a Collection.
class Collection(BaseModel):
    collection_id: str
    collection_title: str
    total_categories: int
    categories: List[Category]
