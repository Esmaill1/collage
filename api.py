import shutil
import tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
import uuid

from collage_generator.cli import run

app = FastAPI(title="Saliency-Aware Collage API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def cleanup_temp_dir(path: str):
    try:
        shutil.rmtree(path)
    except Exception as e:
        print(f"Error cleaning up {path}: {e}")

@app.post("/api/generate")
async def generate_collage(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    width: int = Form(2500),
    height: int = Form(0),
    padding: int = Form(4),
    bg_color: str = Form("#1a1a1a"),
    face_confidence: float = Form(0.35),
    weight_strategy: str = Form("equal"),
    face_padding: float = Form(0.35),
    face_only: bool = Form(False),
    hero: bool = Form(False),
    hero_scale: float = Form(0.45),
    hero_filenames: List[str] = Form([]),
):
    temp_dir = tempfile.mkdtemp()
    input_dir = Path(temp_dir) / "input"
    input_dir.mkdir()
    
    output_file = Path(temp_dir) / f"collage_{uuid.uuid4().hex[:8]}.png"

    # Parse hero filenames sent from the UI (as repeated form fields)
    hero_names = {name.strip() for name in hero_filenames if name.strip()}


    for file in files:
        original_name = file.filename
        save_name = original_name

        # If this file is designated as hero from the UI, ensure "hero" is in the filename
        # so the CLI's hero-detection logic picks it up.
        if hero_names and original_name in hero_names:
            stem = Path(original_name).stem
            suffix = Path(original_name).suffix
            if "hero" not in stem.lower():
                save_name = f"{stem}_hero{suffix}"

        file_path = input_dir / save_name
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # If hero filenames were designated, enable hero mode automatically
    enable_hero = hero or bool(hero_names)

    argv = [
        "--input_dir", str(input_dir),
        "--output_file", str(output_file),
        "--width", str(width),
        "--height", str(height),
        "--padding", str(padding),
        "--bg-color", bg_color,
        "--face-confidence", str(face_confidence),
        "--weight-strategy", weight_strategy,
        "--face-padding", str(face_padding),
        "--hero-scale", str(hero_scale)
    ]
    if face_only:
        argv.append("--face-only")
    if enable_hero:
        argv.append("--hero")


    exit_code = run(argv)
    
    if exit_code != 0 or not output_file.exists():
        cleanup_temp_dir(temp_dir)
        return {"error": "Failed to generate collage"}

    background_tasks.add_task(cleanup_temp_dir, temp_dir)
    
    return FileResponse(
        path=output_file, 
        filename="collage.png",
        media_type="image/png"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)