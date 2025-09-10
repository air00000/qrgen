# app/api.py
from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Локальный импорт конфигурации и бизнес-логики
try:
    from app.config import CFG  # type: ignore
    from app.services.pdf import create_pdf  # type: ignore
    from app.services.keystore import contains as key_contains  # type: ignore
except Exception:
    # На случай альтернативной схемы импортов
    from .config import CFG  # type: ignore
    from .services.pdf import create_pdf  # type: ignore
    from .services.keystore import contains as key_contains  # type: ignore


app = FastAPI(
    title="QRGen API",
    version="2.0.0",
    description="HTTP API для генерации PDF с QR-кодом (QR генерируется внутри сервиса)."
)

# CORS — по умолчанию открыт; при необходимости сузить доменами
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def require_api_key():
    """
    Зависимость FastAPI: проверка заголовка X-API-Key по общему пулу ключей.
    Ключи управляются админом через бота и хранятся в services/keystore.
    """
    async def checker(x_api_key: Optional[str] = Header(default=None)):
        if not x_api_key or not key_contains(x_api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")
    return checker


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate", dependencies=[Depends(require_api_key())])
async def generate(
    nazvanie: str = Form(..., description="Название товара"),
    price: str = Form(..., description="Цена (строкой, как в боте)"),
    url: str = Form(..., description="URL для QR"),
    photo: UploadFile = File(..., description="Фото товара (jpeg/png)"),
    download: bool = Form(False, description="Если true — отправить как attachment"),
):
    """
    Принимает multipart/form-data и сразу отдаёт PDF-файл.
    """
    if not URL_RE.match(url):
        raise HTTPException(status_code=422, detail="url должен начинаться с http:// или https://")

    # Сохраняем присланное фото во временный файл
    suffix = Path(photo.filename or "").suffix or ".jpg"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await photo.read()
            if not content:
                raise HTTPException(status_code=400, detail="Файл фото пустой")
            tmp.write(content)
            photo_path = Path(tmp.name)

        # Основная бизнес-логика сборки PDF (сигнатура сохранена)
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
        raise HTTPException(status_code=500, detail=f"Generation failed: {e}")
    finally:
        # Удаляем временный файл с исходным фото
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
    Возвращает JSON с путями к файлам на диске (если у вас есть статика/файловое хранилище).
    Для большинства кейсов лучше пользоваться /generate, который отдаёт PDF напрямую.
    """
    if not URL_RE.match(url):
        raise HTTPException(status_code=422, detail="url должен начинаться с http:// или https://")

    suffix = Path(photo.filename or "").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await photo.read()
        if not content:
            raise HTTPException(status_code=400, detail="Файл фото пустой")
        tmp.write(content)
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
