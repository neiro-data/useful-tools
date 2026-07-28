"""Command-line entry point: DDL file/stdin -> .drawio file/stdout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ddl_to_drawio.emitter import build_mxgraph_xml
from ddl_to_drawio.parser import DEFAULT_DIALECT, SUPPORTED_DIALECTS, DdlParseError, parse_ddl


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ddl-to-drawio",
        description="Convert a DDL dump into a draw.io ER diagram.",
    )
    parser.add_argument(
        "input",
        help="Path to the input .sql DDL file, or '-' to read from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Path to the output .drawio file, or '-' for stdout. "
        "Defaults to the input basename with a .drawio extension.",
    )
    parser.add_argument(
        "--schema",
        default=None,
        help="Only include tables belonging to this schema (e.g. 'public').",
    )
    parser.add_argument(
        "--dialect",
        choices=SUPPORTED_DIALECTS,
        default=DEFAULT_DIALECT,
        help=f"SQL dialect to parse the input with. One of: {', '.join(SUPPORTED_DIALECTS)}. "
        f"Defaults to '{DEFAULT_DIALECT}'.",
    )
    return parser


def _read_input(input_path: str) -> str:
    if input_path == "-":
        return sys.stdin.read()
    return Path(input_path).read_text(encoding="utf-8")


def _resolve_output_path(input_path: str, output_arg: str | None) -> str:
    if output_arg is not None:
        return output_arg
    if input_path == "-":
        return "-"
    return str(Path(input_path).with_suffix(".drawio"))


def _write_output(output_path: str, content: str) -> None:
    if output_path == "-":
        sys.stdout.write(content)
        return
    Path(output_path).write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the process exit code."""
    args = _build_arg_parser().parse_args(argv)

    try:
        sql = _read_input(args.input)
    except OSError as exc:
        print(f"error: could not read input '{args.input}': {exc}", file=sys.stderr)
        return 1

    try:
        schema = parse_ddl(sql, schema_filter=args.schema, dialect=args.dialect)
    except DdlParseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not schema.tables:
        print("error: no tables found in input DDL", file=sys.stderr)
        return 1

    xml_content = build_mxgraph_xml(schema)
    output_path = _resolve_output_path(args.input, args.output)

    try:
        _write_output(output_path, xml_content)
    except OSError as exc:
        print(f"error: could not write output '{output_path}': {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
