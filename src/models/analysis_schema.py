from pydantic import BaseModel

class ArticleAnalysisInput(BaseModel):
    article_id: str
    article_title: str
    category: str
    collection: str
    url: str
    last_updated: str
    word_count: int
    has_screenshots: bool
    has_videos: bool
    has_tables: bool
    content: str

