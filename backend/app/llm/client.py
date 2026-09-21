"""
LLM Provider Client for ScribeQL.
Default provider is Gemini (native Generative Language API) with structured JSON output.
Falls back to an OpenAI-compatible chat/completions path when LLM_PROVIDER is not Gemini.
Mock generation is used when no API key is configured.
"""

import json
import logging
import asyncio
from typing import Optional
import httpx

from app.config.settings import settings
from app.schema.catalog import SchemaCatalog
from app.llm.schemas import LLMGenerationResult, LLMQueryPlan
from app.llm.prompt import build_system_prompt, build_user_prompt
from app.llm.gemini import (
    build_generate_payload,
    extract_generate_text,
    gemini_headers,
    generate_content_url,
    uses_gemini,
)

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when the LLM provider fails, times out, or returns invalid outputs."""
    pass


class LLMTimeoutError(LLMProviderError):
    """Raised when the LLM call times out."""
    pass


class LLMQuotaExceededError(LLMProviderError):
    """Raised when the LLM daily budget is spent."""
    pass


def _safe_http_error(status_code: int, body: str) -> str:
    snippet = (body or "").replace("\n", " ")[:180]
    return f"LLM API returned HTTP {status_code}: {snippet}"


class LLMClient:
    def __init__(
        self,
        api_key: Optional[str] = ...,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        provider: Optional[str] = None,
    ):
        if api_key is ...:
            self.api_key = settings.llm_api_key
        else:
            self.api_key = api_key or ""
        self.model = model or settings.llm_model or "gemini-3.6-flash"
        self.base_url = base_url or settings.llm_base_url or "https://generativelanguage.googleapis.com/v1beta"
        self.timeout = timeout or settings.llm_timeout_seconds or 60.0
        self.provider = provider or settings.llm_provider or "gemini"

    def _gemini_enabled(self) -> bool:
        return uses_gemini(self.provider, self.model, self.base_url)

    async def generate_sql(
        self,
        question: str,
        schema_catalog: SchemaCatalog,
        rag_context: Optional[str] = None,
        previous_error: Optional[str] = None
    ) -> LLMGenerationResult:
        """
        Generate structured SQL from a natural language question and SchemaCatalog.
        """
        system_prompt = build_system_prompt(schema_catalog.dialect)
        user_prompt = build_user_prompt(question, schema_catalog, rag_context, previous_error)

        if not self.api_key or self.api_key.strip() in ("", "dummy", "placeholder"):
            return self._generate_mock_result(question, schema_catalog)

        try:
            if self._gemini_enabled():
                return await self._generate_sql_gemini(system_prompt, user_prompt)
            return await self._generate_sql_openai_compatible(system_prompt, user_prompt)
        except (LLMProviderError, LLMTimeoutError, LLMQuotaExceededError):
            raise
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("LLM provider request timed out.") from exc
        except httpx.HTTPError as exc:
            raise LLMProviderError("Network error communicating with LLM provider.") from exc

    async def _generate_sql_gemini(self, system_prompt: str, user_prompt: str) -> LLMGenerationResult:
        url = generate_content_url(self.base_url, self.model)
        payload = build_generate_payload(system_prompt, user_prompt)
        last_error: Optional[Exception] = None
        for attempt in range(4):
            async with httpx.AsyncClient(timeout=self.timeout) as http_client:
                try:
                    response = await http_client.post(
                        url,
                        headers=gemini_headers(self.api_key),
                        json=payload,
                    )
                except httpx.TimeoutException as exc:
                    last_error = exc
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
            if response.status_code in (429, 503) and attempt < 3:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code == 429:
                raise LLMQuotaExceededError("LLM provider quota or rate limit exceeded.")
            if response.status_code != 200:
                raise LLMProviderError(_safe_http_error(response.status_code, response.text))
            try:
                content = extract_generate_text(response.json())
            except Exception as exc:
                raise LLMProviderError("Failed to read Gemini generation response.") from exc
            return self._parse_json_response(content)
        if isinstance(last_error, httpx.TimeoutException):
            raise LLMTimeoutError("LLM provider request timed out.") from last_error
        raise LLMProviderError("LLM provider was unavailable after retries.")

    async def _generate_sql_openai_compatible(self, system_prompt: str, user_prompt: str) -> LLMGenerationResult:
        async with httpx.AsyncClient(timeout=self.timeout) as http_client:
            response = await http_client.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
            )
        if response.status_code == 429:
            raise LLMQuotaExceededError("LLM provider quota or rate limit exceeded.")
        if response.status_code != 200:
            raise LLMProviderError(_safe_http_error(response.status_code, response.text))
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return self._parse_json_response(content)

    def _parse_json_response(self, raw_json_text: str) -> LLMGenerationResult:
        """Parse raw JSON string into LLMGenerationResult."""
        try:
            clean_text = raw_json_text.strip()
            if clean_text.startswith("```"):
                clean_text = clean_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            parsed = json.loads(clean_text)
            sql = parsed.get("sql", "").strip()
            explanation = parsed.get("explanation", "Generated query based on schema.")
            assumptions = parsed.get("assumptions", [])

            plan_dict = parsed.get("query_plan", {})
            query_plan = LLMQueryPlan.model_validate(plan_dict) if isinstance(plan_dict, dict) else LLMQueryPlan()

            return LLMGenerationResult(
                query_plan=query_plan,
                sql=sql,
                assumptions=[str(a) for a in assumptions],
                explanation=explanation,
                raw_response=raw_json_text
            )
        except Exception as exc:
            raise LLMProviderError("Failed to parse structured JSON output from LLM.") from exc

    def _generate_mock_result(self, question: str, schema_catalog: SchemaCatalog) -> LLMGenerationResult:
        tables = list(schema_catalog.tables.keys())
        first_table = tables[0] if tables else "orders"
        table_obj = schema_catalog.get_table(first_table)
        col_names = [c.name for c in table_obj.columns] if table_obj else ["id"]

        q_lower = question.lower()
        dialect = schema_catalog.dialect.lower()
        prefix = "demo." if "categories" in tables or "customers" in tables else ""

        if "top" in q_lower or "limit" in q_lower or "highest" in q_lower:
            limit_val = 5
        else:
            limit_val = 10

        selected_cols = ", ".join(col_names[:min(4, len(col_names))])
        sql = f"SELECT {selected_cols} FROM {prefix}{first_table} LIMIT {limit_val}"

        query_plan = LLMQueryPlan(
            select=col_names[:4],
            distinct=False,
            group_by=[],
            having=None,
            limit=limit_val,
            ctes=[],
            assumptions=["Generated based on schema catalog."]
        )

        return LLMGenerationResult(
            query_plan=query_plan,
            sql=sql,
            assumptions=["Generated default read-only query based on SchemaCatalog."],
            explanation=f"Retrieves up to {limit_val} rows from table '{first_table}' in {dialect.upper()} dialect.",
            raw_response=json.dumps({"sql": sql})
        )


llm_client = LLMClient()
