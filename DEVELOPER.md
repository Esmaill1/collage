# Developer Documentation

Welcome to the Saliency-Aware Collage Generator developer documentation. This guide is designed to help you understand the system architecture, how the different components interact, and how to extend or debug the tool.

## Architecture Overview

The system is designed as a linear, decoupled 4-phase pipeline wrapped by either a command-line interface or a web interface. The core pipeline logic lives in `collage_generator/`.

The system's execution flow based on usage mode:
**Web UI (React)** -> **FastAPI Backend (`api.py`)** -> **Pipeline Execution**
**CLI Tool (`main.py`)** -> **Pipeline Execution**

### The Core Pipeline

Each phase in the core pipeline is separated by a clear data contract defined in `collage_generator/models.py`. The flow of data is as follows:
**Images** -> [Phase 1: Detection] -> **`ImageInfo`** -> [Phase 2: Layout] -> **`Cell`** -> [Phase 3: Cropping] -> **`CropSpec`** -> [Phase 4: Rendering] -> **Output Collage**

### Data Models (`models.py`)

The pipeline relies on these core dataclasses to pass information between phases:

- `KeepZone`: Represents a rectangular bounding box in an image that *must not* be cropped out. Generated during Phase 1.
- `ImageInfo`: Contains metadata about an input image (path, original dimensions) and a list of its associated `KeepZone`s.
- `Cell`: Represents a rectangular partition on the final canvas where an image will be placed. Generated during Phase 2.
- `CropSpec`: Defines exactly how an `ImageInfo` should be cropped to fit into a `Cell`. Generated during Phase 3.

---

## The 4-Phase Pipeline

### Phase 1: Detection (`detector.py`)

**Goal:** Identify salient regions (faces/bodies) in the input images to ensure they are not cut out in the final collage.
**Input:** Directory of raw images.
**Output:** List of `ImageInfo` objects.

**Implementation Details:**
- **Primary Engine:** Uses MediaPipe's `FaceDetector` (BlazeFace full-range model) because it is highly robust and can detect faces even in full-body shots.
- **Fallback Engine:** If MediaPipe fails or is unavailable, it falls back to OpenCV's Haar Cascades (`haarcascade_frontalface_default.xml`).
- **Body Expansion:** By default, it expands the detected face bounding box to estimate a full-body bounding box using standard anthropometric ratios (e.g., body height is ~7.5x face height). This behavior can be disabled via the `--face-only` flag.
- **Padding:** Keeps zones are padded so crops aren't uncomfortably tight around subjects' heads.

### Phase 2: Layout (`layout.py`)

**Goal:** Partition the 5:6 canvas into non-overlapping rectangles (cells) for each image.
**Input:** List of `ImageInfo` objects, canvas dimensions.
**Output:** List of `Cell` objects.

**Implementation Details:**
- **Treemap Algorithm:** Uses the `squarify` library to generate a squarified treemap. This ensures 100% canvas coverage with zero wasted space and produces cells that are as close to square as possible.
- **Weight Strategies:**
  - `equal`: Every image gets an equal slice of the canvas.
  - `faces`: Images with more detected faces get larger cells.
  - `resolution`: Higher resolution images get larger cells.
- **Hero Layout:** If the `--hero` flag is passed, the tool searches for an image with "hero" in its filename. This image is placed in the center (taking up a configurable percentage of the canvas via `--hero-scale`), and the remaining images are packed around it using the squarify algorithm on the remaining border areas.

### Phase 3: Cropping (`cropper.py`)

**Goal:** Compute the optimal crop rectangle for each image so it fits its assigned cell without cutting off any `KeepZone`.
**Input:** `ImageInfo` and `Cell` pairs.
**Output:** List of `CropSpec` objects.

**Implementation Details:**
- The algorithm uses closed-form geometry to calculate the largest possible crop window matching the cell's aspect ratio.
- It calculates an "envelope" (a bounding box containing all `KeepZone`s for an image).
- It positions the crop window to encompass the envelope.
- **Top Alignment:** If the desired crop window is vertically too short to fit the entire envelope (which often happens when trying to fit a tall body into a wide cell), the logic prioritizes aligning the top of the crop window with the top of the envelope. This ensures that the subject's head is preserved, even if their legs must be cropped.
- It dynamically avoids letterboxing (black bars) by forcing crops when necessary.

### Phase 4: Rendering (`renderer.py`)

**Goal:** Assemble the final image.
**Input:** List of `CropSpec` objects, canvas dimensions.
**Output:** The final saved image file (`.png`, `.jpg`, etc.).

**Implementation Details:**
- Powered by `Pillow` (PIL).
- Crops each image according to its `CropSpec`, resizes it to the target `Cell` dimensions using `Image.LANCZOS` for high-quality downsampling, and composites it onto the canvas.
- **Debug Mode:** If `--debug` is enabled, it generates a secondary image showing red boxes for faces, green boxes for the keep zone envelopes, yellow boxes for the crop windows, and cyan outlines for the cells. This is invaluable for debugging the cropping and layout logic.

---

## Extending the Project

### Adding a New Weight Strategy
1. Open `collage_generator/layout.py`.
2. Add a new value to the `WeightStrategy` Enum.
3. Update `_compute_weights()` to handle the new strategy and calculate weights for the `ImageInfo` list.
4. Open `collage_generator/cli.py` and add the new strategy to the `--weight-strategy` argument choices.

### Tuning the Crop Logic
If you notice images are cropping poorly, look into `collage_generator/cropper.py`. The logic inside `_compute_crop_for_image` handles clamping and envelope containment. The current logic specifically prioritizes aligning to `env_y` (the top of the subject) when the crop window is too small.

## Local Development Setup

1. **Clone the repository.**
2. **Create a virtual environment:** `python3 -m venv venv && source venv/bin/activate`
3. **Install Python dependencies:** `pip install -r requirements.txt`
4. **Install Node.js dependencies:** `cd ui && npm install && cd ..`

### Running the Full Web Stack
To test the web interface locally, you can use the provided bash script to start both the FastAPI backend and the Vite frontend:
```bash
./start.sh
```
This script handles running both services and shutting them down gracefully when you press `Ctrl+C`. The frontend is served at `http://localhost:5173` and the backend at `http://localhost:8000`.

### Running the CLI
To test CLI-specific changes quickly, use the test images provided or add your own, and always generate a debug image to verify the bounding boxes:
```bash
python3 main.py --input_dir ./test_images --output_file output.png --debug
```
