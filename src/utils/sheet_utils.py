from typing import Dict, List, Literal
from ..models.analysis_schema import (
    ArticlesCatalogue,
    CompetitorAnalysisOutput,
    GapAnalysisResult,
)


def flatten_articles_catalogue(articles: List[ArticlesCatalogue]) -> List[Dict]:
    """
    This function flattens ArticlesCatalogue data into a list of dictionaries
    suitable for spreadsheet representation.
    """

    flattended_data: List[Dict] = []

    for article in articles:
        flattended_data.append(
            {
                "Article ID": article.article_id,
                "Article Title": article.article_title,
                "Collection": article.collection,
                "Category": article.category,
                "URL": f'=HYPERLINK("{article.url}", "Article Link")',
                "Content Type": article.content_type.title(),
                "Topics Covered": "\n".join(
                    f"• {item}" for item in article.topics_covered
                ),
                "Gaps Identified": "\n".join(
                    f"• {item}" for item in article.identified_gaps
                ),
                "Quality Score": article.quality_score,
                "Target Audience": article.target_audience.title(),
                "Last Updated": article.last_updated,
                "Word Count": article.word_count,
                "Has Screenshots": "✅ Yes" if article.has_screenshots else "❌ No",
                "Has Videos": "✅ Yes" if article.has_videos else "❌ No",
                "Has Tables": "✅ Yes" if article.has_tables else "❌ No",
            }
        )

    return flattended_data


def flatten_gap_analysis_result(analysis_data: List[GapAnalysisResult]) -> List[Dict]:
    """
    This function flattens GapAnalysisResult data into a list of dictionaries.
    """

    flattened_data: List[Dict] = []

    for gap in analysis_data:
        flattened_data.append(
            {
                "Gap ID": gap.gap_id,
                "Gap Title": gap.analysis.gap_title,
                "Gap Description": gap.analysis.gap_description,
                "Category": gap.analysis.category,
                "Collection": gap.analysis.collection,
                "Priority": gap.analysis.priority.title(),
                "Affected Audience": gap.analysis.affected_audience.title(),
                "Evidence": "\n".join(f"• {item}" for item in gap.analysis.evidence),
                "Recommendation": gap.analysis.recommendation,
                "Related Topics": "\n".join(
                    f"• {item}" for item in gap.analysis.related_topics
                ),
                "Rationale": gap.analysis.rationale,
                "Suggested Article Title": gap.analysis.suggested_article_title,
            }
        )

    return flattened_data


def flatten_competitor_comparison(
    analysis_data: CompetitorAnalysisOutput,
) -> List[Dict]:
    """
    This function extracts the competitor comparison data from analysis data
    and flattens it into a list of dict.
    """

    flattened_data: List[Dict] = []

    for data in analysis_data.competitor_comparisons:
        flattened_data.append(
            {
                "Competitor Name": data.competitor_name,
                "Docs URL": f'=HYPERLINK("{data.docs_url}", "Docs Link")',
                "Docs Strengths": "\n".join(
                    f"• {item}" for item in data.docs_strengths
                ),
                "Docs Weaknesses": "\n".join(
                    f"• {item}" for item in data.docs_weaknesses
                ),
                "Onboarding Coverage": data.onboarding_coverage.title(),
                "Advanced Feature Coverage": data.advanced_feature_coverage.title(),
                "Docs Structure": data.docs_structure.title(),
                "Notable Documentation Patterns": "\n".join(
                    f"• {item}" for item in data.notable_docs_patterns
                ),
                "Confidence Score": data.confidence_score,
            }
        )

    return flattened_data


def flatten_competitor_analysis_insights(
    analysis_data: CompetitorAnalysisOutput,
) -> List[Dict]:
    """
    This function extracts the competitor analysis insights data from analysis data
    and flattens it into a list of dict.
    """

    flattened_data: List[Dict] = []

    for data in analysis_data.competitor_insights:
        flattened_data.append(
            {
                "Insight Type": format_insight_type(data.insight_type),
                "Insight Summary": data.insight_summary,
                "Detailed Observation": data.detailed_observation,
                "Evidence": data.evidence,
                "Impact Level": data.impact_level.title(),
                "Recommended Action": data.recommended_action,
                "Confidence Score": data.confidence_score,
            }
        )

    return flattened_data


def format_insight_type(
    insight_type: Literal[
        "zipboard_gap", "zipboard_advantage", "industry_expectation", "docs_opportunity"
    ],
) -> str:
    if insight_type == "zipboard_gap":
        return "Gap"
    elif insight_type == "zipboard_advantage":
        return "Advantage"
    elif insight_type == "industry_expectation":
        return "Industry Expectation"
    else:
        return "Opportunity"
