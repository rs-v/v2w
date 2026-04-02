# v2w – Formula Recognition

> 公式图片识别 → LaTeX  
> A service that takes an image of a mathematical formula and returns the corresponding LaTeX code, powered by [pix2tex (LaTeX-OCR)](https://github.com/lukas-blecher/LaTeX-OCR).

---

## Features

| Capability | Technology |
|---|---|
| Formula recognition | [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR) – LaTeX OCR |
| REST API | [FastAPI](https://fastapi.tiangolo.com/) |
| Containerisation | Docker / docker-compose |

---

## Quick Start

### Run with Docker (recommended)

```bash
docker compose up --build
```

The service will be available at:
- **Web Interface**: <http://localhost:8000>
- **Interactive API docs**: <http://localhost:8000/docs>

### Run locally

**Using pip:**

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Using uv:**

```bash
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload
```

> **Note (uv users):** Always use `uv run uvicorn …` (not plain `uvicorn …`) so the server runs inside the uv-managed virtual environment where all dependencies are installed.

---

## Usage

### Web Interface

Open your browser and navigate to <http://localhost:8000> to access the web interface.

### API

#### `POST /api/v1/predict`

Upload an image of a mathematical formula and receive the corresponding LaTeX string.

**Request** – `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | `UploadFile` | Formula image (PNG / JPEG / WebP / BMP / TIFF) |

**Response** – `application/json`

```json
{
  "latex": "\\frac{a}{b}",
  "message": "公式识别成功。"
}
```

**Example (cURL)**

```bash
curl -X POST http://localhost:8000/api/v1/predict \
     -F "file=@formula.png;type=image/png"
```

**Example (Python `requests`)**

```python
import requests

with open("formula.png", "rb") as f:
    resp = requests.post(
        "http://localhost:8000/api/v1/predict",
        files={"file": ("formula.png", f, "image/png")},
    )

print(resp.json()["latex"])
```

#### `GET /api/v1/health`

Returns service health information.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "services": {
    "formula": "pix2tex"
  }
}
```

---

## How it Works

```
Formula image
      │
      ▼
 ┌────────────┐
 │  pix2tex   │  ──►  LaTeX string
 └────────────┘
```

The pix2tex model is loaded once at application **startup** (following the same pattern as the pix2tex reference API), so no cold-start latency is incurred on the first request.

---

## Development

### Run tests

**Using pip:**

```bash
pip install -r requirements.txt
pytest
```

**Using uv:**

```bash
uv pip install -r requirements.txt
uv run pytest
```

### Project layout

```
v2w/
├── app/
│   ├── main.py                  # FastAPI app, lifespan startup, CORS
│   ├── api/
│   │   └── routes.py            # API endpoints (/predict, /health)
│   ├── services/
│   │   └── formula.py           # pix2tex formula recognition
│   └── models/
│       └── schemas.py           # Pydantic response models
├── tests/
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## License

MIT
