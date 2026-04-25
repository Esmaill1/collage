"""Phase 4: PIL Rendering Engine.

Takes CropSpec objects from the crop optimizer and composites the
final collage image using Pillow. Handles normal crops, letterboxing,
and debug overlay rendering.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import CropSpec

logger = logging.getLogger(__name__)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to an RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (26, 26, 26)  # Default dark gray
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _render_normal(
    canvas: Image.Image,
    spec: CropSpec,
) -> None:
    """Render a normally-cropped image into its cell on the canvas."""
    img = Image.open(spec.image_info.path)
    img = img.convert("RGB")

    # Apply the crop
    left, top, right, bottom = spec.crop_box
    cropped = img.crop((left, top, right, bottom))

    # Resize to cell dimensions
    cell_w = int(round(spec.cell.width))
    cell_h = int(round(spec.cell.height))

    if cell_w < 1 or cell_h < 1:
        return

    resized = cropped.resize((cell_w, cell_h), Image.LANCZOS)

    # Paste into canvas
    paste_x = int(round(spec.cell.x))
    paste_y = int(round(spec.cell.y))
    canvas.paste(resized, (paste_x, paste_y))


def _render_letterboxed(
    canvas: Image.Image,
    spec: CropSpec,
    bg_color: tuple[int, int, int],
) -> None:
    """Render a letterboxed image (entire image fit within cell with bars)."""
    img = Image.open(spec.image_info.path)
    img = img.convert("RGB")

    cell_w = int(round(spec.cell.width))
    cell_h = int(round(spec.cell.height))

    if cell_w < 1 or cell_h < 1:
        return

    cell_ar = cell_w / cell_h
    img_ar = img.width / img.height

    if img_ar > cell_ar:
        # Image is wider — fit by width, pad top/bottom
        fit_w = cell_w
        fit_h = int(round(cell_w / img_ar))
    else:
        # Image is taller — fit by height, pad left/right
        fit_h = cell_h
        fit_w = int(round(cell_h * img_ar))

    fit_w = max(1, fit_w)
    fit_h = max(1, fit_h)

    resized = img.resize((fit_w, fit_h), Image.LANCZOS)

    # Create a cell-sized background with padding color
    cell_bg = Image.new("RGB", (cell_w, cell_h), bg_color)

    # Center the resized image within the cell
    offset_x = (cell_w - fit_w) // 2
    offset_y = (cell_h - fit_h) // 2
    cell_bg.paste(resized, (offset_x, offset_y))

    # Paste into main canvas
    paste_x = int(round(spec.cell.x))
    paste_y = int(round(spec.cell.y))
    canvas.paste(cell_bg, (paste_x, paste_y))


def render_collage(
    specs: list[CropSpec],
    canvas_width: int,
    canvas_height: int,
    output_path: Path,
    bg_color: str = "#1a1a1a",
) -> Path:
    """Render the final collage image from CropSpecs.

    Args:
        specs: List of CropSpec objects from the crop optimizer.
        canvas_width: Output canvas width in pixels.
        canvas_height: Output canvas height in pixels.
        output_path: Where to save the final image.
        bg_color: Background/letterbox color as hex string.

    Returns:
        Path to the saved output image.
    """
    rgb_bg = _hex_to_rgb(bg_color)
    canvas = Image.new("RGB", (canvas_width, canvas_height), rgb_bg)

    for i, spec in enumerate(specs):
        logger.debug("Rendering image %d/%d: %s", i + 1, len(specs), spec.image_info.path.name)

        try:
            if spec.letterbox:
                _render_letterboxed(canvas, spec, rgb_bg)
            else:
                _render_normal(canvas, spec)
        except Exception as e:
            logger.error("Failed to render %s: %s", spec.image_info.path.name, e)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save with appropriate format
    suffix = output_path.suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        canvas.save(output_path, "JPEG", quality=95)
    elif suffix == ".webp":
        canvas.save(output_path, "WEBP", quality=95)
    else:
        canvas.save(output_path, "PNG")

    logger.info("Collage saved to %s (%dx%d)", output_path, canvas_width, canvas_height)
    return output_path


def render_debug_image(
    specs: list[CropSpec],
    canvas_width: int,
    canvas_height: int,
    output_path: Path,
    bg_color: str = "#1a1a1a",
) -> Path:
    """Render a debug collage with face detection overlays.

    Draws:
      - Red rectangles: raw face bounding boxes (Keep Zones)
      - Green rectangle: Keep Zone envelope (union of all faces)
      - Cyan outlines: cell boundaries on the canvas
      - Labels: image filename and face count

    Args:
        specs: List of CropSpec objects.
        canvas_width: Output canvas width in pixels.
        canvas_height: Output canvas height in pixels.
        output_path: Where to save the debug image.
        bg_color: Background color as hex string.

    Returns:
        Path to the saved debug image.
    """
    rgb_bg = _hex_to_rgb(bg_color)
    canvas = Image.new("RGB", (canvas_width, canvas_height), rgb_bg)

    for spec in specs:
        try:
            img = Image.open(spec.image_info.path).convert("RGB")
            draw_on_img = ImageDraw.Draw(img)

            # Draw individual face Keep Zones in RED
            for kz in spec.image_info.keep_zones:
                draw_on_img.rectangle(
                    [kz.x, kz.y, kz.right, kz.bottom],
                    outline="red",
                    width=max(2, min(img.width, img.height) // 150),
                )

            # Draw the keep zone envelope in GREEN
            envelope = spec.image_info.get_keep_zone_envelope()
            if envelope:
                ex, ey, ew, eh = envelope
                draw_on_img.rectangle(
                    [ex, ey, ex + ew, ey + eh],
                    outline="lime",
                    width=max(3, min(img.width, img.height) // 100),
                )

            # Draw the crop box in YELLOW
            left, top, right, bottom = spec.crop_box
            draw_on_img.rectangle(
                [left, top, right, bottom],
                outline="yellow",
                width=max(2, min(img.width, img.height) // 120),
            )

            # Crop and resize for the cell
            cell_w = int(round(spec.cell.width))
            cell_h = int(round(spec.cell.height))

            if cell_w < 1 or cell_h < 1:
                continue

            if spec.letterbox:
                # Fit entire annotated image into cell
                cell_ar = cell_w / cell_h
                img_ar = img.width / img.height
                if img_ar > cell_ar:
                    fit_w = cell_w
                    fit_h = max(1, int(round(cell_w / img_ar)))
                else:
                    fit_h = cell_h
                    fit_w = max(1, int(round(cell_h * img_ar)))

                resized = img.resize((fit_w, fit_h), Image.LANCZOS)
                cell_bg = Image.new("RGB", (cell_w, cell_h), rgb_bg)
                offset_x = (cell_w - fit_w) // 2
                offset_y = (cell_h - fit_h) // 2
                cell_bg.paste(resized, (offset_x, offset_y))
                canvas.paste(cell_bg, (int(spec.cell.x), int(spec.cell.y)))
            else:
                cropped = img.crop((left, top, right, bottom))
                resized = cropped.resize((cell_w, cell_h), Image.LANCZOS)
                canvas.paste(resized, (int(spec.cell.x), int(spec.cell.y)))

        except Exception as e:
            logger.error("Failed to render debug for %s: %s", spec.image_info.path.name, e)

    # Draw cell boundaries and labels on the canvas
    canvas_draw = ImageDraw.Draw(canvas)

    for spec in specs:
        cx = int(round(spec.cell.x))
        cy = int(round(spec.cell.y))
        cw = int(round(spec.cell.width))
        ch = int(round(spec.cell.height))

        # Cyan cell boundary
        canvas_draw.rectangle(
            [cx, cy, cx + cw, cy + ch],
            outline="cyan",
            width=2,
        )

        # Label with filename and face count
        label = f"{spec.image_info.path.name} ({len(spec.image_info.keep_zones)} faces)"
        if spec.letterbox:
            label += " [LB]"

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Draw label background
        bbox = canvas_draw.textbbox((cx + 4, cy + 4), label, font=font)
        canvas_draw.rectangle(
            [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2],
            fill=(0, 0, 0, 180),
        )
        canvas_draw.text((cx + 4, cy + 4), label, fill="white", font=font)

    # Save debug image
    debug_path = output_path.parent / f"{output_path.stem}_debug{output_path.suffix}"
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(debug_path, "PNG")

    logger.info("Debug image saved to %s", debug_path)
    return debug_path
