from typing import Dict, List, Literal
from pydantic import BaseModel, Field


# ---------------------------------Article Analysis---------------------------------------------
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
    topics_covered: List[str]
    content_type: Literal[
        "how-to", "conceptual", "faq", "troubleshooting", "mixed", "reference"
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
        "how-to", "conceptual", "faq", "troubleshooting", "mixed", "reference"
    ]
    target_audience: Literal["beginner", "intermediate", "advanced", "mixed"]
    quality_score: int = Field(ge=1, le=5)
    identified_gaps: List[str]
    topics_covered: List[str]


# -------------------------------------------Gap Analysis --------------------------------------
class CorpusSummary(BaseModel):
    total_articles: int = Field(description="Total articles scraped and analyzed.")
    total_collections: int = Field(description="Total collections scraped and analyzed.")
    total_categories: int = Field(description="Total categories scraped and analyzed.")
    documentation_url: str
    articles_per_collection: Dict[str, int]
    articles_per_category: Dict[str, int]
    # Media refers to easy-to-consume content, i.e., Images, Videos, and even Tables
    media_per_collection: Dict[str, int]
    media_per_category: Dict[str, int]


class CoverageMetrics(BaseModel):
    category_topic_coverage: Dict[str, List[str]] = Field(description="List of topics per category.")

class AudienceMetrics(BaseModel):
    audience_distribution: Dict[
        Literal["beginner", "intermediate", "advanced", "mixed"], int
    ] = Field(description="The count of each audience type across all data.")

    audience_by_collection: Dict[str, Dict[Literal["beginner", "intermediate", "advanced", "mixed"], int]] = Field(description="The count of each audience type per collection.")
    audience_by_category: Dict[str, Dict[Literal["beginner", "intermediate", "advanced", "mixed"], int]] = Field(description="The count of each audience type per category.")
    underserved_audiences: List[Literal["beginner", "intermediate", "advanced", "mixed"]] = Field(description="Audience type for which there is little content. Calculated relatively (for example, advanced articles are naturally fewer than beginner.)")
    progression_breaks_detected: bool = Field(description="Categories with beginner and advanced articles but no intermediate articles.")

class ContentTypeMetrics(BaseModel):
    content_type_distribution: Dict[
        Literal["how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"],
        int,
    ] = Field(description="The count of each content type across all articles.")

    content_type_by_collection: Dict[str, Dict[Literal["how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"], int]] = Field(description="The count of each content type per collection.")
    content_type_by_category: Dict[str, Dict[Literal["how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"], int]] = Field(description="The count of each content type per category.")
    missing_content_types_by_category: Dict[str, List[Literal["how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"]]] = Field(description="The content type missing for each category.")

class QualityMetrics(BaseModel):
    average_quality_score: float
    quality_distribution: Dict[int, int] = Field(description="The occurrence count of each quality value.")
    quality_distribution_per_category: Dict[str, Dict[int, int]] = Field(description="The quality frequency distribution per category.")
    average_quality_per_category: Dict[str, float] = Field(description="The average quality score per category.")
    low_quality_categories: List[str] = Field(description="Categories with low average quality value.")

class GapSignals(BaseModel):
    gaps_per_category: Dict[str, int] = Field(description="The number of identified gaps across all articles per category.")

    # Gap Density = Total Gaps in Category / Total Articles in Category
    gap_density_per_category: Dict[str, float]

    # High Gap Density > 0.5, Low Gap Density <= 0.2
    categories_with_high_gap_density: List[str]
    categories_with_low_gap_density: List[str]

    articles_with_gaps: int = Field(description="The number of articles with at least 1 identified gap.")
    total_identified_gaps: int = Field(description="Total identified gaps across all articles.")

    # Total Identified Gaps / Number of articles with gaps
    average_gaps_per_article: float

class StructuralObservations(BaseModel):
    collections_with_no_beginner_content: List[str]
    collections_with_no_advanced_content: List[str]
    categories_with_no_beginner_content: List[str]
    categories_with_no_advanced_content: List[str]
    categories_with_one_or_less_article: List[str]

# This is the finalized schema provided to LLM as context for Gap Analysis.
class GapAnalysisInput(BaseModel):
    corpus_summary: CorpusSummary
    coverage_metrics: CoverageMetrics
    audience_metrics: AudienceMetrics
    content_type_metrics: ContentTypeMetrics
    quality_metrics: QualityMetrics
    gap_signals: GapSignals
    structural_observations: StructuralObservations


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


# This will be passed as response_format property to LLM
# as the client does not accept List[Type] directly.
class GapAnalysisOutputList(BaseModel):
    analysis: List[GapAnalysisOutput]


# The Gap Analysis output returned by LLM is provided a gap_id
# to help uniquely identify the gap analysis data.
# The Gap_ID is generated AFTER LLM response. It simply serves
# as a temporary identifier before the sheets refetch new data.
class GapAnalysisResult(BaseModel):
    gap_id: str
    analysis: GapAnalysisOutput


# -------------------------------------------Competitor Analysis --------------------------------------
# Details about the competitor documentation.
class CompetitorComparison(BaseModel):
    competitor_name: str
    docs_url: str
    docs_strengths: List[str]
    docs_weaknesses: List[str]
    onboarding_coverage: Literal["poor", "fair", "good", "excellent"]
    advanced_feature_coverage: Literal["none", "limited", "moderate", "extensive"]
    docs_structure: Literal["ad-hoc", "moderately-structured", "well-structured"]
    notable_docs_patterns: List[str]
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )


# Insights for zipBoard based on competitor docs analysis.
class CompetitorInsight(BaseModel):
    insight_type: Literal[
        "zipboard_gap", "zipboard_advantage", "industry_expectation", "docs_opportunity"
    ]
    insight_summary: str
    detailed_observation: str
    evidence: str
    impact_level: Literal["low", "medium", "high"]
    recommended_action: str
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )


# The Competitor Analysis output returned by LLM is parsed by this model.
class CompetitorAnalysisOutput(BaseModel):
    competitor_comparisons: List[CompetitorComparison]
    competitor_insights: List[CompetitorInsight]
