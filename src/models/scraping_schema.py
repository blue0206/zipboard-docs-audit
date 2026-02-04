from typing import List, Literal, Optional
from pydantic import BaseModel


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


class Category(BaseModel):
    category_id: str
    category_title: str
    articles: List[Article]
    total_articles: int
    category_description: Optional[str]


class Collection(BaseModel):
    collection_id: str
    collection_title: str
    categories: List[Category]
    total_categories: int
