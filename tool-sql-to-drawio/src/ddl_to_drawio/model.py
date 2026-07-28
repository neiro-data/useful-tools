"""Plain dataclass model shared between the parser and the XML emitter.

The emitter must depend only on these dataclasses, never on sqlglot AST types.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class TableId:
    """Fully-qualified table identity: (schema, name), both lowercase-folded."""

    schema: str
    name: str

    def __str__(self) -> str:
        return f"{self.schema}.{self.name}"


@dataclass(slots=True)
class Column:
    """A single table column."""

    name: str
    type_text: str
    not_null: bool = False
    is_primary_key: bool = False
    is_unique: bool = False


@dataclass(slots=True)
class Table:
    """A parsed table with its ordered columns."""

    table_id: TableId
    columns: list[Column] = field(default_factory=list)

    @property
    def primary_key_columns(self) -> list[str]:
        return [c.name for c in self.columns if c.is_primary_key]

    def column(self, name: str) -> Column | None:
        for c in self.columns:
            if c.name == name:
                return c
        return None


@dataclass(slots=True)
class ForeignKey:
    """An edge from a child table/column to a parent table/column."""

    source_table: TableId
    source_column: str
    target_table: TableId
    target_column: str


@dataclass(slots=True)
class Schema:
    """The full extracted model of a DDL dump."""

    tables: dict[TableId, Table] = field(default_factory=dict)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
