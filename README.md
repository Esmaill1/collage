# Saliency-Aware Collage Generator

A Python CLI tool that packs images of varying aspect ratios into a **5:6 canvas** while **guaranteeing that detected faces are never cropped**. It gracefully handles situations where perfectly fitting all bodies is mathematically impossible by prioritizing faces and head-alignment over lower bodies, avoiding ugly black letterbox bars.

For developer documentation, architecture overview, and how to contribute, please see [DEVELOPER.md](DEVELOPER.md).

## How It Works

The pipeline has 4 phases:

1. **Face Detection** — Uses MediaPipe BlazeFace (with OpenCV Haar cascade fallback) to detect faces and create padded "Keep Zones". Can optionally expand to estimate full-body bounds.
2. **Treemap Layout** — Uses a Squarified Treemap algorithm to partition the canvas into cells (zero wasted space). Supports a "Hero" layout to feature one large image.
3. **Saliency-Aware Crop** — For each image-cell pair, computes the optimal crop that preserves all faces (closed-form geometry). If a crop is too tight, it will smartly top-align to keep heads visible without resorting to letterboxing.
4. **PIL Rendering** — Composites the final collage with LANCZOS resampling.

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Basic usage
python3 main.py --input_dir ./photos --output_file collage.png

# With debug overlays (shows face detection boxes)
python3 main.py --input_dir ./photos --output_file collage.png --debug

# Hero layout (features an image with 'hero' in its filename prominently in the center)
python3 main.py --input_dir ./photos --output_file collage.png --hero

# Full options
python3 main.py \
  --input_dir ./photos \
  --output_file collage.png \
  --width 2500 \
  --padding 4 \
  --bg-color "#1a1a1a" \
  --weight-strategy faces \
  --face-confidence 0.5 \
  --face-padding 0.25 \
  --hero \
  --hero-scale 0.45 \
  --debug \
  -v
```

## CLI Options

| Flag | Default | Description |
|---|---|---|
| `--input_dir` | *(required)* | Folder containing input images |
| `--output_file` | *(required)* | Path to save the output collage |
| `--width` | `2500` | Canvas width in pixels (height auto-computed for 5:6) |
| `--debug` | `false` | Output debug image with face detection overlays |
| `--padding` | `4` | Gap between images in pixels |
| `--bg-color` | `#1a1a1a` | Background/letterbox color (hex) |
| `--face-confidence` | `0.35` | MediaPipe face detection confidence (0-1) |
| `--weight-strategy` | `equal` | Image weighting: `equal`, `faces`, or `resolution` |
| `--face-padding` | `0.35` | Padding around face boxes (fraction of face size) |
| `--face-only` | `false` | Only protect faces (not full body). By default, keep zones expand to full body. |
| `--hero` | `false` | Enable hero layout. Image with 'hero' in filename is placed large/centered. |
| `--hero-scale` | `0.45` | Hero image size as fraction of canvas (0.3-0.7). |
| `-v` / `--verbose` | `false` | Enable debug logging |

## Weight Strategies

- **`equal`** — All images get roughly the same cell area
- **`faces`** — Images with more faces get larger cells
- **`resolution`** — Higher-resolution images get larger cells

## Debug Output

When `--debug` is enabled, an additional image is saved with:
- 🔴 **Red rectangles** — Individual face bounding boxes
- 🟢 **Green rectangles** — Keep Zone envelopes (union of all faces + padding)
- 🟡 **Yellow rectangles** — Crop window applied to each image
- 🔵 **Cyan outlines** — Cell boundaries on the canvas
- Labels with filename and face count

## Project Structure

```
collage/
├── collage_generator/
│   ├── __init__.py      # Package init
│   ├── cli.py           # CLI entry point & pipeline orchestration
│   ├── detector.py      # Phase 1: Face detection (MediaPipe + Haar)
│   ├── layout.py        # Phase 2: Squarified Treemap layout
│   ├── cropper.py       # Phase 3: Saliency-aware crop optimizer
│   ├── renderer.py      # Phase 4: PIL rendering engine
│   └── models.py        # Data classes (KeepZone, ImageInfo, Cell, CropSpec)
├── main.py              # Script entry point
├── requirements.txt     # Dependencies
├── DEVELOPER.md         # Documentation for contributors
└── README.md            # This file
```

## Supported Image Formats

`.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp`

## Requirements

- Python 3.10+
- OpenCV (`opencv-python`)
- MediaPipe (`mediapipe`)
- Pillow (`Pillow`)
- squarify (`squarify`)
- NumPy (`numpy`)
