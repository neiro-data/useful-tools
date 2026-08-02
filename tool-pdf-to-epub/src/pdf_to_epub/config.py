"""Build configuration and tunable thresholds for later pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Thresholds:
    """Every tunable numeric knob used by PDF classification and layout analysis."""

    scanned_max_chars: int = 100  # below this char count/page, page is treated as scanned
    scanned_min_image_area: float = 0.5  # min image-covered area fraction to call a page scanned
    digital_min_chars: int = 100  # min char count/page to call a page digital text
    digital_min_text_area: float = 0.05  # min text-covered area fraction for digital pages
    doc_kind_majority: float = 0.8  # fraction of pages needed to classify whole-doc kind
    column_vote_min_words: int = 150  # min words on a page before it votes on column count
    gutter_bin_pt: float = 2.0  # histogram bin width, in points, for gutter detection
    gutter_min_width_frac: float = 0.02  # min gutter width as fraction of page width
    gutter_search_lo: float = 0.15  # lower bound of page-width fraction searched for gutters
    gutter_search_hi: float = 0.85  # upper bound of page-width fraction searched for gutters
    persistence_strips: int = 20  # number of vertical strips used to test gutter persistence
    persistence_min_frac: float = 0.85  # fraction of strips a gutter must persist across
    column_min_word_frac: float = 0.20  # min fraction of words a column must hold to count
    max_gutters: int = 2  # max number of gutters (i.e. max columns - 1) considered per page
    spanning_overlap_frac: float = 0.20  # overlap fraction to call a block column-spanning
    line_y_tolerance_frac: float = 0.4  # y-tolerance (as line-height fraction) for line grouping
    running_head_band_frac: float = 0.08  # top/bottom page-height fraction scanned for headers
    running_head_min_frac: float = 0.60  # min fraction of pages a text must repeat on to qualify
    running_head_min_pages: int = 3  # min page count before running-head detection is attempted
    running_head_y_tolerance_frac: float = 0.01  # y-tolerance (page-height fraction) for matching
    para_indent_frac: float = 0.5  # first-line indent, as line-height fraction, implying new para
    para_gap_frac: float = 1.5  # vertical gap, as line-height fraction, implying new paragraph
    para_short_line_frac: float = 0.8  # line-width fraction below which a line may end a paragraph
    heading_size_ratio: float = 1.15  # font-size ratio over body text implying a heading
    heading_bold_size_ratio: float = 1.05  # font-size ratio for bold text implying a heading
    heading_max_words: int = 12  # max word count for a line to be considered a heading
    heading_max_lines: int = 2  # max line count for a heading block
    outline_min_entries: int = 2  # min PDF outline entries required to trust it as a TOC
    outline_min_resolved_frac: float = 0.70  # min fraction of outline entries that must resolve
    table_min_rows: int = 2  # min row count for a detected grid to be treated as a table
    orphan_word_frac: float = 0.05  # max fraction of words left unassigned before flagging a page

    # confidence.score_page multipliers
    conf_scanned_no_ocr: float = 0.3  # page was scanned and never OCR'd
    conf_ocr_used: float = 0.8  # page went through OCR
    conf_ambiguous_columns: float = 0.7  # layout reported layout.ambiguous_columns
    conf_too_many_gutters: float = 0.6  # more gutter candidates than t.max_gutters survived
    conf_near_empty_page: float = 0.7  # page classified as near-empty
    conf_table_rejected: float = 0.85  # a candidate table on the page was rejected
    near_empty_char_count: int = 20  # char count below which a page counts as near-empty

    # confidence.score_section multiplier
    conf_heading_from_size_heuristic: float = 0.9  # heading came from font-size heuristic
    outline_resolve_page_tolerance: int = 3  # +/- lines tolerance when resolving outline hrefs


@dataclass(frozen=True)
class BuildConfig:
    input_path: Path
    output_path: Path
    ocr: bool = False
    split_level: int = 1
    min_confidence: float = 0.35
    include_tables: bool = True
    metadata_path: Path | None = None
    thresholds: Thresholds = field(default_factory=Thresholds)

    def __post_init__(self) -> None:
        if self.input_path.suffix.lower() != ".pdf":
            raise ValueError(f"input_path must have a .pdf suffix: {self.input_path}")
        if not 1 <= self.split_level <= 3:
            raise ValueError(f"split_level must be in 1..3, got {self.split_level}")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError(f"min_confidence must be in 0.0..1.0, got {self.min_confidence}")
