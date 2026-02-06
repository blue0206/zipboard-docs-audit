from typing import Dict, List
from ..models.analysis_schema import ArticlesCatalogue


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
