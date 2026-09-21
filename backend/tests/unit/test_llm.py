import json
from unittest.mock import patch, MagicMock
import pytest
import httpx

from app.schema.catalog import SchemaCatalog, TableSchema, ColumnSchema
from app.llm.schemas import LLMGenerationResult, LLMQueryPlan
from app.llm.prompt import build_system_prompt, build_user_prompt, PROMPT_VERSION
from app.llm.client import (
    LLMClient,
    LLMProviderError,
    LLMTimeoutError,
    LLMQuotaExceededError,
)
from app.llm.gemini import (
    SQL_RESPONSE_SCHEMA,
    build_generate_payload,
    extract_generate_text,
    l2_normalize,
    uses_gemini,
)


def create_sample_catalog() -> SchemaCatalog:
    catalog = SchemaCatalog(dialect="postgres")
    catalog.tables["customers"] = TableSchema(
        name="customers",
        columns=[
            ColumnSchema(name="id", data_type="INTEGER", is_primary_key=True),
            ColumnSchema(name="name", data_type="VARCHAR(100)"),
        ],
        primary_keys=["id"]
    )
    return catalog


def test_prompt_builder_versioning_and_formatting():
    sys_prompt = build_system_prompt(dialect="postgres")
    assert PROMPT_VERSION in sys_prompt
    assert "POSTGRES" in sys_prompt

    catalog = create_sample_catalog()
    user_prompt = build_user_prompt(
        question="Show top customers",
        schema_catalog=catalog,
        rag_context="Example: SELECT * FROM demo.customers;",
        previous_error="Syntax error near LIMIT"
    )

    assert "USER QUESTION: Show top customers" in user_prompt
    assert "TABLE customers:" in user_prompt
    assert "RETRIEVED EXAMPLES & CONTEXT" in user_prompt
    assert "PREVIOUS FAILED ATTEMPT FEEDBACK" in user_prompt


def test_llm_json_response_parsing():
    client = LLMClient(api_key="test_key")

    raw_json = json.dumps({
        "query_plan": {
            "select": ["c.name"],
            "distinct": False,
            "group_by": [],
            "having": None,
            "limit": 5,
            "ctes": [],
            "assumptions": ["Top 5 customers by sign-up date."]
        },
        "sql": "SELECT name FROM demo.customers LIMIT 5;",
        "assumptions": ["Top 5 customers by sign-up date."],
        "explanation": "Retrieves the first 5 customer names."
    })

    result = client._parse_json_response(raw_json)
    assert isinstance(result, LLMGenerationResult)
    assert result.sql == "SELECT name FROM demo.customers LIMIT 5;"
    assert result.query_plan.limit == 5
    assert result.explanation == "Retrieves the first 5 customer names."

    # Test stripping markdown fences
    fenced_raw = f"```json\n{raw_json}\n```"
    result_fenced = client._parse_json_response(fenced_raw)
    assert result_fenced.sql == "SELECT name FROM demo.customers LIMIT 5;"

    # Test invalid JSON
    with pytest.raises(LLMProviderError):
        client._parse_json_response("invalid json string {{{")


def test_gemini_helpers_structured_payload():
    assert uses_gemini("gemini", "gemini-2.5-flash", "")
    assert SQL_RESPONSE_SCHEMA["required"] == ["sql", "explanation", "assumptions", "query_plan"]
    payload = build_generate_payload("sys", "user")
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert payload["generationConfig"]["responseSchema"] == SQL_RESPONSE_SCHEMA
    text = extract_generate_text({
        "candidates": [{"content": {"parts": [{"text": '{"sql":"SELECT 1"}'}]}}]
    })
    assert text == '{"sql":"SELECT 1"}'
    vec = l2_normalize([3.0, 4.0])
    assert abs(vec[0] - 0.6) < 1e-9
    assert abs(vec[1] - 0.8) < 1e-9


def test_llm_client_mock_fallback():
    client = LLMClient(api_key=None)
    catalog = create_sample_catalog()

    # Async call
    pytest_asyncio_marker = pytest.mark.asyncio
    import asyncio
    result = asyncio.run(client.generate_sql("Show top 5 customers", catalog))

    assert isinstance(result, LLMGenerationResult)
    assert "SELECT" in result.sql
    assert "customers" in result.sql
    assert result.query_plan.limit == 5


@pytest.mark.asyncio
async def test_llm_client_hosted_provider_success():
    client = LLMClient(api_key="valid_api_key", provider="gemini", model="gemini-2.5-flash")
    catalog = create_sample_catalog()

    structured = json.dumps({
        "query_plan": {"select": ["id"], "limit": 10},
        "sql": "SELECT id FROM demo.customers LIMIT 10;",
        "assumptions": [],
        "explanation": "Selects customer IDs."
    })
    mock_response_json = {
        "candidates": [
            {"content": {"parts": [{"text": structured}]}}
        ]
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_json

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await client.generate_sql("Get customer ids", catalog)
        assert result.sql == "SELECT id FROM demo.customers LIMIT 10;"
        assert result.explanation == "Selects customer IDs."


@pytest.mark.asyncio
async def test_llm_client_provider_errors():
    client = LLMClient(api_key="valid_api_key")
    catalog = create_sample_catalog()

    # 1. Quota Exceeded (429)
    mock_429 = MagicMock()
    mock_429.status_code = 429
    with patch("httpx.AsyncClient.post", return_value=mock_429):
        with pytest.raises(LLMQuotaExceededError):
            await client.generate_sql("Question", catalog)

    # 2. Timeout Exception
    with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(LLMTimeoutError):
            await client.generate_sql("Question", catalog)

    # 3. HTTP 500 Provider Error
    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.text = "Internal Server Error"
    with patch("httpx.AsyncClient.post", return_value=mock_500):
        with pytest.raises(LLMProviderError):
            await client.generate_sql("Question", catalog)
