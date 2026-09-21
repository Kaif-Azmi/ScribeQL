"""
SchemaCatalog Core Abstraction for ScribeQL.
Authoritative representation of database schemas for both demo and custom modes.
"""

from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    default: Optional[str] = None
    enum_values: List[str] = Field(default_factory=list)
    comment: Optional[str] = None


class ForeignKeySchema(BaseModel):
    column: str
    ref_table: str
    ref_column: str


class TableSchema(BaseModel):
    name: str
    columns: List[ColumnSchema] = Field(default_factory=list)
    primary_keys: List[str] = Field(default_factory=list)
    foreign_keys: List[ForeignKeySchema] = Field(default_factory=list)
    comment: Optional[str] = None

    def get_column(self, col_name: str) -> Optional[ColumnSchema]:
        for col in self.columns:
            if col.name.lower() == col_name.lower():
                return col
        return None


class HintsSchema(BaseModel):
    enums: Dict[str, List[str]] = Field(default_factory=dict)
    metrics: Dict[str, str] = Field(default_factory=dict)
    notes: Optional[str] = None


class SchemaCatalog(BaseModel):
    dialect: str  # "postgres" or "mysql"
    tables: Dict[str, TableSchema] = Field(default_factory=dict)
    hints: HintsSchema = Field(default_factory=HintsSchema)
    warnings: List[str] = Field(default_factory=list)

    def has_table(self, table_name: str) -> bool:
        clean_name = table_name.split(".")[-1].lower() if "." in table_name else table_name.lower()
        return clean_name in {t.lower() for t in self.tables.keys()}

    def get_table(self, table_name: str) -> Optional[TableSchema]:
        clean_name = table_name.split(".")[-1].lower() if "." in table_name else table_name.lower()
        for t_name, table in self.tables.items():
            if t_name.lower() == clean_name:
                return table
        return None

    def table_names(self) -> List[str]:
        return list(self.tables.keys())

    def total_foreign_keys(self) -> int:
        return sum(len(t.foreign_keys) for t in self.tables.values())

    def to_prompt_string(self) -> str:
        """Format the catalog into structured text for LLM generation prompts."""
        lines = [f"=== SCHEMA CATALOG (Dialect: {self.dialect.upper()}) ==="]

        for table_name, table in self.tables.items():
            lines.append(f"\nTABLE {table_name}:")
            for col in table.columns:
                pk_flag = " [PK]" if col.is_primary_key else ""
                null_flag = " NULL" if col.is_nullable else " NOT NULL"
                enum_str = f" ENUM({', '.join(col.enum_values)})" if col.enum_values else ""
                lines.append(f"  - {col.name}: {col.data_type}{null_flag}{pk_flag}{enum_str}")

            if table.foreign_keys:
                lines.append("  FOREIGN KEYS:")
                for fk in table.foreign_keys:
                    lines.append(f"    - {fk.column} -> {fk.ref_table}({fk.ref_column})")

        # Include hints if present
        if self.hints.enums or self.hints.metrics or self.hints.notes:
            lines.append("\n=== USER HINTS ===")
            if self.hints.notes:
                lines.append(f"Notes: {self.hints.notes}")
            if self.hints.enums:
                lines.append("Enums:")
                for col_key, vals in self.hints.enums.items():
                    lines.append(f"  - {col_key}: [{', '.join(vals)}]")
            if self.hints.metrics:
                lines.append("Metrics:")
                for metric_name, expr in self.hints.metrics.items():
                    lines.append(f"  - {metric_name} = {expr}")

        return "\n".join(lines)
