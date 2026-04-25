"""Phase 1: Face / Saliency Detection.

Scans every input image to detect faces and generates padded
bounding boxes ("Keep Zones") that must not be cropped.

Uses MediaPipe Face Detection as primary detector with an
OpenCV Haar Cascade fallback.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from .models import ImageInfo, KeepZone

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


_MEDIAPIPE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_full_range/float16/latest/"
    "blaze_face_full_range.tflite"
)

_MODEL_CACHE_DIR = Path(__file__).parent / ".model_cache"


def _ensure_mediapipe_model() -> Path:
    """Download the BlazeFace full-range model if it doesn't exist locally.

    Uses the full-range model which detects faces up to ~5m distance,
    critical for full-body shots where faces are relatively small.

    Returns the path to the .tflite model file.
    """
    import urllib.request

    _MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _MODEL_CACHE_DIR / "blaze_face_full_range.tflite"

    if model_path.exists():
        return model_path

    logger.info("Downloading MediaPipe face detection model (full-range)...")
    urllib.request.urlretrieve(_MEDIAPIPE_MODEL_URL, str(model_path))
    logger.info("Model saved to %s", model_path)

    return model_path


def _try_mediapipe_detection(
    image_rgb: np.ndarray,
    img_width: int,
    img_height: int,
    confidence: float,
) -> list[KeepZone] | None:
    """Attempt face detection using MediaPipe Tasks API.

    Uses mp.tasks.vision.FaceDetector (the current API for MediaPipe >=0.10.14).
    Auto-downloads the BlazeFace short-range model on first run.

    Returns None if MediaPipe is not available or fails to initialize.
    Returns a list of KeepZone objects otherwise (possibly empty).
    """
    try:
        import mediapipe as mp
    except ImportError:
        logger.warning("MediaPipe not installed, falling back to OpenCV Haar cascades.")
        return None

    try:
        model_path = _ensure_mediapipe_model()

        base_options = mp.tasks.BaseOptions(model_asset_path=str(model_path))
        options = mp.tasks.vision.FaceDetectorOptions(
            base_options=base_options,
            min_detection_confidence=confidence,
        )

        with mp.tasks.vision.FaceDetector.create_from_options(options) as detector:
            # Convert numpy RGB array to MediaPipe Image
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
            result = detector.detect(mp_image)

            if not result.detections:
                return []

            zones: list[KeepZone] = []
            for detection in result.detections:
                bbox = detection.bounding_box

                # Tasks API returns pixel coordinates directly
                x = bbox.origin_x
                y = bbox.origin_y
                w = bbox.width
                h = bbox.height

                conf = detection.categories[0].score if detection.categories else confidence

                zones.append(KeepZone(
                    x=x, y=y, width=w, height=h, confidence=conf,
                ))

            return zones

    except Exception as e:
        logger.warning("MediaPipe detection failed: %s. Falling back.", e)
        return None


def _haar_cascade_detection(
    image_gray: np.ndarray,
    img_width: int,
    img_height: int,
) -> list[KeepZone]:
    """Fallback face detection using OpenCV Haar Cascades."""
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    if face_cascade.empty():
        logger.error("Failed to load Haar cascade classifier from %s", cascade_path)
        return []

    faces = face_cascade.detectMultiScale(
        image_gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
    )

    zones: list[KeepZone] = []
    for (x, y, w, h) in faces:
        zones.append(KeepZone(x=x, y=y, width=w, height=h, confidence=0.7))

    return zones


def _apply_padding(
    zones: list[KeepZone],
    img_width: int,
    img_height: int,
    padding_ratio: float = 0.25,
) -> list[KeepZone]:
    """Expand each KeepZone by a padding ratio to include head/hair/ears.

    The padding is proportional to the face bounding box size and
    is clamped to image boundaries.
    """
    padded: list[KeepZone] = []
    for kz in zones:
        pad_x = int(kz.width * padding_ratio)
        pad_y = int(kz.height * padding_ratio)

        # Expand with extra padding on top for hair/forehead
        top_pad = int(kz.height * padding_ratio * 1.5)

        new_x = max(0, kz.x - pad_x)
        new_y = max(0, kz.y - top_pad)
        new_right = min(img_width, kz.right + pad_x)
        new_bottom = min(img_height, kz.bottom + pad_y)

        padded.append(KeepZone(
            x=new_x,
            y=new_y,
            width=new_right - new_x,
            height=new_bottom - new_y,
            confidence=kz.confidence,
        ))

    return padded


def _expand_to_body(
    zones: list[KeepZone],
    img_width: int,
    img_height: int,
) -> list[KeepZone]:
    """Expand face keep zones to estimated full-body bounding boxes.

    Uses standard anthropometric ratios:
      - Total body height ≈ 7.5 × face height
      - Shoulder span ≈ 3 × face width
      - Face sits at the top ~1/7.5 of the body

    The resulting keep zone covers the estimated head-to-toe region,
    clamped to image boundaries. This makes the cropper prioritize
    showing the entire person rather than just the face.
    """
    expanded: list[KeepZone] = []
    for kz in zones:
        face_cx = kz.x + kz.width / 2.0
        face_top = kz.y

        # Estimate body dimensions from face size
        body_height = kz.height * 7.5
        body_width = kz.width * 3.0

        # Body extends from above the head to the feet
        body_top = face_top - kz.height * 0.5  # hair/head top
        body_bottom = face_top + body_height
        body_left = face_cx - body_width / 2.0
        body_right = face_cx + body_width / 2.0

        # Clamp to image bounds
        new_x = max(0, int(body_left))
        new_y = max(0, int(body_top))
        new_right = min(img_width, int(body_right))
        new_bottom = min(img_height, int(body_bottom))

        expanded.append(KeepZone(
            x=new_x,
            y=new_y,
            width=new_right - new_x,
            height=new_bottom - new_y,
            confidence=kz.confidence,
        ))

    return expanded


def detect_single_image(
    image_path: Path,
    confidence: float = 0.5,
    padding_ratio: float = 0.25,
    body_aware: bool = True,
) -> ImageInfo:
    """Detect faces in a single image and return ImageInfo with Keep Zones.

    Args:
        image_path: Path to the input image.
        confidence: Minimum detection confidence (0-1).
        padding_ratio: How much to expand face boxes (fraction of face size).
        body_aware: If True, expand keep zones to estimated full-body bounds.
                    If False, only protect the face/head region.

    Returns:
        ImageInfo with detected keep zones.

    Raises:
        ValueError: If the image cannot be read.
    """
    image_bgr = cv2.imread(str(image_path))
    if image_bgr is None:
        raise ValueError(f"Cannot read image: {image_path}")

    img_height, img_width = image_bgr.shape[:2]
    image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    image_gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # Try MediaPipe first
    zones = _try_mediapipe_detection(image_rgb, img_width, img_height, confidence)

    # Fall back to Haar cascades if MediaPipe unavailable or failed
    if zones is None:
        logger.info("Using Haar cascade fallback for %s", image_path.name)
        zones = _haar_cascade_detection(image_gray, img_width, img_height)

    # Expand keep zones
    if zones:
        if body_aware:
            # Expand to estimated full-body bounding box
            zones = _expand_to_body(zones, img_width, img_height)
        else:
            # Only pad around the face/head
            zones = _apply_padding(zones, img_width, img_height, padding_ratio)

    logger.info(
        "Detected %d face(s) in %s (%dx%d)",
        len(zones), image_path.name, img_width, img_height,
    )

    return ImageInfo(
        path=image_path,
        original_width=img_width,
        original_height=img_height,
        keep_zones=zones,
    )


def detect_all_images(
    input_dir: Path,
    confidence: float = 0.5,
    padding_ratio: float = 0.25,
    body_aware: bool = True,
) -> list[ImageInfo]:
    """Scan all images in a directory and detect faces.

    Args:
        input_dir: Directory containing input images.
        confidence: Minimum face detection confidence.
        padding_ratio: Padding ratio for keep zones.
        body_aware: If True, expand keep zones to full-body estimates.

    Returns:
        List of ImageInfo objects, one per valid image found.

    Raises:
        FileNotFoundError: If input_dir does not exist.
        ValueError: If no valid images are found.
    """
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    image_paths = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in IMAGE_EXTENSIONS and p.is_file()
    )

    if not image_paths:
        raise ValueError(f"No valid images found in {input_dir}")

    logger.info("Found %d images in %s", len(image_paths), input_dir)

    results: list[ImageInfo] = []
    for path in image_paths:
        try:
            info = detect_single_image(path, confidence, padding_ratio, body_aware)
            results.append(info)
        except ValueError as e:
            logger.warning("Skipping %s: %s", path.name, e)

    if not results:
        raise ValueError(f"No images could be processed from {input_dir}")

    return results
