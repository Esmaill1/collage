"""Data models used throughout the collage generation pipeline.

These dataclasses define the data structures that flow between the
four phases: detection → layout → cropping → rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class KeepZone:
    """A bounding box region that must not be cropped (face + padding).

    Coordinates are in the original image pixel space.
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0

    @property
    def right(self) -> int:
        """Right edge x-coordinate."""
        return self.x + self.width

    @property
    def bottom(self) -> int:
        """Bottom edge y-coordinate."""
        return self.y + self.height

    @property
    def center_x(self) -> float:
        """Horizontal center."""
        return self.x + self.width / 2.0

    @property
    def center_y(self) -> float:
        """Vertical center."""
        return self.y + self.height / 2.0

    def intersects(self, left: int, top: int, right: int, bottom: int) -> bool:
        """Check if this keep zone intersects with a given rectangle."""
        return not (
            right <= self.x
            or left >= self.right
            or bottom <= self.y
            or top >= self.bottom
        )

    def is_fully_inside(self, left: int, top: int, right: int, bottom: int) -> bool:
        """Check if this keep zone is fully contained within a rectangle."""
        return (
            left <= self.x
            and top <= self.y
            and right >= self.right
            and bottom >= self.bottom
        )


@dataclass
class ImageInfo:
    """All metadata about one input image, including detected faces.

    Populated during Phase 1 (detection) and consumed by all
    subsequent phases.
    """

    path: Path
    original_width: int
    original_height: int
    keep_zones: list[KeepZone] = field(default_factory=list)
    weight: float = 1.0

    @property
    def aspect_ratio(self) -> float:
        """Width / Height ratio of the original image."""
        if self.original_height == 0:
            return 1.0
        return self.original_width / self.original_height

    @property
    def has_faces(self) -> bool:
        """Whether any faces were detected in this image."""
        return len(self.keep_zones) > 0

    def get_keep_zone_envelope(self) -> tuple[int, int, int, int] | None:
        """Compute the bounding box that contains ALL keep zones.

        Returns:
            (x, y, width, height) of the envelope, or None if no keep zones.
        """
        if not self.keep_zones:
            return None

        min_x = min(kz.x for kz in self.keep_zones)
        min_y = min(kz.y for kz in self.keep_zones)
        max_right = max(kz.right for kz in self.keep_zones)
        max_bottom = max(kz.bottom for kz in self.keep_zones)

        return (min_x, min_y, max_right - min_x, max_bottom - min_y)


@dataclass
class Cell:
    """A rectangular region on the output canvas assigned to one image.

    Coordinates are in output canvas pixel space.
    """

    x: float
    y: float
    width: float
    height: float

    @property
    def aspect_ratio(self) -> float:
        """Width / Height ratio of this cell."""
        if self.height == 0:
            return 1.0
        return self.width / self.height

    @property
    def area(self) -> float:
        """Area of this cell in pixels²."""
        return self.width * self.height


@dataclass
class CropSpec:
    """The final crop + resize instructions for one image.

    Produced by Phase 3 (crop optimizer) and consumed by Phase 4 (renderer).
    """

    image_info: ImageInfo
    cell: Cell
    crop_box: tuple[int, int, int, int]  # (left, top, right, bottom) in original image coords
    letterbox: bool = False  # True if letterboxing is needed to preserve faces
