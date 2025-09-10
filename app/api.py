# app/api.py
from __future__ import annotations

import io
import re
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    # текущий код проекта
    from .config import CFG  # type: ignore
    from .services.pdf import create_pdf  # type: ignore
except Exception as e:
    # на случай запуска как модуля без пакета
    from app.config import CFG  # type: ignore
    from app.services.pdf import create_pdf  # type: ignore

app = FastAPI(
    title="QRGen API",
    version="1.0.0",
    description="HTTP API, дублирующее функционал бота: генерирует PDF-снимок с QR-кодом."
)

# По желанию: открыть CORS (можно сузить доменами)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ← при необходимости заменить на свои домены
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Простейшая токен-аутентификация через заголовок X-API-Key (опционально)
def require_api_key(x_api_key: Optional[str] = None):
    # Задайте API_KEY в .env/.config (например, API_AUTH_TOKEN)
    api_key_env = getattr(CFG, "API_AUTH_TOKEN", None)
    if api_key_env:
        from fastapi import Header
        def checker(x_api_key: Optional[str] = Header(None)):
            if not x_api_key or x_api_key != api_key_env:
                raise HTTPException(status_code=401, detail="Invalid API key")
        return checker
    # если ключ не задан — не проверяем
    return lambda: None


URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", response_class=FileResponse, dependencies=[Depends(require_api_key())])
async def generate(
    nazvanie: str = Form(..., description="Название"),
    price: str = Form(..., description="Цена (строкой, как в боте)"),
    url: str = Form(..., description="URL для QR"),
    photo: UploadFile = File(..., description="Фото для вставки"),
    download: bool = Form(False, description="Если true — принудительно скачивать файл"),
):
    # Валидация входных данных в стиле бота
    if not URL_RE.match(url):
        raise HTTPException(status_code=422, detail="url должен начинаться с http:// или https://")

    # Временный файл под фото
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(photo.filename or "").suffix or ".jpg") as tmp:
            content = await photo.read()
            if not content:
                raise HTTPException(status_code=400, detail="Файл фото пустой")
            tmp.write(content)
            photo_path = Path(tmp.name)

        # Вызов существующей бизнес-логики проекта:
        # create_pdf(nazvanie, price, photo_path, url) -> (pdf_path, processed_photo_path, qr_path)
        pdf_path, processed_photo_path, qr_path = create_pdf(nazvanie, price, str(photo_path), url)

        filename = f"qr_{Path(processed_photo_path).stem or 'result'}.pdf"
        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=filename,
            headers=headers
        )
    except HTTPException:
        raise
    except Exception as e:
        # Пробрасываем причину в ответ (для отладки можно вернуть trace, но тут коротко)
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    finally:
        # Чистка временного файла фото
        try:
            if 'photo_path' in locals() and photo_path.exists():
                photo_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.post("/generate/json", dependencies=[Depends(require_api_key())])
async def generate_json(
    nazvanie: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(...),
):
    """
    Вариант, который возвращает JSON с путями (если вы хотите потом забрать файл отдельным запросом статики).
    По умолчанию лучше использовать /generate, который сразу отдаёт PDF.
    """
    if not URL_RE.match(url):
        raise HTTPException(status_code=422, detail="url должен начинаться с http:// или https://")

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(photo.filename or "").suffix or ".jpg") as tmp:
        tmp.write(await photo.read())
        photo_path = Path(tmp.name)

    try:
        pdf_path, processed_photo_path, qr_path = create_pdf(nazvanie, price, str(photo_path), url)
        return JSONResponse({
            "pdf_path": str(pdf_path),
            "photo_path": str(processed_photo_path),
            "qr_path": str(qr_path),
        })
    finally:
        try:
            photo_path.unlink(missing_ok=True)
        except Exception:
            pass
