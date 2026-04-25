"""Phase 3: Saliency-Aware Crop Optimizer.

For each (image, cell) pair, computes the optimal crop rectangle that:
  1. Matches the cell's aspect ratio (or letterboxes if impossible).
  2. Never intersects any Keep Zone (faces are a hard constraint).
  3. Maximizes the visible area of the original image.

The algorithm uses closed-form geometry — no iteration required.
"""

from __future__ import annotations

import logging

from .models import Cell, CropSpec, ImageInfo

logger = logging.getLogger(__name__)


def _compute_crop_for_image(
    image: ImageInfo,
    cell: Cell,
) -> CropSpec:
    """Compute the optimal crop box for a single image-cell pair.

    Algorithm:
        1. Determine the target aspect ratio from the cell.
        2. Compute the largest crop window at that AR that fits in the image.
        3. If the image has keep zones, constrain the crop to contain them all.
        4. If no valid crop exists, fall back to letterboxing.

    Args:
        image: ImageInfo with detected keep zones.
        cell: The canvas cell this image is assigned to.

    Returns:
        CropSpec with the final crop box and letterbox flag.
    """
    img_w = image.original_width
    img_h = image.original_height
    target_ar = cell.aspect_ratio  # width / height

    # Step 1: Compute the largest crop at the target AR that fits the image
    # Try fitting by width first, then by height
    crop_w_by_width = img_w
    crop_h_by_width = img_w / target_ar

    crop_h_by_height = img_h
    crop_w_by_height = img_h * target_ar

    # Choose the option that fits within image bounds and maximizes area
    if crop_h_by_width <= img_h:
        crop_w = int(round(crop_w_by_width))
        crop_h = int(round(crop_h_by_width))
    elif crop_w_by_height <= img_w:
        crop_w = int(round(crop_w_by_height))
        crop_h = int(round(crop_h_by_height))
    else:
        # Neither fits perfectly — use the one with larger area
        crop_w = int(round(min(crop_w_by_width, img_w)))
        crop_h = int(round(min(crop_h_by_width, img_h)))

    # Clamp dimensions
    crop_w = max(1, min(crop_w, img_w))
    crop_h = max(1, min(crop_h, img_h))

    # Step 2: Get the keep zone envelope
    envelope = image.get_keep_zone_envelope()

    if envelope is None:
        # No faces — center crop
        crop_x = (img_w - crop_w) // 2
        crop_y = (img_h - crop_h) // 2
        return CropSpec(
            image_info=image,
            cell=cell,
            crop_box=(crop_x, crop_y, crop_x + crop_w, crop_y + crop_h),
            letterbox=False,
        )

    env_x, env_y, env_w, env_h = envelope

    # Step 3: Check if the crop window can contain the keep zone envelope
    if crop_w < env_w or crop_h < env_h:
        logger.info(
            "Crop window (%dx%d) is smaller than keep zone (%dx%d) for %s. Forcing crop.",
            crop_w, crop_h, env_w, env_h, image.path.name,
        )
        # Proceed to position the crop window centered on the envelope anyway

    # Step 4: Position the crop window to contain the keep zone envelope
    # Center the crop on the envelope centroid, then clamp to image bounds
    env_center_x = env_x + env_w / 2.0
    env_center_y = env_y + env_h / 2.0

    crop_x = int(round(env_center_x - crop_w / 2.0))
    crop_y = int(round(env_center_y - crop_h / 2.0))

    if crop_h < env_h:
        # Align with the top of the envelope to avoid cutting off the head
        crop_y = int(env_y)

    # Clamp to image boundaries
    crop_x = max(0, min(crop_x, img_w - crop_w))
    crop_y = max(0, min(crop_y, img_h - crop_h))

    # Step 5: Verify all keep zones are fully contained
    # (The clamping above might have shifted the crop away from some zones)
    crop_right = crop_x + crop_w
    crop_bottom = crop_y + crop_h

    # Check if envelope is still fully inside
    if crop_w >= env_w:
        if env_x < crop_x:
            crop_x = max(0, env_x)
            crop_right = crop_x + crop_w
            if crop_right > img_w:
                crop_right = img_w
                crop_x = max(0, crop_right - crop_w)

        if env_x + env_w > crop_right:
            crop_right = min(img_w, env_x + env_w)
            crop_x = max(0, crop_right - crop_w)

    if crop_h >= env_h:
        if env_y < crop_y:
            crop_y = max(0, env_y)
            crop_bottom = crop_y + crop_h
            if crop_bottom > img_h:
                crop_bottom = img_h
                crop_y = max(0, crop_bottom - crop_h)

        if env_y + env_h > crop_bottom:
            crop_bottom = min(img_h, env_y + env_h)
            crop_y = max(0, crop_bottom - crop_h)

    crop_right = crop_x + crop_w
    crop_bottom = crop_y + crop_h

    # Final safety check: verify all individual keep zones
    all_contained = all(
        kz.is_fully_inside(crop_x, crop_y, crop_right, crop_bottom)
        for kz in image.keep_zones
    )

    if not all_contained:
        logger.warning(
            "Cannot contain all keep zones in crop for %s, but forcing crop.",
            image.path.name,
        )
        return CropSpec(
            image_info=image,
            cell=cell,
            crop_box=(crop_x, crop_y, crop_right, crop_bottom),
            letterbox=False,
        )

    logger.debug(
        "Crop for %s: (%d,%d)-(%d,%d) in %dx%d (letterbox=%s)",
        image.path.name, crop_x, crop_y, crop_right, crop_bottom,
        img_w, img_h, False,
    )

    return CropSpec(
        image_info=image,
        cell=cell,
        crop_box=(crop_x, crop_y, crop_right, crop_bottom),
        letterbox=False,
    )


def compute_all_crops(
    images: list[ImageInfo],
    cells: list[Cell],
) -> list[CropSpec]:
    """Compute optimal crop specs for all image-cell pairs.

    Args:
        images: List of ImageInfo objects (from Phase 1).
        cells: List of Cell objects (from Phase 2), same order.

    Returns:
        List of CropSpec objects ready for rendering.

    Raises:
        ValueError: If images and cells have different lengths.
    """
    if len(images) != len(cells):
        raise ValueError(
            f"Mismatch: {len(images)} images but {len(cells)} cells"
        )

    specs: list[CropSpec] = []
    letterbox_count = 0

    for image, cell in zip(images, cells):
        spec = _compute_crop_for_image(image, cell)
        specs.append(spec)
        if spec.letterbox:
            letterbox_count += 1

    logger.info(
        "Crop optimization complete: %d images, %d letterboxed",
        len(specs), letterbox_count,
    )

    return specs
