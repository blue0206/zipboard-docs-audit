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

class ArticleAnalysisResult(BaseModel):
    article_id: str
    analysis: ArticleAnalysisOutput

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

class GapAnalysisInput(BaseModel):
    article_id: str
    article_title: str
    category: str
    collection: str
    url: str
    primary_topic: str
    content_type: Literal["how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    quality_score: int = Field(ge=1, le=5)
    identified_gaps: List[str]
    topics_covered: List[str]


class GapAnalysisOutput(BaseModel):
    gap_title: str
    gap_description: str
    category: str
    collection: str
    priority: Literal["low", "medium", "high"]
    affected_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    related_topics: List[str]
    evidence: List[str]
    recommendation: str
    rationale: str
    suggested_article_title: str

class GapAnalysisResult(BaseModel):
    gap_id: str
    analysis: GapAnalysisOutput
