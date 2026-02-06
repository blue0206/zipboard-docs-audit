from typing import List
from openai.types.responses import ResponseInputParam
from groq.types.chat import ChatCompletionMessageParam
from ..services.llm_service import llm_service
from ..models.llm_schema import GuardrailResult
from ..models.analysis_schema import CompetitorAnalysisOutput, GapAnalysisInput


async def run_competitor_analysis(
    articles: List[GapAnalysisInput],
) -> CompetitorAnalysisOutput:
    """
    This function takes a list of articles (of zipBoard help docs),
    with each containing metadata and analysis results, and performs
    competitor analysis by using web search and related tools to explore
    the competitor docs.

    Args:
        - articles: A list of LLM-ready article inputs for gap analysis.

    Returns:
        The competitor analysis result of the docs.
    """

    SYSTEM_PROMPT = """
    You are a senior Technical Documentation Strategist.

    Your task is to perform a COMPETITOR DOCUMENTATION ANALYSIS
    for the product zipBoard.

    You MUST actively perform external research using:
    - Web search
    - Browser Automation
    - Visiting documentation URLs
    - Reading public help centers, API docs, and onboarding guides

    Tool usage is REQUIRED where necessary to ground findings in reality.
    Do NOT rely solely on prior knowledge.

    ---

    Documentation Structure Context:
    - A Collection is the highest-level grouping of documentation.
    - Each Collection contains multiple Categories.
    - Each Category contains multiple Articles.

    You are evaluating DOCUMENTATION QUALITY, STRUCTURE, COVERAGE, and USEFULNESS.
    You are NOT evaluating product features or marketing claims.

    ---

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

    ---

    Your Objectives:
    1. Analyze competitor documentation portals listed below.
    2. Identify documentation strengths, weaknesses, and patterns.
    3. Compare competitor documentation approaches against zipBoard's current documentation coverage (provided separately).
    4. Derive actionable insights that inform how zipBoard can improve its documentation strategy.

    ---

    Constraints & Rules:
    - Base findings ONLY on publicly available documentation.
    - Do NOT invent undocumented features.
    - Clearly separate observed facts from inferred conclusions.
    - Be concise, structured, and evidence-backed.
    - Focus on documentation quality, not product superiority claims.

    ---

    Expected Output:
    Return a well-structured TEXTUAL analysis containing:
    1. A comparison summary for each competitor's documentation.
    2. Cross-competitor insights highlighting:
    - Documentation gaps for zipBoard
    - Documentation advantages for zipBoard
    - Industry documentation expectations
    - Actionable documentation opportunities

    Your output will be used directly for stakeholder review and spreadsheet reporting.
    """

    USER_PROMPT = f"""
    Competitors to analyze:
    - BugHerd — https://support.bugherd.com/en/ | https://www.bugherd.com/api_v2
    - Userback - https://userback.io/guides/
    - Pastel — https://help.usepastel.com/
    - Marker.io — https://help.marker.io/
    - MarkUp.io - https://educate.ceros.com/en/collections/14629865-markup
    - Filestage — https://help.filestage.io/
    - Ruttl - https://ruttl.com/support/

    zipBoard Documentation Context:
    Below is a structured list of documentation articles with metadata and per-article analysis.
    zipBoard docs: https://help.zipboard.co

    Each item contains:
    - Article metadata (category, collection, target audience, content type)
    - Topics covered
    - Quality score
    - Identified gaps at the article level

    {[f"{article.model_dump_json()}\n" for article in articles]}

    ---

    Perform competitor documentation research and provide:
    - Per-competitor documentation observations
    - Cross-competitor patterns
    - Insights relevant to improving zipBoard's documentation strategy
    """

    # Generate LLM response. The data returned is simple text.
    input: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]
    text_response = await llm_service.get_llm_response_with_research(input)
    # We run the response against a refiner model to return structured output.
    return await refine_competitor_analysis_research(text_response)


async def refine_competitor_analysis_research(
    response_text: str,
) -> CompetitorAnalysisOutput:
    """
    This function takes the textual competitor analysis results from the research model
    and refines it into a structured format using another LLM.

    Args:
        - response_text: The generated competitor analysis which needs to be evaluated.

    Returns:
        The refined competitor analysis in structured format with confidence scores.
    """

    SYSTEM_PROMPT = """
    You are a Documentation Analysis Refiner.

    Your task is to transform a free-form competitor documentation analysis
    into a STRICTLY STRUCTURED output.

    You are NOT allowed to introduce new information.
    You must ONLY use what exists in the input text.

    ---
    Product Context:
    zipBoard is a visual feedback and task management platform used to review
    and collaborate on digital content such as websites, PDFs, images, videos,
    and eLearning materials.

    The analysis under review evaluates documentation quality and coverage,
    not product feature superiority.

    ---

    Your Responsibilities:
    1. Extract competitor documentation comparisons.
    2. Extract actionable insights for zipBoard.
    3. Normalize findings into the required schema.
    4. Assign a CONFIDENCE SCORE to EACH competitor comparison and insight based on clarity, evidence, and specificity.

    ---

    Confidence Score Guidelines (0.0 - 1.0):
    - 0.9 - 1.0: Strong evidence, explicit documentation references
    - 0.7 - 0.89: Well-reasoned, minor assumptions
    - 0.5 - 0.69: Partial evidence, some generalization
    - < 0.5: Weak, vague, or poorly supported

    ---

    Rules:
    - Do NOT invent competitors or features.
    - Do NOT infer beyond the provided text.
    - Remove vague or redundant statements.
    - Ensure schema compliance.
    - Be concise and factual.

    Return output strictly in the required structured format.
    """

    USER_PROMPT = f"""
    The following text is a competitor documentation analysis
    generated by a research model.

    Your task is to:
    - Extract structured competitor comparisons
    - Extract documentation insights for zipBoard
    - Assign a confidence score to EACH entry

    Do NOT add new facts.
    Do NOT perform new research.

    ---

    ANALYSIS TEXT:
    {response_text}
    """

    # Refine the textual response into structured data.
    input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
    response = await llm_service.get_llm_response(
        system_prompt=SYSTEM_PROMPT, input=input, mode="refine_competitor_analysis"
    )
    assert isinstance(response, CompetitorAnalysisOutput)

    # We run the LLM response against a guardrail LLM to verify integrity and validate the response.
    # In case the guardrail returns issues, we retry ONCE, and run the guardrail again. In case
    # we encounter issue again, we simply log and return the response.
    guardrail_results = await run_competitor_analysis_guardrail(response)
    if guardrail_results and not guardrail_results.is_valid:
        # Pass initial model response as string to preserve conversational context.
        input.append({"role": "assistant", "content": response.model_dump_json()})

        # Pass the retry prompt and invoke LLM.
        RETRY_PROMPT = f"""
        Issues identified:
        {[f"- {issue}\n" for issue in guardrail_results.issues]}

        Revise the analysis to fix ONLY these issues.
        """
        input.append({"role": "user", "content": RETRY_PROMPT})
        retried_response = await llm_service.get_llm_response(
            system_prompt=SYSTEM_PROMPT, input=input, mode="refine_competitor_analysis"
        )
        assert isinstance(retried_response, CompetitorAnalysisOutput)

        # Run guardrails again, if failed, log and conitnue.
        final_guardrail_results = await run_competitor_analysis_guardrail(
            retried_response, fallback=True
        )
        if final_guardrail_results and not final_guardrail_results.is_valid:
            print(
                f"Final guardrail failed for Competitor Analysis after retry. Issues: {final_guardrail_results.issues}"
            )

        return retried_response
    else:
        return response


async def run_competitor_analysis_guardrail(
    analysis: CompetitorAnalysisOutput, fallback: bool = False
) -> GuardrailResult | None:
    """
    This function runs guardrail checks on the competitor analysis.

    Args:
        - analysis: The generated competitor analysis which needs to be validated.
        - fallback: Whether to use the fallback model for guardrail (default = False).

    Returns:
        The guardrail result containing validity status and identified issues, or None.
    """

    SYSTEM_PROMPT = """
    You are a strict Output Validator for AI-generated documentation analysis.

    Your role is to validate STRUCTURED OUTPUT for:
    - Hallucinations
    - Unsupported claims
    - Schema violations
    - Overly speculative or marketing language

    ---

    Product Context:
    zipBoard is a visual feedback and task management platform used to review
    and collaborate on digital content such as websites, PDFs, images, videos,
    and eLearning materials.

    ---

    VALIDATION RULES
    Flag issues if:
    - Competitor features are mentioned without documentation evidence
    - zipBoard capabilities are misrepresented
    - Claims go beyond documentation analysis into product comparison
    - Output deviates from the required schema
    - Language is vague, generic, or unverifiable

    ---


    Do NOT: 
    - suggest rewrites.
    - add new information.
    - restate correct content.

    Return output strictly in the required structured format.
    """

    USER_PROMPT = f"""
    Validate the following structured competitor documentation analysis
    against the guardrail rules:

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
