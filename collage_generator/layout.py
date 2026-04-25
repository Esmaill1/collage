"""Phase 2: Treemap Layout Engine.

Uses the Squarified Treemap algorithm to partition a 5:6 canvas into
rectangular cells, one per image. The treemap guarantees 100% canvas
coverage with zero wasted space.
"""

from __future__ import annotations

import logging
from enum import Enum

import squarify

from .models import Cell, ImageInfo

logger = logging.getLogger(__name__)


class WeightStrategy(str, Enum):
    """Strategy for assigning treemap weights to images."""

    EQUAL = "equal"
    FACES = "faces"
    RESOLUTION = "resolution"


def _compute_weights(
    images: list[ImageInfo],
    strategy: WeightStrategy,
) -> list[float]:
    """Compute treemap weights for each image based on the chosen strategy.

    Args:
        images: List of ImageInfo objects.
        strategy: How to determine relative sizes.

    Returns:
        List of weights (same order as images).
    """
    if strategy == WeightStrategy.EQUAL:
        return [1.0] * len(images)

    elif strategy == WeightStrategy.FACES:
        # Images with faces get more space. Base weight = 1, +1 per face.
        weights = []
        for img in images:
            w = 1.0 + len(img.keep_zones) * 1.5
            weights.append(w)
        return weights

    elif strategy == WeightStrategy.RESOLUTION:
        # Weight by megapixels (normalized so smallest = 1)
        pixels = [img.original_width * img.original_height for img in images]
        min_px = max(min(pixels), 1)
        return [px / min_px for px in pixels]

    else:
        return [1.0] * len(images)


def compute_layout(
    images: list[ImageInfo],
    canvas_width: int,
    canvas_height: int,
    strategy: WeightStrategy = WeightStrategy.EQUAL,
    padding: int = 0,
) -> list[Cell]:
    """Partition the canvas into cells using a squarified treemap.

    Each image is assigned a rectangular cell on the canvas. The algorithm
    produces cells that are as close to square as possible, which minimizes
    the aspect ratio mismatch between images and their cells.

    Args:
        images: List of ImageInfo objects (order matters for layout).
        canvas_width: Output canvas width in pixels.
        canvas_height: Output canvas height in pixels.
        strategy: Weight strategy for relative cell sizing.
        padding: Gap between cells in pixels (applied as inner padding).

    Returns:
        List of Cell objects (same order as images).
    """
    if not images:
        return []

    weights = _compute_weights(images, strategy)

    # squarify requires values sorted descending for optimal layout.
    # We sort by weight and track original indices to restore order.
    indexed_weights = sorted(
        enumerate(weights), key=lambda x: x[1], reverse=True,
    )
    sorted_indices = [i for i, _ in indexed_weights]
    sorted_weights = [w for _, w in indexed_weights]

    # Normalize weights to fill the canvas area
    normalized = squarify.normalize_sizes(
        sorted_weights, canvas_width, canvas_height,
    )

    # Compute the treemap rectangles
    if padding > 0:
        rects = squarify.padded_squarify(
            normalized, 0, 0, canvas_width, canvas_height,
        )
    else:
        rects = squarify.squarify(
            normalized, 0, 0, canvas_width, canvas_height,
        )

    # Build Cell objects in sorted order
    sorted_cells: list[Cell] = []
    for rect in rects:
        cell = Cell(
            x=rect["x"],
            y=rect["y"],
            width=rect["dx"],
            height=rect["dy"],
        )
        sorted_cells.append(cell)

    # Restore original order
    cells: list[Cell | None] = [None] * len(images)
    for sorted_pos, original_idx in enumerate(sorted_indices):
        if sorted_pos < len(sorted_cells):
            cells[original_idx] = sorted_cells[sorted_pos]

    # Apply inner padding (shrink each cell by padding amount)
    if padding > 0:
        half_pad = padding / 2.0
        final_cells: list[Cell] = []
        for cell in cells:
            if cell is None:
                continue
            final_cells.append(Cell(
                x=cell.x + half_pad,
                y=cell.y + half_pad,
                width=max(1, cell.width - padding),
                height=max(1, cell.height - padding),
            ))
        result = final_cells
    else:
        result = [c for c in cells if c is not None]

    logger.info(
        "Layout computed: %d cells on %dx%d canvas (strategy=%s, padding=%d)",
        len(result), canvas_width, canvas_height, strategy.value, padding,
    )

    for i, cell in enumerate(result):
        logger.debug(
            "  Cell %d: (%.1f, %.1f) %.1fx%.1f  AR=%.2f",
            i, cell.x, cell.y, cell.width, cell.height, cell.aspect_ratio,
        )

    return result


def _pack_into_region(
    n_images: int,
    region_x: float,
    region_y: float,
    region_w: float,
    region_h: float,
    padding: int,
) -> list[Cell]:
    """Pack n_images into a rectangular region using squarify.

    Args:
        n_images: Number of images to fit in this region.
        region_x, region_y: Top-left corner of the region.
        region_w, region_h: Width and height of the region.
        padding: Gap between cells in pixels.

    Returns:
        List of Cell objects for this region.
    """
    if n_images <= 0 or region_w < 1 or region_h < 1:
        return []

    weights = [1.0] * n_images
    normalized = squarify.normalize_sizes(weights, region_w, region_h)

    rects = squarify.squarify(normalized, region_x, region_y, region_w, region_h)

    cells: list[Cell] = []
    half_pad = padding / 2.0
    for rect in rects:
        if padding > 0:
            cells.append(Cell(
                x=rect["x"] + half_pad,
                y=rect["y"] + half_pad,
                width=max(1, rect["dx"] - padding),
                height=max(1, rect["dy"] - padding),
            ))
        else:
            cells.append(Cell(
                x=rect["x"],
                y=rect["y"],
                width=rect["dx"],
                height=rect["dy"],
            ))

    return cells


def compute_hero_layout(
    images: list[ImageInfo],
    hero_index: int,
    canvas_width: int,
    canvas_height: int,
    hero_scale: float = 0.45,
    padding: int = 0,
) -> list[Cell]:
    """Compute a layout with one large centered hero image.

    Places the hero image as a large rectangle in the center of the
    canvas, then distributes remaining images into 4 surrounding
    strips (top, bottom, left, right) using treemap packing.

    Layout structure:
        ┌──────┬────────────┬──────┐
        │      │    TOP     │      │
        │ LEFT ├────────────┤RIGHT │
        │      │    HERO    │      │
        │      │  (large)   │      │
        │      ├────────────┤      │
        │      │   BOTTOM   │      │
        └──────┴────────────┴──────┘

    Args:
        images: List of ImageInfo objects.
        hero_index: Index of the hero image in the list.
        canvas_width: Output canvas width in pixels.
        canvas_height: Output canvas height in pixels.
        hero_scale: Fraction of canvas width/height for the hero (0.3-0.7).
        padding: Gap between cells in pixels.

    Returns:
        List of Cell objects (same order as images).
    """
    if not images:
        return []

    if len(images) == 1:
        # Only one image — it IS the hero, fill canvas
        half_pad = padding / 2.0
        return [Cell(
            x=half_pad, y=half_pad,
            width=canvas_width - padding,
            height=canvas_height - padding,
        )]

    n_remaining = len(images) - 1
    half_pad = padding / 2.0

    # ── Hero cell dimensions (centered) ──────────────────────────
    hero_w = canvas_width * hero_scale
    hero_h = canvas_height * hero_scale
    hero_x = (canvas_width - hero_w) / 2.0
    hero_y = (canvas_height - hero_h) / 2.0

    hero_cell = Cell(
        x=hero_x + half_pad,
        y=hero_y + half_pad,
        width=hero_w - padding,
        height=hero_h - padding,
    )

    # ── Define 4 surrounding strip regions ───────────────────────
    # Top strip: full width, above hero
    top = {"x": 0, "y": 0, "w": canvas_width, "h": hero_y}
    # Bottom strip: full width, below hero
    bot = {"x": 0, "y": hero_y + hero_h, "w": canvas_width, "h": canvas_height - hero_y - hero_h}
    # Left strip: left of hero, between top and bottom strips
    left = {"x": 0, "y": hero_y, "w": hero_x, "h": hero_h}
    # Right strip: right of hero, between top and bottom strips
    right = {"x": hero_x + hero_w, "y": hero_y, "w": canvas_width - hero_x - hero_w, "h": hero_h}

    strips = [top, bot, left, right]
    areas = [s["w"] * s["h"] for s in strips]
    total_area = sum(areas)

    # ── Distribute remaining images across strips by area ────────
    # Each strip gets images proportional to its share of total area
    counts = [0, 0, 0, 0]
    if total_area > 0:
        for i in range(4):
            counts[i] = max(1, round(n_remaining * areas[i] / total_area))

    # Adjust counts to exactly equal n_remaining
    diff = sum(counts) - n_remaining
    if diff > 0:
        # Remove from smallest strips first
        order = sorted(range(4), key=lambda i: areas[i])
        for i in order:
            while counts[i] > 1 and diff > 0:
                counts[i] -= 1
                diff -= 1
    elif diff < 0:
        # Add to largest strips first
        order = sorted(range(4), key=lambda i: areas[i], reverse=True)
        for i in order:
            while diff < 0:
                counts[i] += 1
                diff += 1

    # ── Pack each strip ──────────────────────────────────────────
    remaining_cells: list[Cell] = []
    for i, strip in enumerate(strips):
        strip_cells = _pack_into_region(
            counts[i], strip["x"], strip["y"], strip["w"], strip["h"], padding,
        )
        remaining_cells.extend(strip_cells)

    # ── Build final list in original image order ─────────────────
    # Hero goes at hero_index, remaining cells fill the rest
    cells: list[Cell] = []
    remaining_iter = iter(remaining_cells)
    for i in range(len(images)):
        if i == hero_index:
            cells.append(hero_cell)
        else:
            try:
                cells.append(next(remaining_iter))
            except StopIteration:
                # Shouldn't happen, but safety fallback
                cells.append(Cell(x=0, y=0, width=1, height=1))

    logger.info(
        "Hero layout computed: hero=%s (%.0f%% of canvas), %d surrounding cells",
        images[hero_index].path.name, hero_scale * 100, n_remaining,
    )

    return cells
