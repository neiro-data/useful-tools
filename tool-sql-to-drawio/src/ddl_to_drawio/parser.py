"""Parse a PostgreSQL DDL dump into the plain dataclass model.

Uses sqlglot to build an AST and walks it directly -- no regex on the main parse path.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from ddl_to_drawio.model import Column, ForeignKey, Schema, Table, TableId

DEFAULT_SCHEMA = "public"


class DdlParseError(Exception):
    """Raised when the DDL cannot be parsed at all."""


@dataclass(slots=True)
class _PendingForeignKey:
    """A not-yet-resolved FK; may reference a table's PK implicitly.

    ``target_columns`` is ``None`` when the DDL's ``REFERENCES parent`` clause
    omitted an explicit column list, meaning "the parent's primary key".
    Resolution is deferred until every ``CREATE TABLE`` has been parsed, since
    the parent's primary key may not yet be known while still walking the AST.
    """

    source_table: TableId
    source_columns: list[str]
    target_table: TableId
    target_columns: list[str] | None
    constraint_label: str


def _identifier_name(identifier: exp.Identifier) -> str:
    """Fold unquoted identifiers to lowercase; keep quoted ones as written."""
    if identifier.args.get("quoted"):
        return str(identifier.this)
    return str(identifier.this).lower()


def _table_id(table: exp.Table) -> TableId:
    name = _identifier_name(table.this)
    db = table.args.get("db")
    schema = _identifier_name(db) if db is not None else DEFAULT_SCHEMA
    return TableId(schema=schema, name=name)


def _column_type_text(column_def: exp.ColumnDef) -> str:
    kind = column_def.args.get("kind")
    if kind is None:
        return ""
    return str(kind.sql(dialect="postgres"))


def _parse_create_table(create: exp.Create) -> Table:
    schema_expr = create.this
    if isinstance(schema_expr, exp.Schema):
        table_expr = schema_expr.this
        entries = schema_expr.expressions
    else:
        table_expr = schema_expr
        entries = []

    table = Table(table_id=_table_id(table_expr))

    table_level_pk_names: set[str] = set()
    table_level_unique_names: set[str] = set()

    for entry in entries:
        if isinstance(entry, exp.PrimaryKey):
            table_level_pk_names |= {_identifier_name(i) for i in entry.expressions}
        elif isinstance(entry, exp.Constraint):
            for sub in entry.expressions:
                if isinstance(sub, exp.PrimaryKeyColumnConstraint):
                    schema_sub = sub.args.get("this")
                    if isinstance(schema_sub, exp.Schema):
                        table_level_pk_names |= {
                            _identifier_name(i) for i in schema_sub.expressions
                        }
                elif isinstance(sub, exp.UniqueColumnConstraint):
                    schema_sub = sub.args.get("this")
                    if isinstance(schema_sub, exp.Schema):
                        table_level_unique_names |= {
                            _identifier_name(i) for i in schema_sub.expressions
                        }

    for entry in entries:
        if not isinstance(entry, exp.ColumnDef):
            continue
        name = _identifier_name(entry.this)
        not_null = False
        is_pk = name in table_level_pk_names
        is_unique = name in table_level_unique_names
        for constraint in entry.constraints:
            kind = constraint.kind
            if isinstance(kind, exp.NotNullColumnConstraint):
                not_null = True
            elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
                is_pk = True
                not_null = True
            elif isinstance(kind, exp.UniqueColumnConstraint):
                is_unique = True
        table.columns.append(
            Column(
                name=name,
                type_text=_column_type_text(entry),
                not_null=not_null,
                is_primary_key=is_pk,
                is_unique=is_unique,
            )
        )

    return table


def _inline_foreign_keys(create: exp.Create, source_table: TableId) -> list[_PendingForeignKey]:
    """Return pending FKs declared inline within a ``CREATE TABLE``.

    Source and target columns are paired positionally, so composite (multi-column)
    foreign keys resolve each source column to its corresponding target column
    rather than collapsing every source column onto the first target column.
    """
    results: list[_PendingForeignKey] = []
    schema_expr = create.this
    entries = schema_expr.expressions if isinstance(schema_expr, exp.Schema) else []

    for entry in entries:
        if isinstance(entry, exp.ColumnDef):
            col_name = _identifier_name(entry.this)
            for constraint in entry.constraints:
                kind = constraint.kind
                if isinstance(kind, exp.Reference):
                    target = _reference_target(kind)
                    if target is not None:
                        target_table, target_columns = target
                        results.append(
                            _PendingForeignKey(
                                source_table=source_table,
                                source_columns=[col_name],
                                target_table=target_table,
                                target_columns=target_columns,
                                constraint_label=f"{source_table}.{col_name}",
                            )
                        )
        elif isinstance(entry, exp.ForeignKey):
            ref = entry.args.get("reference")
            if not isinstance(ref, exp.Reference):
                continue
            target = _reference_target(ref)
            if target is None:
                continue
            target_table, target_columns = target
            source_columns = [_identifier_name(i) for i in entry.expressions]
            results.append(
                _PendingForeignKey(
                    source_table=source_table,
                    source_columns=source_columns,
                    target_table=target_table,
                    target_columns=target_columns,
                    constraint_label=f"{source_table} ({', '.join(source_columns)})",
                )
            )

    return results


def _reference_target(reference: exp.Reference) -> tuple[TableId, list[str] | None] | None:
    """Return (target_table, target_columns) for a REFERENCES clause.

    ``target_columns`` is ``None`` when the clause omits an explicit column
    list (e.g. ``REFERENCES parent``), meaning "the parent's primary key".
    Returns ``None`` only when the target table itself cannot be resolved.
    """
    schema_expr = reference.this
    if isinstance(schema_expr, exp.Schema):
        table_expr = schema_expr.this
        columns = schema_expr.expressions
    elif isinstance(schema_expr, exp.Table):
        table_expr = schema_expr
        columns = []
    else:
        return None
    if not isinstance(table_expr, exp.Table):
        return None
    target_table = _table_id(table_expr)
    if not columns:
        return target_table, None
    target_columns = [_identifier_name(c) for c in columns]
    return target_table, target_columns


def _parse_alter_foreign_keys(alter: exp.Alter) -> list[_PendingForeignKey]:
    source_table = alter.this
    if not isinstance(source_table, exp.Table):
        return []
    source_id = _table_id(source_table)

    results: list[_PendingForeignKey] = []
    for action in alter.args.get("actions", []):
        constraints = action.expressions if isinstance(action, exp.AddConstraint) else []
        for constraint in constraints:
            if not isinstance(constraint, exp.Constraint):
                continue
            constraint_name = _constraint_name(constraint)
            for sub in constraint.expressions:
                if not isinstance(sub, exp.ForeignKey):
                    continue
                ref = sub.args.get("reference")
                if not isinstance(ref, exp.Reference):
                    continue
                target = _reference_target(ref)
                if target is None:
                    continue
                target_table, target_columns = target
                source_columns = [_identifier_name(i) for i in sub.expressions]
                results.append(
                    _PendingForeignKey(
                        source_table=source_id,
                        source_columns=source_columns,
                        target_table=target_table,
                        target_columns=target_columns,
                        constraint_label=constraint_name
                        or f"{source_id} ({', '.join(source_columns)})",
                    )
                )
    return results


def _constraint_name(constraint: exp.Constraint) -> str | None:
    identifier = constraint.args.get("this")
    if isinstance(identifier, exp.Identifier):
        return _identifier_name(identifier)
    return None


def parse_ddl(sql: str, schema_filter: str | None = None) -> Schema:
    """Parse a full PostgreSQL DDL dump into a Schema model.

    Args:
        sql: The raw DDL text.
        schema_filter: If given, only keep tables belonging to this schema.

    Returns:
        The extracted Schema.

    Raises:
        DdlParseError: If sqlglot cannot tokenize/parse the input at all.
    """
    try:
        statements = sqlglot.parse(sql, read="postgres")
    except Exception as exc:  # noqa: BLE001 - re-raise as our own error type
        raise DdlParseError(f"Failed to parse DDL: {exc}") from exc

    schema = Schema()
    pending_fks: list[_PendingForeignKey] = []

    for statement in statements:
        if statement is None:
            continue
        if isinstance(statement, exp.Create) and statement.args.get("kind") == "TABLE":
            table = _parse_create_table(statement)
            if schema_filter and table.table_id.schema != schema_filter:
                continue
            schema.tables[table.table_id] = table
            pending_fks.extend(_inline_foreign_keys(statement, table.table_id))
        elif isinstance(statement, exp.Alter):
            pending_fks.extend(_parse_alter_foreign_keys(statement))
        # Everything else (Set, Create Index, Comment, ...) is intentionally ignored.

    for pending in pending_fks:
        if pending.source_table not in schema.tables:
            print(
                f"warning: skipping FK from unknown source table {pending.source_table}",
                file=sys.stderr,
            )
            continue
        if pending.target_table not in schema.tables:
            print(
                f"warning: skipping FK {pending.constraint_label} -> "
                f"{pending.target_table} (target table not found in dump)",
                file=sys.stderr,
            )
            continue

        target_columns = pending.target_columns
        if target_columns is None:
            target_columns = schema.tables[pending.target_table].primary_key_columns
            if not target_columns:
                print(
                    f"warning: skipping FK {pending.constraint_label} -> "
                    f"{pending.target_table} (no target column list given and "
                    "target table has no primary key)",
                    file=sys.stderr,
                )
                continue

        if len(pending.source_columns) != len(target_columns):
            print(
                f"warning: skipping FK {pending.constraint_label} -> "
                f"{pending.target_table} (source/target column count mismatch: "
                f"{len(pending.source_columns)} vs {len(target_columns)})",
                file=sys.stderr,
            )
            continue

        for source_column, target_column in zip(
            pending.source_columns, target_columns, strict=True
        ):
            schema.foreign_keys.append(
                ForeignKey(
                    source_table=pending.source_table,
                    source_column=source_column,
                    target_table=pending.target_table,
                    target_column=target_column,
                )
            )

    return schema
