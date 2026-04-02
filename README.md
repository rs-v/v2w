# v2w – Screenshot to Word

> 截图识别公式等转 Word  
> A cloud service that converts screenshots (containing text and mathematical formulas) into Microsoft Word (`.docx`) documents.

---

## Features

| Capability | Technology |
|---|---|
| Text recognition (OCR) | [EasyOCR](https://github.com/JaidedAI/EasyOCR) – supports Chinese & English out of the box |
| Formula recognition | [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR) – LaTeX OCR |
| Formula embedding | [latex2mathml](https://github.com/roniemartinez/latex2mathml) + custom MathML→OMML converter – editable OMML equations (MathType-compatible) |
| Word generation | [python-docx](https://python-docx.readthedocs.io/) |
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

The web interface provides:
- **Drag-and-drop** file upload
- **Image preview** before conversion
- **Progress tracking** during conversion
- **Automatic download** of the generated Word document

Simply upload a screenshot containing text and/or mathematical formulas, and the system will automatically convert it to an editable Word document.

---

## API

### `POST /api/v1/convert`

Upload a screenshot and receive a Word document.

**Request** – `multipart/form-data`

| Field | Type | Description |
|---|---|---|
| `file` | `UploadFile` | Image file (PNG / JPEG / WebP / BMP / TIFF) |

**Response** – `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

The response body is the `.docx` file ready for download.

**Example (cURL)**

```bash
curl -X POST http://localhost:8000/api/v1/convert \
     -F "file=@screenshot.png;type=image/png" \
     --output result.docx
```

**Example (Python `requests`)**

```python
import requests

with open("screenshot.png", "rb") as f:
    resp = requests.post(
        "http://localhost:8000/api/v1/convert",
        files={"file": ("screenshot.png", f, "image/png")},
    )

with open("result.docx", "wb") as out:
    out.write(resp.content)
```

### `GET /api/v1/health`

Returns service health and component information.

```json
{
  "status": "ok",
  "version": "1.0.0",
  "services": {
    "ocr": "easyocr",
    "formula": "pix2tex",
    "word": "python-docx"
  }
}
```

---

## How it Works

```
Screenshot image
      │
      ▼
 ┌────────────┐
 │  EasyOCR   │  ──►  Text blocks (paragraphs)
 └────────────┘
      │
      ▼  (math-symbol heuristic)
 ┌────────────┐
 │  pix2tex   │  ──►  LaTeX string
 └────────────┘
      │
      ▼  (LaTeX → MathML → OMML)
 ┌────────────┐
 │ python-docx│  ──►  .docx with editable equations
 └────────────┘
```

1. The uploaded image is passed through **EasyOCR** to detect all text blocks (bounding boxes included).
2. Each block is checked with a heuristic (ratio of Greek / mathematical Unicode characters).
3. Blocks that look like formulas are cropped to their bounding box and re-processed with **pix2tex** to obtain a LaTeX string.
4. LaTeX strings are converted to **OMML** (Office Math Markup Language) via `latex2mathml` (LaTeX→MathML) and a custom lxml-based MathML→OMML converter, then embedded as **native editable equations** in the Word document — fully compatible with Word's built-in equation editor and **MathType**.
5. The final `.docx` is streamed back to the client.

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
│   ├── main.py                  # FastAPI app & CORS setup
│   ├── api/
│   │   └── routes.py            # API endpoints
│   ├── services/
│   │   ├── ocr.py               # EasyOCR text recognition
│   │   ├── formula.py           # pix2tex formula recognition
│   │   ├── image_processor.py   # Orchestration pipeline
│   │   └── word_gen.py          # python-docx Word generation
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
