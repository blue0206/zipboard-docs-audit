import asyncio
from typing import Literal
from httpx import Headers
from openai import AsyncOpenAI, APIStatusError
from openai.types.responses import ResponseInputParam
from models.llm_schema import GuardrailResult
from ..core.config import env_settings
from ..models.analysis_schema import ArticleAnalysisOutput, CompetitorAnalysisOutput, GapAnalysisOutput

# There are a total of ~387 zipBoard articles. If we scrape and process all
# of them, even one-by-one, we will definitely hit rate limits as we're on
# free tier. Therefore, we use multiple models and rotate between them
# for article analysis. (modulo arithmetic ftw!)
ARTICLE_ANALYSIS_MODELS = [
    "llama-3.3-70b-versatile", 
    "moonshotai/kimi-k2-instruct", 
    "moonshotai/kimi-k2-instruct-0905",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
]
# Gap analysis is done once for entire scraped batch, hence a single model will do.
GAP_ANALYSIS_MODEL = "openai/gpt-oss-120b"
# Groq Compound model can perform browser automation, web search, and visit URLs, hence
# this can be helpful for competitor analysis.
COMPETITOR_ANALYSIS_MODEL = "groq/compound"
# Just to be defensive, we judge the output of competitor analysis by a good model.
JUDGE_MODEL = "openai/gpt-oss-120b"
# Serves as output guardrail for all LLM response. Might hit rate limits,
# but priority is low so acceptable.
SAFEGUARD_MODEL = "openai/gpt-oss-safeguard-20b" 


class LLMService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=env_settings.GROQ_API_KEY,
            base_url=env_settings.GROQ_BASE_URL
        )
        self.model_idx = 0

    def _get_next_article_analysis_model(self) -> str:
        """
        Returns the next model in the rotation for article analysis.
        """

        model = ARTICLE_ANALYSIS_MODELS[self.model_idx]
        self.model_idx = (self.model_idx + 1) % len(ARTICLE_ANALYSIS_MODELS)
        return model
    
    def _get_temperature(self, mode: Literal["article_analysis", "gap_analysis", "judge_gap_analysis", "output_guardrail", "competitor_analysis"]) -> float:
        """
        Returns temperature based on mode. Higher temperature for gap analysis and competitor analysis to encourage moderate creativity, while lower for article analysis and judging to enforce accuracy.
        """

        if mode == "article_analysis":
            return 0.25
        elif mode == "gap_analysis":
            return 0.45
        elif mode == "competitor_analysis":
            return 0.65
        elif mode == "judge_gap_analysis":
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
        mode: Literal["article_analysis", "gap_analysis", "judge_gap_analysis", "output_guardrail", "competitor_analysis"]
    ) -> ArticleAnalysisOutput | GapAnalysisOutput | CompetitorAnalysisOutput | GuardrailResult | None:
        """
        Fetches LLM response based on mode with retry and rate limit handling.

        Args:
            - system_prompt: The system prompt to set context for LLM.
            - user_prompt: The user prompt containing the actual input.
            - mode: The mode of analysis which determines model choice and temperature.
        
        Returns:
            Parsed LLM response as per expected schema or None in case of failure.
        """
        
        retries = 5
        
        for attempt in range(retries):
            # Set model based on mode
            if mode == "gap_analysis":
                model = GAP_ANALYSIS_MODEL
                response_format = GapAnalysisOutput
            elif mode == "article_analysis":
                model = self._get_next_article_analysis_model()
                response_format = ArticleAnalysisOutput
            elif mode == "competitor_analysis":
                model = COMPETITOR_ANALYSIS_MODEL
                response_format = CompetitorAnalysisOutput
            elif mode == "judge_gap_analysis":
                model = JUDGE_MODEL
                response_format = GuardrailResult
            else:
                model = SAFEGUARD_MODEL
                response_format = GuardrailResult

            try:
                print(f"🤖 Req: {model} | Attempt {attempt+1}")

                response = await self.client.responses.parse(
                    model=model,
                    instructions=system_prompt,
                    input=input,
                    text_format=response_format,
                    temperature=self._get_temperature(mode)
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

llm_service = LLMService()
