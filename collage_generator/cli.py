"""CLI entry point for the Saliency-Aware Collage Generator.

Parses command-line arguments and orchestrates the 4-phase pipeline:
  Phase 1: Face detection (detector.py)
  Phase 2: Treemap layout (layout.py)
  Phase 3: Saliency-aware crop (cropper.py)
  Phase 4: PIL rendering (renderer.py)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .cropper import compute_all_crops
from .detector import detect_all_images
from .layout import WeightStrategy, compute_hero_layout, compute_layout
from .renderer import render_collage, render_debug_image

# Fixed aspect ratio: 5:6 (width:height)
ASPECT_RATIO = 5 / 6


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate CLI arguments."""
    parser = argparse.ArgumentParser(
        prog="collage",
        description=(
            "Saliency-Aware Collage Generator\n\n"
            "Packs images into a 5:6 canvas while guaranteeing that "
            "detected faces are never cropped."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Required arguments
    parser.add_argument(
        "--input_dir",
        type=Path,
        required=True,
        help="Folder containing input images.",
    )
    parser.add_argument(
        "--output_file",
        type=Path,
        required=True,
        help="Path to save the output collage (e.g., collage.png).",
    )

    # Optional arguments
    parser.add_argument(
        "--width",
        type=int,
        default=2500,
        help="Canvas width in pixels. (default: 2500)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=0,
        help="Canvas height in pixels. If 0 (default), auto-computed for 5:6 ratio.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Output an additional debug image with face detection overlays.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=4,
        help="Gap between images in pixels. (default: 4)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default="#1a1a1a",
        help="Background / letterbox color as hex. (default: #1a1a1a)",
    )
    parser.add_argument(
        "--face-confidence",
        type=float,
        default=0.35,
        help="Minimum face detection confidence 0-1. (default: 0.35)",
    )
    parser.add_argument(
        "--weight-strategy",
        type=str,
        choices=["equal", "faces", "resolution"],
        default="equal",
        help="How to weight images for treemap cell sizing. (default: equal)",
    )
    parser.add_argument(
        "--face-padding",
        type=float,
        default=0.35,
        help="Padding around face boxes as fraction of face size. (default: 0.35)",
    )
    parser.add_argument(
        "--face-only",
        action="store_true",
        default=False,
        help="Only protect faces (not full body). By default, keep zones expand to estimated full-body bounds.",
    )
    parser.add_argument(
        "--hero",
        action="store_true",
        default=False,
        help="Enable hero layout. The image with 'hero' in its filename is placed large and centered.",
    )
    parser.add_argument(
        "--hero-scale",
        type=float,
        default=0.45,
        help="Hero image size as fraction of canvas (0.3-0.7). (default: 0.45)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose/debug logging.",
    )

    args = parser.parse_args(argv)

    # Validate
    if args.width < 100:
        parser.error("--width must be at least 100 pixels.")
    if args.height < 0:
        parser.error("--height must be >= 0 (0 = auto).")
    if args.height > 0 and args.height < 100:
        parser.error("--height must be at least 100 pixels (or 0 for auto).")
    if not 0.0 <= args.face_confidence <= 1.0:
        parser.error("--face-confidence must be between 0.0 and 1.0.")
    if args.padding < 0:
        parser.error("--padding must be >= 0.")
    if not 0.0 <= args.face_padding <= 1.0:
        parser.error("--face-padding must be between 0.0 and 1.0.")

    return args


def _setup_logging(verbose: bool) -> None:
    """Configure logging format and level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def run(argv: list[str] | None = None) -> int:
    """Main entry point for the collage generator.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    logger = logging.getLogger("collage")
    logger.info("=" * 60)
    logger.info("Saliency-Aware Collage Generator v1.0")
    logger.info("=" * 60)

    canvas_width = args.width
    if args.height > 0:
        canvas_height = args.height
    else:
        canvas_height = int(round(canvas_width / ASPECT_RATIO))
    strategy = WeightStrategy(args.weight_strategy)

    logger.info("Canvas: %d x %d", canvas_width, canvas_height)
    logger.info("Input:  %s", args.input_dir)
    logger.info("Output: %s", args.output_file)
    logger.info("Strategy: %s | Padding: %dpx | Debug: %s",
                strategy.value, args.padding, args.debug)

    t_start = time.perf_counter()

    try:
        # ── Phase 1: Face Detection ──────────────────────────────────
        logger.info("")
        logger.info("Phase 1/4: Detecting faces...")
        t1 = time.perf_counter()
        images = detect_all_images(
            args.input_dir,
            confidence=args.face_confidence,
            padding_ratio=args.face_padding,
            body_aware=not args.face_only,
        )
        total_faces = sum(len(img.keep_zones) for img in images)
        logger.info(
            "  → %d images loaded, %d total faces detected (%.2fs)",
            len(images), total_faces, time.perf_counter() - t1,
        )

        # ── Phase 2: Layout ──────────────────────────────────────────
        logger.info("")
        t2 = time.perf_counter()

        # Check for hero mode
        hero_index = None
        if args.hero:
            for i, img in enumerate(images):
                if "hero" in img.path.stem.lower():
                    hero_index = i
                    break
            if hero_index is None:
                logger.warning(
                    "--hero flag set but no image with 'hero' in filename found. "
                    "Using standard treemap layout."
                )

        if hero_index is not None:
            logger.info("Phase 2/4: Computing hero layout (hero=%s)...",
                        images[hero_index].path.name)
            cells = compute_hero_layout(
                images,
                hero_index=hero_index,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                hero_scale=args.hero_scale,
                padding=args.padding,
            )
        else:
            logger.info("Phase 2/4: Computing treemap layout...")
            cells = compute_layout(
                images,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                strategy=strategy,
                padding=args.padding,
            )

        logger.info(
            "  → %d cells computed (%.2fs)",
            len(cells), time.perf_counter() - t2,
        )

        # ── Phase 3: Saliency-Aware Crop ────────────────────────────
        logger.info("")
        logger.info("Phase 3/4: Optimizing crops...")
        t3 = time.perf_counter()
        specs = compute_all_crops(images, cells)
        letterboxed = sum(1 for s in specs if s.letterbox)
        logger.info(
            "  → %d crop specs ready, %d letterboxed (%.2fs)",
            len(specs), letterboxed, time.perf_counter() - t3,
        )

        # ── Phase 4: Rendering ──────────────────────────────────────
        logger.info("")
        logger.info("Phase 4/4: Rendering collage...")
        t4 = time.perf_counter()
        output = render_collage(
            specs,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            output_path=args.output_file,
            bg_color=args.bg_color,
        )
        logger.info(
            "  → Collage saved: %s (%.2fs)",
            output, time.perf_counter() - t4,
        )

        # ── Debug output (optional) ─────────────────────────────────
        if args.debug:
            logger.info("")
            logger.info("Rendering debug overlay...")
            debug_output = render_debug_image(
                specs,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                output_path=args.output_file,
                bg_color=args.bg_color,
            )
            logger.info("  → Debug image saved: %s", debug_output)

        # ── Summary ─────────────────────────────────────────────────
        elapsed = time.perf_counter() - t_start
        logger.info("")
        logger.info("=" * 60)
        logger.info("Done in %.2f seconds.", elapsed)
        logger.info("  Images: %d | Faces: %d | Letterboxed: %d",
                     len(images), total_faces, letterboxed)
        logger.info("  Canvas: %d x %d | Output: %s",
                     canvas_width, canvas_height, args.output_file)
        logger.info("=" * 60)

        return 0

    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        return 1
    except ValueError as e:
        logger.error("Validation error: %s", e)
        return 1
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        return 1
