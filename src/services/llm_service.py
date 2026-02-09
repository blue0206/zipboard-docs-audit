import asyncio
from typing import List, Literal
from httpx import Headers
from openai import AsyncOpenAI, APIStatusError
from groq import AsyncGroq, APIStatusError as GroqAPIStatusError
from groq.types.chat import ChatCompletionMessageParam
from openai.types.responses import ResponseInputParam
from ..core.config import env_settings
from ..models.analysis_schema import (
    ArticleAnalysisOutput,
    CompetitorAnalysisOutput,
    GapAnalysisOutputList,
)
from ..models.llm_schema import GuardrailResult

# There are a total of ~387 zipBoard articles. If we scrape and process all
# of them, even one-by-one, we will definitely hit rate limits as we're on
# free tier. Therefore, we use multiple models and rotate between them
# for article analysis.
ARTICLE_ANALYSIS_MODELS = [
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "openai/gpt-oss-20b",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]
# Gap analysis is done once for entire scraped batch, hence a single model will do.
GAP_ANALYSIS_MODEL = "groq/compound-mini"
# Groq Compound model can perform browser automation, web search, and visit URLs, hence
# this can be helpful for competitor analysis.
COMPETITOR_ANALYSIS_RESEARCH_MODEL = "groq/compound"
# Groq Compound model returns unstructured output. This model refines it and
# returns a structured output.
REFINER_MODEL = "openai/gpt-oss-120b"
# Serves as output guardrail for all LLM response. Might hit rate limits,
# but priority is low so acceptable.
SAFEGUARD_MODELS = ["openai/gpt-oss-safeguard-20b", "openai/gpt-oss-20b"]


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=env_settings.GROQ_API_KEY, base_url=env_settings.GROQ_BASE_URL
        )
        self.groq_client = AsyncGroq(
            api_key=env_settings.GROQ_API_KEY,
        )
        self.model_idx = 0

    def _get_next_article_analysis_model(self) -> str:
        """
        Returns the next model in the rotation for article analysis.
        """

        model = ARTICLE_ANALYSIS_MODELS[self.model_idx]
        self.model_idx = (self.model_idx + 1) % len(ARTICLE_ANALYSIS_MODELS)
        return model

    def _get_temperature(
        self,
        mode: Literal[
            "article_analysis",
            "gap_analysis",
            "refine_competitor_analysis",
            "output_guardrail",
            "competitor_analysis",
            "refine_gap_analysis",
        ],
    ) -> float:
        """
        Returns temperature based on mode. Higher temperature for gap analysis and competitor analysis to encourage moderate creativity, while lower for article analysis and judging to enforce accuracy.
        """

        if mode == "article_analysis":
            return 0.25
        elif mode == "gap_analysis":
            return 0.5
        elif mode == "competitor_analysis":
            return 0.65
        elif mode == "refine_competitor_analysis":
            return 0.15
        elif mode == "refine_gap_analysis":
            return 0.15
        else:
            return 0.1

    def _parse_retry_after(self, headers: Headers) -> float:
        """
        Extracts wait time from headers or error message.
        """

        # Wait for time equal to value specified in retry-after header returned by Groq.
        if headers and "retry-after" in headers:
            try:
                return float(headers["retry-after"])
            except Exception:
                pass

        # Default backoff if retry-after header in present.
        return 60.0

    async def get_llm_response(
        self,
        system_prompt: str,
        input: ResponseInputParam,
        mode: Literal[
            "article_analysis",
            "refine_gap_analysis",
            "refine_competitor_analysis",
            "output_guardrail",
        ],
        fallback: bool = False,
    ) -> (
        ArticleAnalysisOutput
        | GapAnalysisOutputList
        | CompetitorAnalysisOutput
        | GuardrailResult
        | None
    ):
        """
        Fetches LLM response based on mode with retry and rate limit handling.

        Args:
            - system_prompt: The system prompt to set context for LLM.
            - input: The input messages for LLM.
            - mode: The mode of analysis which determines model choice and temperature.
            - fallback: Only pass this for guardrail request. (Default = False)

        Returns:
            Parsed LLM response as per expected schema or None in case of failure.
        """

        retries = 5

        for attempt in range(retries):
            # Set model and response_format based on mode
            if mode == "refine_gap_analysis":
                model = REFINER_MODEL
                response_format = GapAnalysisOutputList

            elif mode == "article_analysis":
                model = self._get_next_article_analysis_model()
                response_format = ArticleAnalysisOutput

            elif mode == "refine_competitor_analysis":
                model = REFINER_MODEL
                response_format = CompetitorAnalysisOutput

            else:
                model = SAFEGUARD_MODELS[1] if fallback else SAFEGUARD_MODELS[0]
                response_format = GuardrailResult

            try:
                print(f"🤖 Req: {model} | Attempt {attempt + 1}")

                response = await self.client.responses.parse(
                    model=model,
                    instructions=system_prompt,
                    input=input,
                    text_format=response_format,
                    temperature=self._get_temperature(mode),
                )

                content = response.output_parsed
                if not content:
                    raise ValueError("Empty response")

                return content

            except APIStatusError as e:
                # Handle Rate Limits (429)
                if e.status_code == 429:
                    # Prase retry-after header in response and wait.
                    print(f"Rate limit encountered: {str(e)}")

                    # Check if rate limit is TPD or above and exit early.
                    if e.message.find("TPM") == -1 and e.message.find("RPM") == -1:
                        return None

                    wait_time = self._parse_retry_after(e.response.headers)
                    wait_time += 1.0

                    print(f"Rate Limit ({model}). Sleeping {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue

                # Log other API errors and continue.
                print(f"API Error ({model}): {e}")

            except Exception as e:
                print(f"Exception occurred: {e}")

        return None

    async def get_llm_response_with_groq(
        self,
        input: List[ChatCompletionMessageParam],
        mode: Literal["competitor_analysis", "gap_analysis"],
    ) -> str:
        """
        Fetches LLM response with retry and rate limit handling. Force tool calls, for research.

        Args:
            - input: The input messages for LLM.
            - mode: The mode of analysis which determines model choice and temperature.

        Returns:
            Returns unstructured, text output.
        """
        retries = 5
        model = (
            COMPETITOR_ANALYSIS_RESEARCH_MODEL
            if mode == "competitor_analysis"
            else GAP_ANALYSIS_MODEL
        )

        for attempt in range(retries):
            try:
                print(f"🤖 Req: {model} | Attempt {attempt + 1}")

                response = await self.groq_client.chat.completions.create(
                    model=model,
                    messages=input,
                    temperature=self._get_temperature(mode),
                    compound_custom={
                        "tools": {
                            "enabled_tools": [
                                "browser_automation",
                                "web_search",
                                "visit_website",
                            ]
                        }
                    },
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("Empty response")

                return content

            except GroqAPIStatusError as e:
                # Handle Rate Limits (429)
                if e.status_code == 429:
                    # Prase retry-after header in response and wait.
                    print(f"Rate limit encountered: {str(e)}")

                    # Check if rate limit is TPD or above and exit early.
                    if e.message.find("TPM") == -1 and e.message.find("RPM") == -1:
                        return ""

                    wait_time = self._parse_retry_after(e.response.headers)
                    wait_time += 1.0

                    print(f"Rate Limit ({model}). Sleeping {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                    continue

                # Log other API errors and continue.
                print(f"API Error ({model}): {e}")

            except Exception as e:
                print(f"Exception occurred: {e}")

        return ""


llm_service = LLMService()
