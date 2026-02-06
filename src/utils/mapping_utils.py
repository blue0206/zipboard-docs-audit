from typing import Dict, List
from ..models.analysis_schema import (
    ArticleAnalysisInput,
    ArticleAnalysisOutput,
    ArticleAnalysisResult,
    ArticlesCatalogue,
    GapAnalysisInput,
)
from ..models.scraping_schema import Article, Collection


def normalize_scraped_articles(
    collections: List[Collection],
) -> List[ArticleAnalysisInput]:
    """
    This function normalizes the scraped articles into LLM-ready context by:
        - trimming tree-like heirarchy
        - providing all necessary metadata at (same) article level, and
        - normalizing article content array.

    Args:
        - collections: The entire scraped payload returned by scraper.

    Returns:
        A list of LLM-ready articles with relevant metadata and trimmed context
        to save tokens.
    """
    normalized_articles: List[ArticleAnalysisInput] = []
    for collection in collections:
        for category in collection.categories:
            for article in category.articles:
                normalized_articles.append(
                    ArticleAnalysisInput(
                        article_id=article.article_id,
                        article_title=article.article_title,
                        category=category.category_title,
                        collection=collection.collection_title,
                        url=article.url,
                        has_screenshots=article.has_screenshots,
                        has_videos=article.has_videos,
                        has_tables=article.has_tables,
                        last_updated=article.last_updated,
                        word_count=article.word_count,
                        content=normalize_article_content_to_markdown(article),
                    )
                )

    return normalized_articles


def normalize_article_content_to_markdown(article: Article) -> str:
    """
    This function trims article content from multiple empty-ish blocks to
    markdown string to save tokens. To prevent content from being too long,
    the final markdown content is limited to 11,000 characters.

    Args:
        - article: The article payload which forms a part of scraped data.

    Returns:
        A markdown string representing entire article content, trimmed in case
        exceeding limit.
    """

    md_lines: List[str] = []

    md_lines.append(f"Title: {article.article_title}")
    md_lines.append(f"URL: {article.url}")
    md_lines.append("---- Content ----")

    for block in article.content:
        text = block.text if block.text else ""

        # Handle headings.
        if block.type == "heading":
            prefix = "#" * (block.level or 1)
            md_lines.append(f"{prefix} {text}")

        # Handle paragraphs.
        elif block.type == "paragraph":
            md_lines.append(text)

        # Handle lists.
        elif block.type == "list":
            if block.items:
                # Use number for ordered lists.
                li_marker = "1." if block.ordered else "-"
                for item in block.items:
                    md_lines.append(f"{li_marker} {item}")

        # Handle images (just alt text).
        elif block.type == "image":
            md_lines.append(f"Image: {block.alt or 'Image'}")

        # Handle videos (just platform).
        elif block.type == "video":
            md_lines.append(f"Video: {block.platform}")

        # Handle callouts.
        elif block.type == "callout":
            # Variant provides context about whether callout is info or warn.
            md_lines.append(f"Callout ({block.variant}): ")
            md_lines.append(f"> {text}")

        # Handle tables.
        elif block.type == "table":
            if block.headers:
                md_lines.append(f"| {'|'.join(block.headers)} |")
            if block.rows:
                for row in block.rows:
                    md_lines.append(f"| {'|'.join(row)} |")

    markdown_content = "\n".join(md_lines)
    return markdown_content[:11000]


def normalize_analyzed_articles_to_catalogue(
    analyzed_articles: List[ArticleAnalysisResult], articles: List[ArticleAnalysisInput]
) -> List[ArticlesCatalogue]:
    """
    This function combines the original article metadata with the analysis output
    from LLM to create a catalogue of articles with insights for spreadsheet display.

    Args:
        - analyzed_articles: The list of analyzed articles returned by LLM after analysis.
        - articles: The original list of LLM-ready articles used for analysis.

    Returns:
        A list of articles with combined metadata, analysis and gaps for spreadsheet display.
    """

    analysis_map: Dict[str, ArticleAnalysisOutput] = {
        result.article_id: result.analysis for result in analyzed_articles
    }

    catalogue: List[ArticlesCatalogue] = []

    for article in articles:
        analysis = analysis_map.get(article.article_id)

        if not analysis:
            continue

        catalogue.append(
            ArticlesCatalogue(
                article_id=article.article_id,
                article_title=article.article_title,
                category=article.category,
                collection=article.collection,
                has_screenshots=article.has_screenshots,
                has_videos=article.has_videos,
                has_tables=article.has_tables,
                last_updated=article.last_updated,
                url=article.url,
                word_count=article.word_count,
                content_type=analysis.content_type,
                topics_covered=analysis.topics_covered,
                quality_score=analysis.quality_score,
                target_audience=analysis.target_audience,
                identified_gaps=analysis.identified_gaps,
            )
        )

    return catalogue


def normalize_articles_to_gap_analysis_input(
    analyzed_articles: List[ArticleAnalysisResult], articles: List[ArticlesCatalogue]
) -> List[GapAnalysisInput]:
    """
    This function combines the article catalogue metadata with the analysis output
    from LLM to create structure for LLM ingestion for Gap Analysis.

    Args:
        - analyzed_articles: The list of analyzed articles returned by LLM after article analysis.
        - articles: The list of article catalogue.

    Returns:
        A list of articles with combined metadata, analysis and gaps for LLM ingestion.
    """

    # This is required because the primary_topic field is not present in
    # article catalogue as it is redundant for spreadsheet display but
    # useful for LLM ingestion as it serves as important metadata about
    # what the article is mostly about.
    analysis_map: Dict[str, ArticleAnalysisOutput] = {
        result.article_id: result.analysis for result in analyzed_articles
    }

    gap_analysis_input: List[GapAnalysisInput] = []

    for article in articles:
        analysis = analysis_map.get(article.article_id)

        if not analysis:
            continue

        gap_analysis_input.append(
            GapAnalysisInput(
                article_id=article.article_id,
                article_title=article.article_title,
                category=article.category,
                collection=article.collection,
                content_type=article.content_type,
                identified_gaps=article.identified_gaps,
                primary_topic=analysis.primary_topic,
                quality_score=article.quality_score,
                target_audience=article.target_audience,
                topics_covered=article.topics_covered,
                url=article.url,
            )
        )

    return gap_analysis_input
