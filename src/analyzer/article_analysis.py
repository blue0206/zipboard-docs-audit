import asyncio
from typing import List
from openai.types.responses import ResponseInputParam
from ..core.config import env_settings
from ..services.llm_service import llm_service
from ..models.analysis_schema import (
    ArticleAnalysisInput,
    ArticleAnalysisOutput,
    ArticleAnalysisResult,
)
from ..models.llm_schema import GuardrailResult


async def analyze_articles(
    articles: List[ArticleAnalysisInput],
) -> List[ArticleAnalysisResult]:
    """
    This function takes in a list of LLM-ready article inputs, and runs the
    article analysis for each article concurrently with a limit of 4 concurrent requests.
    The article analysis involves invoking the LLM with appropriate prompts and input,
    and also running guardrail checks on the generated analysis to ensure quality and
    integrity of the analysis.

    Args:
        - articles: A list of LLM-ready article inputs for analysis.

    Returns:
        A list of article analysis outputs from LLM.
    """
    # Default value is 2. This has been set using the formula: Floor[(No. of Article Analysis Models)/2]
    # In this case, we have 5 models hence a value of Floor(5/2) = 2 is good.
    # This ensures there are models free while others are working, giving us time to cool off their
    # rate-limit.
    semaphore = asyncio.Semaphore(env_settings.MAX_CONCURRENT_LLM_CALLS)

    results = await asyncio.gather(
        *[run_article_analysis(a, semaphore) for a in articles]
    )
    results = [
        ArticleAnalysisResult(article_id=article.article_id, analysis=result)
        for result, article in zip(results, articles)
        if result is not None
    ]

    return results


async def run_article_analysis(
    article: ArticleAnalysisInput, semaphore: asyncio.Semaphore
) -> ArticleAnalysisOutput | None:
    """
    This function runs the article analysis by invoking LLM with appropriate prompts and input,
    and also runs guardrail checks on the generated analysis to ensure quality and integrity of the analysis.

    Args:
        - article: The LLM-ready article input for analysis.
        - semaphore: The asyncio semaphore to limit concurrency.

    Returns:
        The article analysis output from LLM or None in case of failure.
    """

    SYSTEM_PROMPT = """
    You are a documentation quality analyst evaluating a single help article.

    Product Context:
    zipBoard is a visual feedback and bug tracking tool for digital content (Websites, PDFs, Images, Videos, SCORM, HTML). 
    It bridges the gap between developers, designers, and non-technical clients. It has the following features:

    1. Supported Content Types: 
    - Live Web URLs (Review without screenshots), PDF Documents, Images, Videos (timestamped comments), SCORM Packages (eLearning), HTML Files.
    2. Review Tools: 
    - Annotation & Markup tools (Arrow, Box, Pen).
    - Guest Reviews (Clients can review without creating an account/login).
    - Responsive/Device mode testing.
    3. Project Management: 
    - Kanban Board & Table Views.
    - Task conversion (Comment -> Task).
    - Version Control for files.
    4. Integrations: 
    - Issue Tracking: Jira, Wrike, Azure DevOps.
    - Communication: Slack, Microsoft Teams.
    - CI/CD & Automation: LambdaTest, Zapier, Custom API.
    5. Enterprise/Admin: 
    - SSO (Single Sign-On).
    - Custom Roles & Permissions.
    - Organization Management.

    Your task is to:
    1. Identify the primary topic and supporting topics covered
    2. Classify the content type and target audience
    3. Identify gaps or missing information that would reduce clarity, completeness, or usability (if any)
    4. Assign a quality score from 1 (poor) to 5 (excellent) based on completeness and usefulness

    Rules:
    - Base your analysis ONLY on the provided article content and metadata
    - Do NOT assume undocumented product behavior
    - Do NOT suggest features that do not exist in the article
    - Gaps must be concrete and actionable (not vague)
    - Topics must be short noun phrases (no sentences)
    - Return output strictly in the required structured format
    """

    USER_PROMPT = f"""
    Article Metadata:
    - ID: {article.article_id}
    - Title: {article.article_title}
    - Collection: {article.collection}
    - Category: {article.category}
    - URL: {article.url}
    - Last Updated: {article.last_updated}
    - Word Count: {article.word_count}
    - Screenshots: {"Present" if article.has_screenshots else "Absent"}
    - Has Videos: {"Present" if article.has_videos else "Absent"}
    - Has Tables: {"Present" if article.has_tables else "Absent"}

    Article Content (Markdown):
    {article.content}
    """

    async with semaphore:
        # Generate LLM response and get insights.
        input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
        response = await llm_service.get_llm_response(
            system_prompt=SYSTEM_PROMPT, input=input, mode="article_analysis"
        )

        try:
            assert isinstance(response, ArticleAnalysisOutput)
        except Exception as e:
            # We simply return None instead of raising error.
            print(f"Article Analysis output assertion failed: {str(e)}")
            return None

        # We run the LLM response against a guardrail LLM to verify integrity and validate the response.
        # In case the guardrail returns issues, we retry ONCE, and run the guardrail again. In case
        # we encounter issue again, we simply log and return the response.
        guardrail_results = await run_article_analysis_guardrail(
            article=article, analysis=response
        )
        if guardrail_results and not guardrail_results.is_valid:
            # Pass initial model response as string to preserve conversational context.
            input.append({"role": "assistant", "content": response.model_dump_json()})

            # Pass the retry prompt and invoke LLM.
            RETRY_PROMPT = f"""
            Issues identified:
            {[f"- {issue}\n" for issue in guardrail_results.issues]}

            Revise the analysis to fix ONLY these issues.
            Do not introduce new gaps or topics.
            """
            input.append({"role": "user", "content": RETRY_PROMPT})
            retried_response = await llm_service.get_llm_response(
                system_prompt=SYSTEM_PROMPT, input=input, mode="article_analysis"
            )

            try:
                assert isinstance(retried_response, ArticleAnalysisOutput)
            except Exception as e:
                # We simply return the previous response instead of raising error.
                # Since its structure is correct, this is acceptable as
                # something is better than nothing.
                print(
                    f"Article Analysis output assertion failed, returning previous try response.\nError Details: {str(e)}"
                )
                return response

            # Run guardrails again, if failed, log and conitnue.
            final_guardrail_results = await run_article_analysis_guardrail(
                article=article, analysis=retried_response, fallback=True
            )
            if final_guardrail_results and not final_guardrail_results.is_valid:
                print(
                    f"Final guardrail failed for article {article.article_id} after retry. Issues: {final_guardrail_results.issues}"
                )
            return retried_response
        else:
            return response


async def run_article_analysis_guardrail(
    article: ArticleAnalysisInput,
    analysis: ArticleAnalysisOutput,
    fallback: bool = False,
) -> GuardrailResult | None:
    """
    This function runs guardrail checks on the article analysis to ensure
    integrity and validity of the analysis.

    Args:
        - article: The original article input which forms the context for guardrail checks.
        - analysis: The generated article analysis which needs to be validated.
        - fallback: Whether to use the fallback model for guardrail (default = False).

    Returns:
        The guardrail result containing validity status and identified issues, or None.
    """

    SYSTEM_PROMPT = """
    You are a validation model verifying the quality of an article analysis.

    Your task is to check whether the analysis is:
    1. Grounded strictly in the provided article content
    2. Free from hallucinated product features or assumptions
    3. Specific, concrete, and non-generic
    4. Internally consistent

    You must NOT:
    - Add new insights
    - Rewrite or improve the analysis
    - Infer undocumented behavior

    Evaluate the following:
    - Are identified gaps directly supported by the article content?
    - Are topics covered reasonable abstractions of the article?
    - Is the quality score justified and consistent with the gaps?
    - Are classifications (content type, audience) plausible?

    Return output strictly in the required structured format.
    """

    USER_PROMPT = f"""
    Article Content (Markdown):
    {article.content}

    Generated Analysis:
    {analysis.model_dump_json()}
    """

    input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
    response = await llm_service.get_llm_response(
        system_prompt=SYSTEM_PROMPT,
        input=input,
        mode="output_guardrail",
        fallback=fallback,
    )
    if isinstance(response, GuardrailResult):
        return response
    return None
