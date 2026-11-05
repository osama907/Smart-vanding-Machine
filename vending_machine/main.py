import json
import os
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from vending_machine.database import (
    get_connection,
    initialize_database,
    serialize_supplement,
)
from vending_machine.recommendations import retrieve_recommendations
from vending_machine.schemas import PurchaseRequest, RecommendationRequest, SupplementCreate

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_AUDIO_BYTES = 25 * 1024 * 1024
IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="AI Sports Nutrition Vending Assistant",
    description=(
        "Fitness supplement recommendations grounded in a structured nutrition catalog. "
        "Accepts typed context and optional local voice or image-model processing."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_image(data: bytes) -> str:
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be 10 MB or smaller.")
    suffix = next((suffix for signature, suffix in IMAGE_SIGNATURES.items() if data.startswith(signature)), None)
    if suffix is None:
        raise HTTPException(status_code=415, detail="Upload a valid JPEG or PNG image.")
    return suffix


def _recommend(request: RecommendationRequest, input_mode: str, extra_context: str = "") -> dict:
    with get_connection() as connection:
        return retrieve_recommendations(connection, request, input_mode, extra_context)


def _load_vision_labels(image_bytes: bytes, suffix: str) -> list[str]:
    model_path = os.getenv("VISION_MODEL_PATH", "").strip()
    if not model_path:
        raise HTTPException(
            status_code=503,
            detail=(
                "Image analysis is optional and is not configured. Set VISION_MODEL_PATH "
                "to local YOLO weights trained for your supplement or sports-product labels."
            ),
        )
    if not Path(model_path).is_file():
        raise HTTPException(status_code=503, detail="Configured local vision model weights were not found.")
    try:
        from ultralytics import YOLO
    except ImportError as error:
        raise HTTPException(
            status_code=503,
            detail="Computer-vision dependencies are missing. Install requirements-vision.txt.",
        ) from error

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as image_file:
            image_file.write(image_bytes)
            temp_path = image_file.name
        results = _get_vision_model(model_path).predict(source=temp_path, verbose=False)
        labels = []
        for result in results:
            names = result.names
            for box in result.boxes:
                label = str(names[int(box.cls.item())])
                if label.casefold() not in ("person", "face") and label not in labels:
                    labels.append(label)
        return labels
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Local image analysis failed: {error}") from error
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@lru_cache(maxsize=2)
def _get_vision_model(model_path: str):
    from ultralytics import YOLO

    return YOLO(model_path)


def _transcribe_audio(audio_bytes: bytes) -> str:
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 25 MB or smaller.")
    if not audio_bytes.startswith(b"RIFF") or audio_bytes[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="Upload a valid WAV audio file.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise HTTPException(
            status_code=503,
            detail="Voice support is optional. Install requirements-voice.txt to enable local transcription.",
        ) from error

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_file.write(audio_bytes)
            temp_path = audio_file.name
        model = WhisperModel(os.getenv("WHISPER_MODEL_SIZE", "base"), device="cpu", compute_type="int8")
        segments, _ = model.transcribe(temp_path, vad_filter=True)
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        if not transcript:
            raise HTTPException(status_code=422, detail="No speech could be transcribed from this audio.")
        return transcript
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Local speech transcription failed: {error}") from error
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@app.get("/", tags=["system"])
def root():
    return {
        "name": app.title,
        "version": app.version,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


@app.get("/api/v1/health", tags=["system"])
def health():
    with get_connection() as connection:
        connection.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}


@app.get("/api/v1/supplements", tags=["nutrition catalog"])
def list_supplements(
    search: Optional[str] = Query(default=None, max_length=120),
    category: Optional[str] = Query(default=None, max_length=80),
    in_stock: bool = True,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    filters = ["stock > 0"] if in_stock else []
    parameters: list = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append("(name LIKE ? OR description LIKE ? OR category LIKE ?)")
        parameters.extend([pattern, pattern, pattern])
    if category:
        filters.append("category = ?")
        parameters.append(category.strip())
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    with get_connection() as connection:
        rows = connection.execute(
            f"SELECT * FROM supplements {where_clause} ORDER BY category, name LIMIT ? OFFSET ?",
            [*parameters, limit, offset],
        ).fetchall()
    return [serialize_supplement(row) for row in rows]


@app.post("/api/v1/supplements", status_code=201, tags=["nutrition catalog"])
def create_supplement(payload: SupplementCreate):
    values = payload.model_dump()
    values["name"] = values["name"].strip()
    if not values["name"]:
        raise HTTPException(status_code=422, detail="Supplement name cannot be blank.")
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO supplements (
                    name, category, description, serving_size, protein_g, caffeine_mg,
                    activity_tags, goal_tags, dietary_tags, allergens, warnings, price, stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["name"], values["category"].strip(), values["description"].strip(),
                    values["serving_size"].strip(), values["protein_g"], values["caffeine_mg"],
                    *[
                        json.dumps(values[field])
                        for field in ("activity_tags", "goal_tags", "dietary_tags", "allergens", "warnings")
                    ],
                    values["price"], values["stock"],
                ),
            )
            row = connection.execute(
                "SELECT * FROM supplements WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="A supplement with this name already exists.") from error
    return serialize_supplement(row)


@app.post("/api/v1/recommendations/text", tags=["recommendations"])
def recommend_from_text(request: RecommendationRequest):
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Describe your activity or fitness goal.")
    return _recommend(request, "text")


@app.post("/api/v1/recommendations/voice", tags=["recommendations"])
async def recommend_from_voice(audio: UploadFile = File(...)):
    audio_bytes = await audio.read(MAX_AUDIO_BYTES + 1)
    transcript = _transcribe_audio(audio_bytes)
    request = RecommendationRequest(message=transcript)
    result = _recommend(request, "voice")
    return {"transcript": transcript, **result}


@app.post("/api/v1/recommendations/image", tags=["recommendations"])
async def recommend_from_image(
    image: UploadFile = File(...),
    activity: Optional[str] = Form(default=None, max_length=80),
    goal: Optional[str] = Form(default=None, max_length=80),
    dietary_preference: Optional[str] = Form(default=None, max_length=80),
    allergies: str = Form(default="", max_length=500),
    caffeine_sensitive: bool = Form(default=False),
):
    image_bytes = await image.read(MAX_IMAGE_BYTES + 1)
    suffix = _validate_image(image_bytes)
    labels = _load_vision_labels(image_bytes, suffix)
    message = " ".join(part for part in (activity, goal, *labels) if part)
    request = RecommendationRequest(
        message=message or "general fitness",
        activity=activity,
        goal=goal,
        dietary_preference=dietary_preference,
        allergies=[item.strip() for item in allergies.split(",") if item.strip()],
        caffeine_sensitive=caffeine_sensitive,
    )
    result = _recommend(request, "image", " ".join(labels))
    result["detected_labels"] = labels
    return result


@app.post("/api/v1/purchases", status_code=201, tags=["purchases"])
def purchase_supplement(payload: PurchaseRequest):
    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        supplement = connection.execute(
            "SELECT id, name, price, stock FROM supplements WHERE id = ?", (payload.product_id,)
        ).fetchone()
        if supplement is None:
            raise HTTPException(status_code=404, detail="Supplement not found.")
        if supplement["stock"] < payload.quantity:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock. Only {supplement['stock']} item(s) are available.",
            )
        connection.execute(
            "UPDATE supplements SET stock = stock - ? WHERE id = ?",
            (payload.quantity, payload.product_id),
        )
        total = round(supplement["price"] * payload.quantity, 2)
        cursor = connection.execute(
            """
            INSERT INTO purchases (supplement_id, supplement_name, quantity, unit_price, total)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.product_id,
                supplement["name"],
                payload.quantity,
                supplement["price"],
                total,
            ),
        )
    return {
        "purchase_id": cursor.lastrowid,
        "product_id": payload.product_id,
        "product_name": supplement["name"],
        "quantity": payload.quantity,
        "total": total,
        "remaining_stock": supplement["stock"] - payload.quantity,
    }


@app.get("/api/v1/purchases", tags=["purchases"])
def purchase_history(limit: int = Query(default=50, ge=1, le=200)):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM purchases ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


@app.get("/api/v1/recommendations/history", tags=["recommendations"])
def recommendation_history(limit: int = Query(default=50, ge=1, le=200)):
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM recommendation_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
