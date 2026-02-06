from typing import List, Literal
from pydantic import BaseModel, Field


# The context provided to LLM for Article Analysis will be mapped to this model.
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


# The Article Analysis output returned by LLM is parsed by this model.
class ArticleAnalysisOutput(BaseModel):
    primary_topic: str
    topics_covered: List[str]
    content_type: Literal[
        "how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"
    ]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    identified_gaps: List[str]
    quality_score: int = Field(ge=1, le=5)


# The Article Analysis output returned by LLM is provided an article_id
# to help uniquely identify the article analysis data and map it to
# the respective article. 
# (The article_id is not generated, instead the actual article_id is simply reused.)
class ArticleAnalysisResult(BaseModel):
    article_id: str
    analysis: ArticleAnalysisOutput


# This model represents the spreadsheet-ready data for Articles Catalogue sheet.
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
    content_type: Literal[
        "how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"
    ]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    quality_score: int = Field(ge=1, le=5)
    identified_gaps: List[str]
    topics_covered: List[str]


# The context provided to LLM for Gap Analysis will be mapped to this model.
class GapAnalysisInput(BaseModel):
    article_id: str
    article_title: str
    category: str
    collection: str
    url: str
    primary_topic: str
    content_type: Literal[
        "how_to", "conceptual", "faq", "troubleshooting", "mixed", "reference"
    ]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    quality_score: int = Field(ge=1, le=5)
    identified_gaps: List[str]
    topics_covered: List[str]


# The Gap Analysis output returned by LLM is parsed by this model.
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


# The Gap Analysis output returned by LLM is provided a gap_id
# to help uniquely identify the gap analysis data.
# The Gap_ID is generated AFTER LLM response. It simply serves
# as a temporary identifier before the sheets refetch new data.
class GapAnalysisResult(BaseModel):
    gap_id: str
    analysis: GapAnalysisOutput


class CompetitorAnalysisOutput(BaseModel):
    pass
