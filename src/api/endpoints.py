from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from ..analyzer.competitor_analysis import run_competitor_analysis
from ..analyzer.gap_analysis import run_gap_analysis
from ..analyzer.article_analysis import analyze_articles
from ..services.sheet_service import update_competitor_analysis_sheet, update_google_sheets
from ..utils.sheet_utils import flatten_articles_catalogue, flatten_competitor_analysis_insights, flatten_competitor_comparison, flatten_gap_analysis_result
from ..utils.mapping_utils import normalize_analyzed_articles_to_catalogue, normalize_articles_to_gap_analysis_input, normalize_scraped_articles
from ..scraper.scraper import run_scraper
from ..models.api import ApiError, ApiResponse

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("/", response_model=ApiResponse)
async def get_articles(concurrency: int = 2, limit: int = 16):
    try:
        # 1. ------------------Scraping-----------------------
        scraped_data = await run_scraper(concurrency=concurrency, limit=limit)

        # 2. -------------------Article Analysis------------------------------

        # Normalize scraped data and pass for LLM ingestion to generate insights and identify gaps.
        normalized_articles = normalize_scraped_articles(scraped_data)
        article_analysis_result = await analyze_articles(normalized_articles)

        # Normalize analyzed data and initial normalized article data into a structure fit for
        # spreadsheet display.
        articles_catalogue = normalize_analyzed_articles_to_catalogue(analyzed_articles=article_analysis_result, articles=normalized_articles)

        # Flatten normalized data into dicts and update spreadsheet.
        flattened_articles = flatten_articles_catalogue(articles_catalogue)
        await run_in_threadpool(update_google_sheets, flattened_articles, "Articles Catalogue")

        # 3. ---------------------------Gap Analysis---------------------------------

        # Normalize analyzed article data and the finalized article catalogue into LLM-ready
        # input for Gap Analysis.
        gap_analysis_input = normalize_articles_to_gap_analysis_input(analyzed_articles=article_analysis_result, articles=articles_catalogue)
        gap_analysis_result = await run_gap_analysis(gap_analysis_input)

        # Flatten gap analysis results into dict and update spreadsheet.
        flattened_gaps = flatten_gap_analysis_result(gap_analysis_result)
        await run_in_threadpool(update_google_sheets, flattened_gaps, "Gap Analysis")

        # 4. ----------------------------Competitor Analysis-----------------------------

        # Perform competitor analysis. It requires the same context as gap analysis.
        competitor_analysis_result = await run_competitor_analysis(gap_analysis_input)

        # We represent competitor analysis in 2 tables:
        # a. Competitor Comparison
        # b. Insights for zipBoard based on competitor analysis
        # Hence, we extract and flatten both data into separate vars and update sheets.
        flattened_competitor_comparison = flatten_competitor_comparison(competitor_analysis_result)
        flattened_competitor_analysis_insights = flatten_competitor_analysis_insights(competitor_analysis_result)
        await run_in_threadpool(update_competitor_analysis_sheet, flattened_competitor_comparison, flattened_competitor_analysis_insights)

        return ApiResponse(
            success=True,
            status_code=200,
            payload="The articles have been scraped and the Google Sheet has been updated successfully."
        )
    except Exception as e:
        print("Exception Occurred: ", e)
        raise ApiError(status_code=500, payload="Internal Server Error", details=str(e))
