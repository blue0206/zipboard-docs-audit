from typing import List, Literal
from pydantic import BaseModel, Field

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

class ArticleAnalysisOutput(BaseModel):
    primary_topic: str
    topics_covered: List[str]
    content_type: Literal["how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    identified_gaps: List[str]
    quality_score: int = Field(ge=1, le=5)

class ArticlesCatalogue(BaseModel):
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
    content_type: Literal["how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    quality_score: int = Field(ge=1, le=5)
    identified_gaps: List[str]
    topics_covered: List[str]
