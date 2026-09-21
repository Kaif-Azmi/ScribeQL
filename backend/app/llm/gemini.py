"""
Minimal Gemini REST helpers for ScribeQL.

Uses the Google Generative Language API (v1beta) with httpx.
Does not introduce a new SDK or change SchemaCatalog / RAG / sqlglot.
"""

from typing import Any, Dict, List

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Matches LLMGenerationResult / docs/api.md Section 3.3
SQL_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "query_plan": {
            "type": "OBJECT",
            "properties": {
                "select": {"type": "ARRAY", "items": {"type": "STRING"}},
                "distinct": {"type": "BOOLEAN"},
                "group_by": {"type": "ARRAY", "items": {"type": "STRING"}},
                "having": {"type": "STRING", "nullable": True},
                "limit": {"type": "INTEGER", "nullable": True},
                "ctes": {"type": "ARRAY", "items": {"type": "STRING"}},
                "assumptions": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        },
        "sql": {"type": "STRING"},
        "assumptions": {"type": "ARRAY", "items": {"type": "STRING"}},
        "explanation": {"type": "STRING"},
    },
    "required": ["sql", "explanation", "assumptions", "query_plan"],
}


def uses_gemini(provider: str, model: str, base_url: str) -> bool:
    provider_l = (provider or "").lower()
    if provider_l in ("gemini", "google", "google-gemini"):
        return True
    if "generativelanguage.googleapis.com" in (base_url or ""):
        return True
    if (model or "").lower().startswith("gemini"):
        return True
    return False


def gemini_headers(api_key: str) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }


def generate_content_url(base_url: str, model: str) -> str:
    root = (base_url or GEMINI_API_BASE).rstrip("/")
    model_id = model.removeprefix("models/")
    return f"{root}/models/{model_id}:generateContent"


def embed_content_url(base_url: str, model: str) -> str:
    root = (base_url or GEMINI_API_BASE).rstrip("/")
    model_id = model.removeprefix("models/")
    return f"{root}/models/{model_id}:batchEmbedContents"


def build_generate_payload(system_prompt: str, user_prompt: str, temperature: float = 0.1) -> Dict[str, Any]:
    return {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
            "responseSchema": SQL_RESPONSE_SCHEMA,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }


def extract_generate_text(data: Dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("Gemini response contained no candidates.")
    parts = (((candidates[0] or {}).get("content") or {}).get("parts")) or []
    texts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
    if not texts:
        raise ValueError("Gemini response contained no text parts.")
    return "\n".join(texts)


def build_embed_payload(
    texts: List[str],
    model: str,
    dimension: int,
    task_type: str,
) -> Dict[str, Any]:
    model_id = model if model.startswith("models/") else f"models/{model}"
    requests = []
    for text in texts:
        requests.append(
            {
                "model": model_id,
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "outputDimensionality": dimension,
            }
        )
    return {"requests": requests}


def extract_embeddings(data: Dict[str, Any]) -> List[List[float]]:
    embeddings = data.get("embeddings") or []
    vectors: List[List[float]] = []
    for item in embeddings:
        values = item.get("values") if isinstance(item, dict) else None
        if not values:
            raise ValueError("Gemini embedding item was missing values.")
        vectors.append([float(v) for v in values])
    return vectors


def l2_normalize(vector: List[float]) -> List[float]:
    norm = sum(v * v for v in vector) ** 0.5
    if not norm:
        return vector
    return [v / norm for v in vector]
