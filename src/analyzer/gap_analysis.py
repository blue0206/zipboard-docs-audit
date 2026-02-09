from typing import List
from groq.types.chat import ChatCompletionMessageParam
from openai.types.responses import ResponseInputParam
from ..models.analysis_schema import (
    GapAnalysisInput,
    GapAnalysisOutput,
    GapAnalysisOutputList,
    GapAnalysisResult,
)
from ..models.llm_schema import GuardrailResult
from ..services.llm_service import llm_service


async def run_gap_analysis(analysis_input: GapAnalysisInput) -> List[GapAnalysisResult]:
    """
    This function takes a list of articles (of zipBoard help docs),
    with each containing metadata and analysis results, and performs
    gap analysis to find any missing pieces or issues in the overall docs.

    Args:
        - articles: A list of LLM-ready article inputs for gap analysis.

    Returns:
        The gap analysis reuslt of the docs.
    """

    SYSTEM_PROMPT = """
    You are a senior Technical Documentation Auditor.

    You are performing a DOCUMENTATION-WIDE GAP ANALYSIS for zipBoard.

    ---

    Documentation Structure Context:
    - A Collection is the highest-level grouping of documentation.
    - Each Collection contains multiple Categories.
    - Each Category contains multiple Articles.
    - Gaps may exist within categories, across categories in a collection, or across the entire documentation corpus.

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

    Documentation Expectations:
    The documentation should effectively support:
    - New users onboarding into visual review and feedback workflows
    - Designers, developers, and non-technical stakeholders collaborating together
    - Managers tracking feedback through tasks and workflows
    - Enterprise admins configuring roles, permissions, and integrations
    - Advanced users working with APIs, automation, and CI/CD integrations

    ---

    Your Role:
    You are given a PRE-COMPUTED CORPUS SUMMARY consisting of:
    - Coverage metrics
    - Audience distribution
    - Content type distribution
    - Quality metrics
    - Gap signals
    - Structural observations

    You MUST:
    - Use the provided corpus metrics as high-level signals
    - Validate, expand, and contextualize them through direct documentation research
    - Resolve ambiguities by inspecting the documentation directly

    ---

    Tool Usage (REQUIRED):
    You MUST actively perform research using available tools:
    - browser_automation
    - visit_website
    - web_search
    
    Your research MUST include:
    - Navigating zipBoard documentation categories
    - Inspecting onboarding flows and first-time user guidance
    - Reviewing advanced, API, and integration documentation
    - Observing documentation depth, progression, and structure

    The provided corpus metrics are ORIENTING SIGNALS — not replacements for research.

    ---

    A "gap" means:
    - Important topics missing or under-covered
    - Missing or underrepresented guidance
    - Poor progression across user skill levels
    - Missing onboarding, conceptual grounding, or advanced guidance
    - Documentation that exists but does not sufficiently serve its audience

    ---

    Priority Guidelines (IMPORTANT):
    High:
    - Blocks adoption, onboarding, or scale

    Medium:
    - Causes friction or incomplete understanding

    Low:
    - Depth, polish, or long-term improvement

    ---

    You must:
    - Base every gap strictly on the provided input data
    - Use metadata, topics covered, content types, quality scores, and micro-gaps
    - Avoid speculation or undocumented features
    - Identify as many gaps as genuinely exist, 11+ is good, but at least 5 TOTAL.
    - Ensure at least 4 HIGH priority gaps if they genuinely exist
    - Ensure a MIX of priorities (high, medium, low) where realistically applicable

    If fewer than 4 high-priority gaps genuinely exist:
    - Include medium and low priority gaps
    - Do NOT artificially inflate priority

    You MUST NOT perform gap analysis solely by interpreting metrics without inspecting the documentation.

    Your output must be:
    - Evidence-backed
    - Actionable
    - Suitable for stakeholder review
    """

    USER_PROMPT = f"""
    You are provided with a STRUCTURED CORPUS-LEVEL SNAPSHOT of zipBoard documentation.

    Documentation URL (PRIMARY SOURCE for research): https://help.zipboard.co 
    You are expected to explore this documentation directly using tools.

    ---

    Your task:
    1. Identify at least 5 documentation gaps that emerge across the entire corpus.
    2. Gaps must represent a MIX of:
        - High priority (critical blockers)
        - Medium priority (significant friction or inconsistency)
        - Low priority (depth, clarity, or long-term improvement)
    2. Each gap must:
        - Be documentation-wide (not article-specific)
        - Be supported by multiple signals or patterns
        - Clearly explain *why* it is a gap
    3. Assign:
        - Priority (low / medium / high)
        - Affected audience (beginner / intermediate / advanced / mixed)
    4. Provide:
        - Clear evidence grounded in the metrics
        - An actionable recommendation
        - A suggested article or documentation addition (if applicable)

    Rules:
    - Do NOT invent missing features or product behavior.
    - Do NOT restate metrics verbatim, interpret them.
    - Do NOT repeat the same gap using different wording.
    - Do NOT speculate beyond the data

    ---

    {analysis_input.model_dump_json()}
    """

    # Generate LLM response. The data returned is simple text.
    input: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT},
    ]
    text_response = await llm_service.get_llm_response_with_groq(
        input, mode="gap_analysis"
    )
    # We run the response against a refiner model to return structured output.
    structured_response = await refine_gap_analysis(analysis_input, text_response)
    return generate_gap_ids(structured_response.analysis)


async def refine_gap_analysis(
    analysis_input: GapAnalysisInput, response_text: str
) -> GapAnalysisOutputList:
    """
    This function takes the textual gap analysis results and refines it
    into a structured format using another LLM.

    Args:
        - response_text: The generated gap analysis which needs to be structured.

    Returns:
        The refined gap analysis in structured format.
    """

    SYSTEM_PROMPT = """
    You are a Documentation Analysis Refiner.

    Your role is to TRANSFORM an unstructured documentation gap analysis
    into a strictly structured output that conforms EXACTLY to the provided schema.

    ---

    You MUST:
    - Preserve the meaning, intent, and substance of the input analysis
    - Convert each identified gap into ONE structured gap entry
    - Normalize wording without adding new ideas
    - Assign priority levels realistically (high / medium / low)
    - Ensure at least 5 gaps exist if they are present in the input analysis.

    ---

    If fewer than 4 high-priority gaps genuinely exist:
    - Include medium and low priority gaps
    - Do NOT artificially inflate priority

    ---

    You MUST NOT:
    - Invent new gaps, topics, or product features
    - Introduce assumptions not present in the input
    - Remove valid gaps unless they are exact duplicates
    - Change the scope of analysis
    - Reinterpret, re-derive, or recompute metrics.
    - Fabricate gaps to meet count requirements.

    You may ONLY normalize and structure the gaps already identified.
    ---

    If the input contains:
    - Overlapping gaps: merge them into one coherent gap
    - Excessively high priorities: rebalance priority honestly

    ---

    Priority Guidelines (IMPORTANT):
    - High priority gaps should represent critical blockers to adoption, usability, or scale.
    - Medium priority gaps should represent noticeable friction or incomplete guidance.
    - Low priority gaps should represent polish, depth, or long-term improvements.

    ---
    
    IMPORTANT: Return output strictly in the required structured format.
    """

    USER_PROMPT = f"""
    Below is an UNSTRUCTURED documentation-wide gap analysis
    generated by another model.

    Your task:
    - Convert this analysis into the required structured format
    - Each gap must be:
        - Clear and specific
        - Supported by evidence from multiple articles or categories
        - Documentation-wide (not article-specific)
    - Ensure a minimum of 5 gaps
    - Assign realistic priorities (high / medium / low)
    - Identify affected user levels (beginner / intermediate / advanced / mixed)
    - Provide actionable recommendations
    - Suggest appropriate new article titles where relevant

    IMPORTANT:
    - Do NOT invent new gaps
    - Do NOT add product features
    - Do NOT reference raw article content
    - Do NOT include analysis text outside the schema

    ---

    IMPORTANT: Return output strictly in the required structured format.

    Unstructured Gap Analysis Input:

    {response_text}
    """

    # Refine the textual response into structured data.
    input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
    response = await llm_service.get_llm_response(
        system_prompt=SYSTEM_PROMPT, input=input, mode="refine_gap_analysis"
    )
    assert isinstance(response, GapAnalysisOutputList)

    # We run the LLM response against a guardrail LLM to verify integrity and validate the response.
    # In case the guardrail returns issues, we retry ONCE, and run the guardrail again. In case
    # we encounter issue again, we simply log and return the response.
    guardrail_results = await run_gap_analysis_guardrail(
        analysis_input=analysis_input, analysis_output=response.analysis
    )
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
            system_prompt=SYSTEM_PROMPT, input=input, mode="refine_gap_analysis"
        )

        try:
            assert isinstance(retried_response, GapAnalysisOutputList)
        except Exception as e:
            print(
                f"Gap Analysis output assertion failed, returning previous try response.\nError Details: {str(e)}"
            )
            return response

        # Run guardrails again, if failed, log and conitnue.
        final_guardrail_results = await run_gap_analysis_guardrail(
            analysis_input=analysis_input,
            analysis_output=retried_response.analysis,
            fallback=True,
        )
        if final_guardrail_results and not final_guardrail_results.is_valid:
            print(
                f"Final guardrail failed for Competitor Analysis after retry. Issues: {final_guardrail_results.issues}"
            )

        return retried_response
    else:
        return response


async def run_gap_analysis_guardrail(
    analysis_input: GapAnalysisInput,
    analysis_output: List[GapAnalysisOutput],
    fallback: bool = False,
) -> GuardrailResult | None:
    """
    This function runs guardrail checks on the gap analysis to ensure
    integrity and validity of the analysis.

    Args:
        - articles: The original list of articles input which forms the context for guardrail checks.
        - analysis: The generated gap analysis which needs to be validated.
        - fallback: Whether to use the fallback model for guardrail (default = False).

    Returns:
        The guardrail result containing validity status and identified issues, or None.
    """

    SYSTEM_PROMPT = """
    You are an output validation and quality assurance system.
    
    Your role is to evaluate documentation gap analysis results for:
    - Hallucinations
    - Weak or unsupported claims
    - Redundancy between gaps
    - Missing rationale or evidence
    - Overly generic or vague recommendations

    The input analysis is based on:
    - Pre-computed corpus-level metrics
    - Direct documentation research via tools

    Flag issues if:
    - Evidence contradicts provided metrics
    - Gaps reference signals not present in the input
    - Claims imply article-level inspection

    You must NOT:
    - Add new insights
    - Rewrite or improve the analysis
    - Infer undocumented behavior

    Evaluate the following:
        1. Gaps that are not supported by evidence
        2. Gaps that overlap significantly with others
        3. Claims that are vague, generic, or unverifiable
        4. Missing or weak rationale for priority
        5. Recommendations that are unclear or not actionable

    You must NOT:
    - Add new insights
    - Rewrite or improve the analysis
    - Infer undocumented behavior

    You ONLY identify issues and suggest corrections.

    Return output strictly in the required structured format.
    """

    USER_PROMPT = f"""
    Input:
        {analysis_input.model_dump_json()}

    Gap Analysis Results:
        {[f"{result.model_dump_json()}\n" for result in analysis_output]}
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


def generate_gap_ids(analysis: List[GapAnalysisOutput]) -> List[GapAnalysisResult]:
    """
    This function generates and assigns a Gap ID to each Gap Analysis entry.

    Args:
        - analysis: The generated gap analysis.

    Returns:
        The complete, spreadsheet-ready gap analysis results with ID.
    """

    results: List[GapAnalysisResult] = []

    for idx, gap in enumerate(analysis, start=1):
        results.append(GapAnalysisResult(gap_id=f"GAP-{idx:03d}", analysis=gap))

    return results
