from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.concurrency import run_in_threadpool
from ..core.dependency import authenticate_request
from ..analyzer.competitor_analysis import run_competitor_analysis
from ..analyzer.gap_analysis import run_gap_analysis
from ..analyzer.article_analysis import analyze_articles
from ..services.sheet_service import (
    update_google_sheets,
)
from ..utils.sheet_utils import (
    flatten_articles_catalogue,
    flatten_competitor_analysis_insights,
    flatten_competitor_comparison,
    flatten_gap_analysis_result,
)
from ..utils.mapping_utils import (
    generate_gap_analysis_input,
    normalize_analyzed_articles_to_catalogue,
    normalize_scraped_articles,
)
from ..scraper.scraper import run_scraper
from ..models.api import ApiError, ApiResponse

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get(
    "/", response_model=ApiResponse, dependencies=[Depends(authenticate_request)]
)
async def get_articles(
    background_tasks: BackgroundTasks,
    concurrency: int = 2,
    limit: int = 16,
    gap_analysis: bool = True,
    competitor_analysis: bool = True,
) -> ApiResponse:
    try:
        # The pipeline is run in background to immediately return response to user
        # while processing continues. This prevents request timeouts on long running tasks.
        background_tasks.add_task(
            run_pipeline, concurrency, limit, gap_analysis, competitor_analysis
        )

        return ApiResponse(
            success=True,
            status_code=202,
            payload="The request is being processed successfully.",
        )
    except Exception as e:
        print("Exception Occurred: ", e)
        raise ApiError(status_code=500, payload="Internal Server Error", details=str(e))


async def run_pipeline(
    concurrency: int = 2,
    limit: int = 16,
    gap_analysis: bool = True,
    competitor_analysis: bool = True,
) -> None:
    """
    Runs the complete pipeline for scraping, analyzing, and updating Google Sheets.
    """

    # 1. ------------------Scraping-----------------------
    scraped_data = await run_scraper(concurrency=concurrency, limit=limit)

    # 2. -------------------Article Analysis------------------------------

    # Normalize scraped data and pass for LLM ingestion to generate insights and identify gaps.
    normalized_articles = normalize_scraped_articles(scraped_data)
    article_analysis_result = await analyze_articles(normalized_articles)

    # Normalize analyzed data and initial normalized article data into a structure fit for
    # spreadsheet display.
    articles_catalogue = normalize_analyzed_articles_to_catalogue(
        analyzed_articles=article_analysis_result, articles=normalized_articles
    )

    # Flatten normalized data into dicts and update spreadsheet.
    flattened_articles = flatten_articles_catalogue(articles_catalogue)
    await run_in_threadpool(
        update_google_sheets, flattened_articles, "Articles Catalogue"
    )

    # 3. ---------------------------Gap Analysis---------------------------------

    if gap_analysis:
        # Normalize analyzed article data and the finalized article catalogue into LLM-ready
        # input for Gap Analysis.
        gap_analysis_input = generate_gap_analysis_input(
            scraped_data=scraped_data, articles=articles_catalogue
        )
        gap_analysis_result = await run_gap_analysis(gap_analysis_input)

        # Flatten gap analysis results into dict and update spreadsheet.
        flattened_gaps = flatten_gap_analysis_result(gap_analysis_result)
        await run_in_threadpool(update_google_sheets, flattened_gaps, "Gap Analysis")

    # 4. ----------------------------Competitor Analysis-----------------------------

    if competitor_analysis:
        # Perform competitor analysis. It requires the same context as gap analysis.
        competitor_analysis_result = await run_competitor_analysis()

        # We represent competitor analysis in 2 tables:
        # a. Competitor Comparison
        # b. Insights for zipBoard based on competitor analysis
        # Hence, we extract and flatten both data into separate vars and update sheets.
        flattened_competitor_comparison = flatten_competitor_comparison(
            competitor_analysis_result
        )
        flattened_competitor_analysis_insights = flatten_competitor_analysis_insights(
            competitor_analysis_result
        )
        await run_in_threadpool(
            update_google_sheets,
            flattened_competitor_comparison,
            "Competitor Comparison",
        )
        await run_in_threadpool(
            update_google_sheets,
            flattened_competitor_analysis_insights,
            "Strategic Insights & Recommendations",
        )
