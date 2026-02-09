from typing import Dict, List, Literal
from ..core.config import env_settings
from ..models.analysis_schema import (
    ArticleAnalysisInput,
    ArticleAnalysisOutput,
    ArticleAnalysisResult,
    ArticlesCatalogue,
    AudienceMetrics,
    ContentTypeMetrics,
    CorpusSummary,
    CoverageMetrics,
    GapAnalysisInput,
    GapSignals,
    QualityMetrics,
    StructuralObservations,
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


def generate_gap_analysis_input(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> GapAnalysisInput:
    """
    This function uses the articles catalogue metadata to calculate relevant metrics for
    gaps evaluation and returns them into an LLM-ready, non-bloating, structured format.

    Args:
        scraped_data (List[Collection]): The entire scraped data. This will primarily be used to init collections and categories as articles alone might be insufficient (for example, collections/categories with no articles.)
        articles (List[ArticlesCatalogue]): The list of article catalogue.

    Returns:
        GapAnalysisInput: A list of metrics generated from articles metadata in structured format for evaluation.
    """

    # Compute metrics.
    corpus_summary = compute_corpus_summary(scraped_data, articles)
    coverage_metrics = compute_coverage_metrics(scraped_data, articles)
    audience_metrics = compute_audience_metrics(scraped_data, articles)
    content_type_metrics = compute_content_type_metrics(scraped_data, articles)
    quality_metrics = compute_quality_metrics(scraped_data, articles)
    gap_signals = compute_gap_signals(scraped_data, articles)
    structural_observations = compute_structural_observations(scraped_data, articles)

    return GapAnalysisInput(
        corpus_summary=corpus_summary,
        coverage_metrics=coverage_metrics,
        audience_metrics=audience_metrics,
        content_type_metrics=content_type_metrics,
        quality_metrics=quality_metrics,
        gap_signals=gap_signals,
        structural_observations=structural_observations,
    )


def compute_corpus_summary(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> CorpusSummary:
    """
    This function computes corpus summary from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        CorpusSummary: The computed corpus summary as object.
    """

    # Init schema vars to be computed.
    articles_per_collection: Dict[str, int] = {}
    articles_per_category: Dict[str, int] = {}
    media_per_collection: Dict[str, int] = {}
    media_per_category: Dict[str, int] = {}

    # Initialize dicts with collection and category keys and initial values using scraped data.
    for collection in scraped_data:
        articles_per_collection[collection.collection_title] = 0
        media_per_collection[collection.collection_title] = 0

        for category in collection.categories:
            articles_per_category[category.category_title] = 0
            media_per_category[category.category_title] = 0

    # Update values.
    for article in articles:
        articles_per_collection[article.collection] += 1
        articles_per_category[article.category] += 1

        if article.has_screenshots or article.has_videos or article.has_tables:
            media_per_collection[article.collection] += 1
            media_per_category[article.category] += 1

    return CorpusSummary(
        total_articles=len(articles),
        total_collections=len(scraped_data),
        total_categories=len(articles_per_category),
        articles_per_collection=articles_per_collection,
        articles_per_category=articles_per_category,
        documentation_url=env_settings.SCRAPING_BASE_URL,
        media_per_collection=media_per_collection,
        media_per_category=media_per_category,
    )


def compute_coverage_metrics(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> CoverageMetrics:
    """
    This function computes coverage metrics from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        CoverageMetrics: The computed coverage metrics as object.
    """

    # Init schema vars to be computed.
    category_topic_coverage: Dict[str, List[str]] = {}

    # Initialize dict with category keys and initial values using scraped data.
    for collection in scraped_data:
        for category in collection.categories:
            category_topic_coverage[category.category_title] = []

    # Update values.
    for article in articles:
        category_topic_coverage[article.category].extend(article.topics_covered)

    return CoverageMetrics(category_topic_coverage=category_topic_coverage)


def compute_audience_metrics(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> AudienceMetrics:
    """
    This function computes audience metrics from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        AudienceMetrics: The computed audience metrics as object.
    """

    # Init schema vars to be computed.
    audience_distribution: Dict[
        Literal["beginner", "intermediate", "advanced", "mixed"], int
    ] = {"beginner": 0, "intermediate": 0, "advanced": 0, "mixed": 0}
    audience_by_collection: Dict[
        str, Dict[Literal["beginner", "intermediate", "advanced", "mixed"], int]
    ] = {}
    audience_by_category: Dict[
        str, Dict[Literal["beginner", "intermediate", "advanced", "mixed"], int]
    ] = {}
    underserved_audiences: List[
        Literal["beginner", "intermediate", "advanced", "mixed"]
    ] = []
    progression_breaks_detected: bool = False

    # Initialize dicts with collection and category keys and initial values using scraped data.
    for collection in scraped_data:
        audience_by_collection[collection.collection_title] = {
            "beginner": 0,
            "intermediate": 0,
            "advanced": 0,
            "mixed": 0,
        }

        for category in collection.categories:
            audience_by_category[category.category_title] = {
                "beginner": 0,
                "intermediate": 0,
                "advanced": 0,
                "mixed": 0,
            }

    # Update values.
    for article in articles:
        audience_distribution[article.target_audience] += 1

        audience_by_collection[article.collection][article.target_audience] += 1
        audience_by_category[article.category][article.target_audience] += 1

    # Find progression breaks in categories.
    for audience_dist in audience_by_category.values():
        # Note that mixed articles will be treated as beginner, intermediate, and advanced
        # and therefore there is no progression break.
        if audience_dist["mixed"] > 0:
            continue

        if (
            audience_dist["beginner"] > 0
            and audience_dist["advanced"] > 0
            and audience_dist["intermediate"] == 0
        ):
            progression_breaks_detected = True
            break

    # Compute underserved audiences. We use relative thresholds for each audience type.
    # - If beginner+mixed articles audience_distribution < 25% of total,
    #   the beginner audience can safely be considered underserved.
    # - If intermediate+mixed articles audience_distribution < 20% of total,
    #   then intermediate audience is underserved.
    # - If advanced+mixed articles audience_distribution < 10% of total,
    #   the advanced audience can be considered underserved.
    #   We choose as low as 10% because advanced articles are naturally fewer.
    total_articles = len(articles)
    if (audience_distribution["beginner"] + audience_distribution["mixed"]) < (
        0.25 * total_articles
    ):
        underserved_audiences.append("beginner")
    if (audience_distribution["intermediate"] + audience_distribution["mixed"]) < (
        0.20 * total_articles
    ):
        underserved_audiences.append("intermediate")
    if (audience_distribution["advanced"] + audience_distribution["mixed"]) < (
        0.10 * total_articles
    ):
        underserved_audiences.append("advanced")

    return AudienceMetrics(
        audience_distribution=audience_distribution,
        audience_by_collection=audience_by_collection,
        audience_by_category=audience_by_category,
        underserved_audiences=underserved_audiences,
        progression_breaks_detected=progression_breaks_detected,
    )


def compute_content_type_metrics(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> ContentTypeMetrics:
    """
    This function computes Content-Type metrics from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        ContentTypeMetrics: The computed content type metrics as object.
    """

    # Init schema vars to be computed.
    content_type_distribution: Dict[
        Literal["how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"],
        int,
    ] = {
        "how-to": 0,
        "conceptual": 0,
        "faq": 0,
        "reference": 0,
        "troubleshooting": 0,
        "mixed": 0,
    }
    content_type_by_collection: Dict[
        str,
        Dict[
            Literal[
                "how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"
            ],
            int,
        ],
    ] = {}
    content_type_by_category: Dict[
        str,
        Dict[
            Literal[
                "how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"
            ],
            int,
        ],
    ] = {}
    missing_content_types_by_category: Dict[
        str,
        List[
            Literal[
                "how-to", "conceptual", "faq", "reference", "troubleshooting", "mixed"
            ]
        ],
    ] = {}

    # Initialize dicts with collection and category keys and initial values using scraped data.
    for collection in scraped_data:
        content_type_by_collection[collection.collection_title] = {
            "how-to": 0,
            "conceptual": 0,
            "faq": 0,
            "reference": 0,
            "troubleshooting": 0,
            "mixed": 0,
        }

        for category in collection.categories:
            content_type_by_category[category.category_title] = {
                "how-to": 0,
                "conceptual": 0,
                "faq": 0,
                "reference": 0,
                "troubleshooting": 0,
                "mixed": 0,
            }

            missing_content_types_by_category[category.category_title] = []

    # Update values.
    for article in articles:
        content_type_distribution[article.content_type] += 1

        content_type_by_collection[article.collection][article.content_type] += 1
        content_type_by_category[article.category][article.content_type] += 1

    for category_key, category_value in content_type_by_category.items():
        for content_type, count in category_value.items():
            if count == 0:
                missing_content_types_by_category[category_key].append(content_type)

    return ContentTypeMetrics(
        content_type_distribution=content_type_distribution,
        content_type_by_collection=content_type_by_collection,
        content_type_by_category=content_type_by_category,
        missing_content_types_by_category=missing_content_types_by_category,
    )


def compute_quality_metrics(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> QualityMetrics:
    """
    This function computes Quality metrics from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        QualityMetrics: The computed quality metrics as object.
    """

    # Init schema vars to be computed.
    average_quality_score: float = 0
    quality_distribution: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    quality_distribution_per_category: Dict[str, Dict[int, int]] = {}
    average_quality_per_category: Dict[str, float] = {}
    low_quality_categories: List[str] = []

    # Initialize dicts with category keys and initial values using scraped data.
    for collection in scraped_data:
        for category in collection.categories:
            quality_distribution_per_category[category.category_title] = {
                1: 0,
                2: 0,
                3: 0,
                4: 0,
                5: 0,
            }
            average_quality_per_category[category.category_title] = 0

    # Compute quality distribution per category.
    for article in articles:
        quality_distribution_per_category[article.category][article.quality_score] += 1

    # Calculate average quality score globally and for each category
    total_score = 0
    total_count = 0
    for category, quality_distribution in quality_distribution_per_category.items():
        # Average quality = Sum(quality * count) / Sum(count)
        category_score = sum(
            [score * count for score, count in quality_distribution.items()]
        )
        category_count = sum(quality_distribution.values())

        average_quality = category_score / category_count if category_count > 0 else 0
        average_quality_per_category[category] = average_quality

        total_score += category_score
        total_count += category_count

    # Compute global average quality score
    average_quality_score = total_score / total_count if total_count > 0 else 0

    # Find and store low quality categories
    for category, average in average_quality_per_category.items():
        if average < (average_quality_score - 0.5):
            low_quality_categories.append(category)

    return QualityMetrics(
        average_quality_score=average_quality_score,
        average_quality_per_category=average_quality_per_category,
        quality_distribution=quality_distribution,
        quality_distribution_per_category=quality_distribution_per_category,
        low_quality_categories=low_quality_categories,
    )


def compute_gap_signals(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> GapSignals:
    """
    This function computes Gap Signals metric from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        GapSignals: The computed gap signals as object.
    """

    # Init schema vars to be computed and helper vars.
    gaps_per_category: Dict[str, int] = {}
    articles_per_category: Dict[str, int] = {}
    gap_density_per_category: Dict[str, float] = {}
    categories_with_high_gap_density: List[str] = []
    categories_with_low_gap_density: List[str] = []
    articles_with_gaps: int = 0
    total_identified_gaps: int = 0
    average_gaps_per_article: float = 0

    # Initialize dict with category keys and initial values using scraped data.
    for collection in scraped_data:
        for category in collection.categories:
            gaps_per_category[category.category_title] = 0
            gap_density_per_category[category.category_title] = 0
            articles_per_category[category.category_title] = 0

    # Update values.
    for article in articles:
        identified_gaps = len(article.identified_gaps)

        gaps_per_category[article.category] += identified_gaps
        total_identified_gaps += identified_gaps
        articles_per_category[article.category] += 1
        if identified_gaps > 0:
            articles_with_gaps += 1

    # Total Identified Gaps / Number of articles with gaps
    average_gaps_per_article = total_identified_gaps / articles_with_gaps if articles_with_gaps > 0 else 0

    # Compute gap density across categories.
    for category, gaps in gaps_per_category.items():
        gap_density = gaps / articles_per_category[category] if articles_per_category[category] > 0 else 0

        # Gap Density = Total Gaps in Category / Total Articles in Category
        gap_density_per_category[category] = gap_density

        # High Gap Density > 0.5, Low Gap Density <= 0.2
        if gap_density > 0.5:
            categories_with_high_gap_density.append(category)
        elif gap_density <= 0.2:
            categories_with_low_gap_density.append(category)

    return GapSignals(
        articles_with_gaps=articles_with_gaps,
        average_gaps_per_article=average_gaps_per_article,
        categories_with_high_gap_density=categories_with_high_gap_density,
        categories_with_low_gap_density=categories_with_low_gap_density,
        gap_density_per_category=gap_density_per_category,
        gaps_per_category=gaps_per_category,
        total_identified_gaps=total_identified_gaps,
    )


def compute_structural_observations(
    scraped_data: List[Collection], articles: List[ArticlesCatalogue]
) -> StructuralObservations:
    """
    This function computes structural observations from scraped data and articles catalogue.

    Args:
        scraped_data (List[Collection]): The entire scraped data.
        articles (List[ArticlesCatalogue]): The list of articles catalogue.

    Returns:
        StructuralObservations: The computed structural observations as object.
    """

    # Init schema vars to be computed and helper vars.
    collections_with_no_beginner_content: List[str] = []
    collections_with_no_advanced_content: List[str] = []
    categories_with_no_beginner_content: List[str] = []
    categories_with_no_advanced_content: List[str] = []
    categories_with_one_or_less_article: List[str] = []
    content_type_by_collection: Dict[
        str, List[Literal["beginner", "intermediate", "advanced", "mixed"]]
    ] = {}
    content_type_by_category: Dict[
        str, List[Literal["beginner", "intermediate", "advanced", "mixed"]]
    ] = {}

    # Initialize dict with collection and category keys and initial values using scraped data.
    for collection in scraped_data:
        content_type_by_collection[collection.collection_title] = []

        for category in collection.categories:
            content_type_by_category[category.category_title] = []

            # We also simply find which categories have one or less article. Note that we don't
            # rely on scraped data for calculating metrics anywhere else because there is a good chance that
            # not all articles are successfully analyzed during the Article Analysis phase and hence, those
            # unanalyzed articles are bound to be cast off.
            # In this case, it poses no issue, but instead, is a better approach as the scraped data can truly
            # tell us the actual number of articles in categories/collections as scraping has lesser miss rate
            # than LLM analysis.
            if len(category.articles) <= 1:
                categories_with_one_or_less_article.append(category.category_title)

    # Update values.
    for article in articles:
        if (
            article.target_audience
            not in content_type_by_collection[article.collection]
        ):
            content_type_by_collection[article.collection].append(
                article.target_audience
            )
        if article.target_audience not in content_type_by_category[article.category]:
            content_type_by_category[article.category].append(article.target_audience)

    # Find the collections and categories with no beginner/advanced content.
    for collection, audience in content_type_by_collection.items():
        if "beginner" not in audience and "mixed" not in audience:
            collections_with_no_beginner_content.append(collection)
        if "advanced" not in audience and "mixed" not in audience:
            collections_with_no_advanced_content.append(collection)

    for category, audience in content_type_by_category.items():
        if "beginner" not in audience and "mixed" not in audience:
            categories_with_no_beginner_content.append(category)
        if "advanced" not in audience and "mixed" not in audience:
            categories_with_no_advanced_content.append(category)

    return StructuralObservations(
        collections_with_no_beginner_content=collections_with_no_beginner_content,
        collections_with_no_advanced_content=collections_with_no_advanced_content,
        categories_with_no_beginner_content=categories_with_no_beginner_content,
        categories_with_no_advanced_content=categories_with_no_advanced_content,
        categories_with_one_or_less_article=categories_with_one_or_less_article,
    )
