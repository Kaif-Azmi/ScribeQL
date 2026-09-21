"""
Prompt Builder for ScribeQL with prompt versioning.
Formats SchemaCatalog, dialect rules, RAG context, and retry instructions into structured prompts.
"""

from typing import Optional
from app.schema.catalog import SchemaCatalog

PROMPT_VERSION = "v1.0"


SYSTEM_PROMPT_TEMPLATE = """You are ScribeQL's expert Natural-Language-to-SQL generation engine (Prompt Version: {prompt_version}).

Your mission is to generate a precise, safe, read-only SQL query in the requested dialect ({dialect}) based strictly on the provided SchemaCatalog and user question.

STRICT INSTRUCTIONS:
1. DIALECT: Generate valid SQL for dialect: {dialect}.
2. SAFETY & SCOPE: Generate ONLY a single SELECT or set-operation query. NEVER generate INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, EXEC, or locking clauses.
3. SCHEMA REASONING: Refer strictly to table and column names in the provided SchemaCatalog. Do NOT invent non-existent columns or tables.
4. STRUCTURED OUTPUT: Return ONLY a valid JSON object matching the requested schema with the following keys:
   - "query_plan": Object containing "select", "distinct", "group_by", "having", "limit", "ctes", "assumptions".
   - "sql": The exact, clean SQL string.
   - "assumptions": List of plain text interpretations made (e.g., date ranges, ambiguous terms).
   - "explanation": Plain-language explanation of what the query does.

DO NOT wrapped JSON in markdown fences unless instructed. Output pure, parseable JSON.
"""


def build_system_prompt(dialect: str = "postgres") -> str:
    """Build the system prompt for the given SQL dialect."""
    return SYSTEM_PROMPT_TEMPLATE.format(
        prompt_version=PROMPT_VERSION,
        dialect=dialect.upper()
    )


def build_user_prompt(
    question: str,
    schema_catalog: SchemaCatalog,
    rag_context: Optional[str] = None,
    previous_error: Optional[str] = None
) -> str:
    """Build the user prompt combining question, SchemaCatalog, RAG context, and retry feedback."""
    parts = []

    # 1. Question
    parts.append(f"USER QUESTION: {question.strip()}")

    # 2. Schema Catalog
    parts.append(schema_catalog.to_prompt_string())

    # 3. RAG Context (if available)
    if rag_context and rag_context.strip():
        parts.append(f"=== RETRIEVED EXAMPLES & CONTEXT ===\n{rag_context.strip()}")

    # 4. Previous Error Feedback (for retry iterations)
    if previous_error and previous_error.strip():
        parts.append(f"=== PREVIOUS FAILED ATTEMPT FEEDBACK ===\nThe previous SQL attempt failed with error:\n{previous_error.strip()}\n\nPlease fix the SQL query to resolve this error.")

    return "\n\n".join(parts)
