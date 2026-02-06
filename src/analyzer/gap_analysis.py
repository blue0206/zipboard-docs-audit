from typing import List
from openai.types.responses import ResponseInputParam
from ..models.analysis_schema import GapAnalysisInput, GapAnalysisOutput, GapAnalysisOutputList, GapAnalysisResult
from ..models.llm_schema import GuardrailResult
from ..services.llm_service import llm_service


async def run_gap_analysis(articles: List[GapAnalysisInput]) -> List[GapAnalysisResult]:
    """
    This function takes a list of articles (of zipBoard help docs), 
    with each containing metadata and analysis results, and performs
    gap analysis to find any missing pieces or issues in the overall docs.

    Args:
        - articles: A list of LLM-ready article inputs for gap analysis.
    
    Returns:
        The gap analysis reuslt of the docs.
    """

    SYSTEM_PROMPT="""
    You are a senior Technical Documentation Auditor.

    Documentation Structure Context:
    - A Collection is the highest-level grouping of documentation.
    - Each Collection contains multiple Categories.
    - Each Category contains multiple Articles.
    - Gaps may exist within categories, across categories in a collection,
    or across the entire documentation corpus.

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

    Documentation Expectations:
    The documentation should effectively support:
    - New users onboarding into visual review and feedback workflows
    - Designers, developers, and non-technical stakeholders collaborating together
    - Managers tracking feedback through tasks and workflows
    - Enterprise admins configuring roles, permissions, and integrations
    - Advanced users working with APIs, automation, and CI/CD integrations

    Your task is to perform a DOCUMENTATION-WIDE GAP ANALYSIS.
    You are NOT reviewing individual articles in isolation.

    A "gap" means:
    - Important topics missing or under-covered
    - Inconsistencies across articles or sections
    - Poor progression across user skill levels
    - Missing onboarding, conceptual grounding, or advanced guidance
    - Documentation that exists but does not sufficiently serve its audience

    Priority Guidelines (IMPORTANT):
    - High priority gaps should represent critical blockers to adoption, usability, or scale.
    - Medium priority gaps should represent noticeable friction or incomplete guidance.
    - Low priority gaps should represent polish, depth, or long-term improvements.

    You must:
    - Base every gap strictly on the provided input data
    - Use metadata, topics covered, content types, quality scores, and micro-gaps
    - Avoid speculation or undocumented features
    - Identify AT LEAST 5 gaps TOTAL
    - Ensure a MIX of priorities (high, medium, low) where realistically applicable

    If fewer than 3 high-priority gaps genuinely exist:
    - Include medium and low priority gaps to reach a minimum of 5
    - Do NOT artificially inflate priority

    Your output must be actionable, specific, and suitable for stakeholder review.
    """

    USER_PROMPT=f"""
    Below is a structured list of documentation articles with metadata and per-article analysis.

    Each item contains:
    - Article metadata (category, collection, target audience, content type)
    - Topics covered
    - Quality score
    - Identified gaps at the article level

    Your task:
    1. Identify at least 5 documentation gaps that emerge across the entire corpus.
    2. Gaps must represent a MIX of:
        - High priority (critical blockers)
        - Medium priority (significant friction or inconsistency)
        - Low priority (depth, clarity, or long-term improvement)
    2. Each gap must be:
        - Clearly described
        - Supported by evidence from multiple articles
        - Relevant at a documentation-wide level (not article-specific)
    3. Assign a priority (low / medium / high) based on user impact.
    4. Clearly state who is affected (beginner / intermediate / advanced / mixed).
    5. Provide a concrete recommendation for addressing each gap.
    6. Suggest a suitable new article title or documentation addition where applicable.

    Rules:
    - Do NOT repeat the same gap using different wording.
    - Do NOT invent missing features or product behavior.
    - Do NOT reference raw article content (only metadata and analysis).
    - Evidence should reference recurring patterns across articles (e.g., repeated omissions, inconsistent coverage), not individual URLs.

    Return the result strictly in the specified output schema.

    ---

    {[f"{article.model_dump_json()}\n" for article in articles]}
    """

    # Generate LLM response and get insights.
    input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
    response = await llm_service.get_llm_response(system_prompt=SYSTEM_PROMPT, input=input, mode="gap_analysis")
    assert isinstance(response, GapAnalysisOutputList)

    # We run the LLM response against a guardrail LLM to verify integrity and validate the response.
    # In case the guardrail returns issues, we retry ONCE, and run the guardrail again. In case
    # we encounter issue again, we simply log and return the response.
    guardrail_results = await run_gap_analysis_guardrail(articles=articles, analysis=response.analysis)
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
        retried_response = await llm_service.get_llm_response(system_prompt=SYSTEM_PROMPT, input=input, mode="gap_analysis")
        assert isinstance(retried_response, GapAnalysisOutputList)

        # Run guardrails again, if failed, log and conitnue.
        final_guardrail_results = await run_gap_analysis_guardrail(articles=articles, analysis=retried_response.analysis)
        if final_guardrail_results and not final_guardrail_results.is_valid:
            print(f"Final guardrail failed for Gap Analysis after retry. Issues: {final_guardrail_results.issues}")

        final_result = generate_gap_ids(retried_response.analysis)
        return final_result
    else:
        final_result = generate_gap_ids(response.analysis)
        return final_result
    
async def run_gap_analysis_guardrail(articles: List[GapAnalysisInput], analysis: List[GapAnalysisOutput]) -> GuardrailResult | None:
    """
    This function runs guardrail checks on the gap analysis to ensure
    integrity and validity of the analysis.

    Args:
        - articles: The original list of articles input which forms the context for guardrail checks.
        - analysis: The generated gap analysis which needs to be validated.
    
    Returns:
        The guardrail result containing validity status and identified issues, or None.
    """

    SYSTEM_PROMPT="""
    You are an output validation and quality assurance system.

    Your role is to evaluate documentation gap analysis results for:
    - Hallucinations
    - Weak or unsupported claims
    - Redundancy between gaps
    - Missing rationale or evidence
    - Overly generic or vague recommendations

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

    USER_PROMPT=f"""
    Input:
        {[f"{article.model_dump_json()}\n" for article in articles]}

    Gap Analysis Results:
        {[f"{result.model_dump_json()}\n" for result in analysis]}
    """

    input: ResponseInputParam = [{"role": "user", "content": USER_PROMPT}]
    response = await llm_service.get_llm_response(system_prompt=SYSTEM_PROMPT, input=input, mode="output_guardrail")
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
        results.append(GapAnalysisResult(
            gap_id=f"GAP-{idx:03d}",
            analysis=gap
        ))
    
    return results
