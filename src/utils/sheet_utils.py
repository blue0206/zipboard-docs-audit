from typing import Dict, List
from ..models.analysis_schema import ArticlesCatalogue, GapAnalysisResult


def flatten_articles_catalogue(articles: List[ArticlesCatalogue]) -> List[Dict]:
    """
    This function flattens ArticlesCatalogue data into a list of dictionaries
    suitable for spreadsheet representation.
    """

    flattended_data: List[Dict] = []

    for article in articles:
        flattended_data.append({
            "Article ID": article.article_id,
            "Article Title": article.article_title,
            "Collection": article.collection,
            "Category": article.category,
            "URL": article.url,
            "Content Type": ", ".join(article.content_type),
            "Topics Covered": ", ".join(article.topics_covered),
            "Gaps Identified": ", ".join(article.identified_gaps),
            "Quality Score": article.quality_score,
            "Target Audience": article.target_audience,
            "Last Updated": article.last_updated,
            "Word Count": article.word_count,
            "Has Screenshots": article.has_screenshots,
            "Has Videos": article.has_videos,
            "Has Tables": article.has_tables
        })

    return flattended_data

def flatten_gap_analysis_result(analysis_data: List[GapAnalysisResult]) -> List[Dict]:
    """
    This function flattens GapAnalysisResult data into a list of dictionaries.
    """

    flattened_data: List[Dict] = []

    for gap in analysis_data:
        flattened_data.append({
            "Gap ID": gap.gap_id,
            "Gap Title": gap.analysis.gap_title,
            "Gap Description": gap.analysis.gap_description,
            "Category": gap.analysis.category,
            "Collection": gap.analysis.collection,
            "Priority": gap.analysis.priority,
            "Affected Audience": gap.analysis.affected_audience,
            "Evidence": ", ".join(gap.analysis.evidence),
            "Recommendation": gap.analysis.recommendation,
            "Related Topics": ", ".join(gap.analysis.related_topics),
            "Rationale": gap.analysis.rationale,
            "Suggested Article Title": gap.analysis.suggested_article_title
        })
    
    return flattened_data
