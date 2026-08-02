"""Internal data contract. No third-party library types leak past this module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Metadata:
    identifier: str
    title: str
    language: str
    author: str | None
    publisher: str | None
    modified: str


@dataclass(frozen=True)
class Warning:  # noqa: A001 - deliberate shadow of the builtin, scoped to this module
    code: str
    message: str
    page: int | None
    severity: str  # "warning" | "error"


@dataclass(frozen=True)
class Chapter:
    id: str
    title: str
    file_name: str
    body_xhtml: str
    anchors: tuple[str, ...]
    source_pages: tuple[int, ...] = ()
    confidence: float = 1.0


@dataclass(frozen=True)
class TocNode:
    title: str
    href: str
    children: tuple[TocNode, ...]


@dataclass(frozen=True)
class BookModel:
    metadata: Metadata
    chapters: tuple[Chapter, ...]
    toc: tuple[TocNode, ...]
    spine: tuple[str, ...]
    source_pages: tuple[int, ...] = ()
    confidence: float = 1.0
    warnings: tuple[Warning, ...] = ()
