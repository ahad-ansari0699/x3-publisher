"""Layout-region detection for rendered document pages."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Region:
    kind: str
    bbox: list[int]
    confidence: float
    line_count: int

    def to_dict(self) -> dict:
        return asdict(self)


def union_box(boxes: list[Box]) -> list[int] | None:
    if not boxes:
        return None
    left = min(box[0] for box in boxes)
    top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes)
    bottom = max(box[1] + box[3] for box in boxes)
    return [int(left), int(top), int(right), int(bottom)]


def longest_ink_run(row: np.ndarray) -> int:
    longest = current = 0
    for value in row:
        if value:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def separator_above_footnotes(
    gray: np.ndarray, footnote_lines: list[Box], width: int
) -> bool:
    if not footnote_lines:
        return False
    first_footnote_y = min(box[1] for box in footnote_lines)
    search_top = max(0, first_footnote_y - int(gray.shape[0] * 0.08))
    ink = gray[search_top:first_footnote_y] < 155
    return any(longest_ink_run(row) >= width * 0.12 for row in ink)


def find_footnote_separator(gray: np.ndarray) -> int | None:
    height, width = gray.shape
    ink = gray < 155
    start = int(height * 0.50)
    stop = int(height * 0.90)
    candidates = [
        y
        for y in range(start, stop)
        if longest_ink_run(ink[y]) >= width * 0.05
    ]
    if not candidates:
        return None

    groups: list[list[int]] = []
    for y in candidates:
        if not groups or y > groups[-1][-1] + 1:
            groups.append([y])
        else:
            groups[-1].append(y)

    thin_rules = [group for group in groups if len(group) <= 4]
    return thin_rules[0][0] if thin_rules else None


def is_two_column_layout(
    lines: list[Box], width: int, height: int
) -> bool:
    content = [
        box
        for box in lines
        if height * 0.10 < box[1] < height * 0.91
    ]
    if len(content) < 18:
        return False
    narrow = [box for box in content if box[2] <= width * 0.40]
    left = [box for box in narrow if box[0] < width * 0.35]
    right = [box for box in narrow if box[0] >= width * 0.48]
    return (
        len(narrow) / len(content) >= 0.72
        and len(left) >= 8
        and len(right) >= 8
    )


def detect_regions(
    gray: np.ndarray,
    lines: list[Box],
    *,
    allow_footnotes: bool = True,
    two_columns: bool = False,
) -> list[Region]:
    """Detect coarse semantic regions using geometry and relative text scale."""
    height, width = gray.shape
    if not lines:
        return []

    header_lines = [box for box in lines if box[1] + box[3] <= height * 0.11]
    footer_lines = [box for box in lines if box[1] >= height * 0.91]
    content_lines = [
        box for box in lines if box not in header_lines and box not in footer_lines
    ]

    if two_columns:
        left_lines = [
            box for box in content_lines if box[0] + box[2] / 2 < width * 0.49
        ]
        right_lines = [
            box for box in content_lines if box[0] + box[2] / 2 >= width * 0.49
        ]
        regions = []
        for kind, boxes, confidence in (
            ("header", header_lines, 0.72),
            ("body_left", left_lines, 0.93),
            ("body_right", right_lines, 0.93),
            ("footer", footer_lines, 0.76),
        ):
            bbox = union_box(boxes)
            if bbox:
                regions.append(
                    Region(kind, bbox, confidence, len(boxes))
                )
        return regions

    main_candidates = [
        box for box in content_lines if height * 0.14 <= box[1] <= height * 0.78
    ]
    bottom_candidates = [box for box in content_lines if box[1] > height * 0.78]
    main_height = (
        float(np.median([box[3] for box in main_candidates]))
        if main_candidates
        else 0.0
    )
    small_bottom_lines = [
        box
        for box in bottom_candidates
        if main_height and box[3] <= max(3.0, main_height * 0.82)
    ]

    footnote_lines: list[Box] = []
    separator_y = find_footnote_separator(gray) if allow_footnotes else None
    if separator_y is not None:
        footnote_lines = [
            box
            for box in content_lines
            if separator_y + 2 < box[1] < height * 0.91
        ]
    elif allow_footnotes and small_bottom_lines:
        first_bottom_y = min(box[1] for box in small_bottom_lines)
        preceding = [box for box in content_lines if box[1] < first_bottom_y]
        previous_bottom = max((box[1] + box[3] for box in preceding), default=0)
        has_gap = first_bottom_y - previous_bottom >= height * 0.012
        has_separator = separator_above_footnotes(gray, small_bottom_lines, width)
        if has_gap or has_separator:
            footnote_lines = small_bottom_lines

    body_lines = [
        box
        for box in content_lines
        if box not in footnote_lines and box not in bottom_candidates
    ]
    body_lines.extend(
        box for box in bottom_candidates if box not in footnote_lines
    )

    regions = []
    for kind, boxes, confidence in (
        ("header", header_lines, 0.72),
        ("body", body_lines, 0.90),
        ("footnote", footnote_lines, 0.84),
        ("footer", footer_lines, 0.76),
    ):
        bbox = union_box(boxes)
        if bbox:
            regions.append(
                Region(
                    kind=kind,
                    bbox=bbox,
                    confidence=confidence,
                    line_count=len(boxes),
                )
            )
    return regions
