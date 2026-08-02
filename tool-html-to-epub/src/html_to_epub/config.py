"""CLI/build configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuildConfig:
    """Resolved settings for a single build/inspect run."""

    input_path: str
    output_path: str | None
    metadata_path: str | None
    title: str | None
    author: str | None
    language: str | None
    identifier: str | None
    split_level: int = 1

    def __post_init__(self) -> None:
        if self.split_level not in (1, 2):
            raise ValueError("split_level must be 1 or 2")
