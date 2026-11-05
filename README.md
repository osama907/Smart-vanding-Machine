# AI-Powered Sports Nutrition Vending Assistant

A FastAPI application for gym users, runners, walkers, and other active people. It recommends protein supplements and vitamins from a structured sports-nutrition catalog based on the user's stated activity, goal, dietary preference, allergies, and caffeine sensitivity.

The recommendation flow retrieves in-stock products from the nutrition database, ranks them against the user's context and product tags, filters known allergens and dietary constraints, and returns catalog-grounded match reasons. It does not diagnose conditions or prescribe supplement doses.

## Features

- Typed recommendation requests for gym, running, walking, and other activities.
- Retrieval-based recommendations from an editable, structured nutrition database.
- Product facts include category, serving label, protein/caffeine content, activity and goal tags, allergens, warnings, stock, and price.
- Optional local WAV transcription and optional local image analysis.
- Purchase endpoint with an atomic stock decrement and purchase history.
- Recommendation history and interactive OpenAPI docs.
- SQLite persistence with a sample protein, hydration, performance, and vitamin catalog.

Image and voice uploads are processed locally when their optional models are configured and are not retained after processing. Image processing does not perform face recognition or identify people. Image recommendations use the local model's detected product labels together with profile fields supplied in the request.

## Run on Windows

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn vending_machine.main:app --reload
```

Open `http://127.0.0.1:8000/docs` to explore and try the API. The SQLite database is created at `data/sports_nutrition.db`. Set `VENDING_DATABASE_PATH` to select another database file.

## Text recommendation

`POST /api/v1/recommendations/text`

```json
{
  "message": "I run several times a week and want help with hydration and recovery",
  "activity": "running",
  "goal": "recovery",
  "dietary_preference": "vegan",
  "allergies": [],
  "caffeine_sensitive": true
}
```

The response contains the inferred activity and goal, up to three in-stock catalog matches, match reasons, product facts, and a safety notice. The allergy list is used to exclude products whose catalog allergens match the supplied values.

## Voice recommendation (optional)

Voice requests use local `faster-whisper` transcription; audio is not sent to an external service.

```powershell
python -m pip install -r requirements-voice.txt
python -m uvicorn vending_machine.main:app --reload
```

Send a WAV file as multipart form data to `POST /api/v1/recommendations/voice`. Set `WHISPER_MODEL_SIZE` to a faster-whisper model size such as `tiny`, `base`, or `small` (default: `base`). Model files may download the first time faster-whisper is run.

## Image recommendation (optional)

Install the optional computer-vision requirements and configure local YOLO weights trained for supplement/product labels:

```powershell
python -m pip install -r requirements-vision.txt
$env:VISION_MODEL_PATH = "C:\models\sports-products.pt"
python -m uvicorn vending_machine.main:app --reload
```

Send a JPEG/PNG as `image` multipart form data to `POST /api/v1/recommendations/image`. Optional form fields are `activity`, `goal`, `dietary_preference`, comma-separated `allergies`, and `caffeine_sensitive`. Without model weights, this endpoint responds with HTTP 503; text recommendations remain available.

## API endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Check API and database |
| `GET` | `/api/v1/supplements` | Search/filter the supplement catalog |
| `POST` | `/api/v1/supplements` | Add a catalog supplement |
| `POST` | `/api/v1/recommendations/text` | Recommend from typed context |
| `POST` | `/api/v1/recommendations/voice` | Transcribe WAV locally, then recommend |
| `POST` | `/api/v1/recommendations/image` | Analyze JPEG/PNG locally, then recommend |
| `GET` | `/api/v1/recommendations/history` | View recent recommendation activity |
| `POST` | `/api/v1/purchases` | Buy a catalog item and decrement stock |
| `GET` | `/api/v1/purchases` | View recent purchases |

### Purchase example

`POST /api/v1/purchases`

```json
{
  "product_id": 1,
  "quantity": 1
}
```

## Safety and scope

Recommendations are general product information, not medical, nutritional, or personalized dosage advice. Follow each product's label and seek qualified professional guidance for medical conditions, medication interactions, pregnancy, allergies, or uncertainty. Seed catalog facts are example data and should be checked against actual manufacturer labels before deployment. This demo does not include payment processing or authentication for catalog administration.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
```
