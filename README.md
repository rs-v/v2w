# v2w – Screenshot to Word

> 截图识别公式等转 Word  
> A cloud service that converts screenshots (containing text and mathematical formulas) into Microsoft Word (`.docx`) documents.

---

## Features

| Capability | Technology |
|---|---|
| Text recognition (OCR) | [EasyOCR](https://github.com/JaidedAI/EasyOCR) – supports Chinese & English out of the box |
| Formula recognition | [pix2tex](https://github.com/lukas-blecher/LaTeX-OCR) – LaTeX OCR |
| Word generation | [python-docx](https://python-docx.readthedocs.io/) |
| REST API | [FastAPI](https://fastapi.tiangolo.com/) |
| Containerisation | Docker / docker-compose |

---

## Quick Start

### Run with Docker (recommended)

```bash
docker compose up --build
```

The service will be available at <http://localhost:8000>.  
Interactive API docs: <http://localhost:8000/docs>

### Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

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
 │  pix2tex   │  ──►  LaTeX string → rendered as inline image
 └────────────┘
      │
      ▼
 ┌────────────┐
 │ python-docx│  ──►  .docx file returned to client
 └────────────┘
```

1. The uploaded image is passed through **EasyOCR** to detect all text blocks.
2. Each block is checked with a heuristic (ratio of Greek / mathematical Unicode characters).
3. Blocks that look like formulas are re-processed with **pix2tex** to obtain a LaTeX representation.
4. Formulas are rendered to PNG (via Matplotlib) and embedded as pictures in the document alongside the raw LaTeX source.
5. The final `.docx` is streamed back to the client.

---

## Development

### Run tests

```bash
pip install -r requirements.txt
pytest
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
