from fastapi import FastAPI, HTTPException, Response, UploadFile, File, Form
from typing import Optional
import os, uuid

from app.services.pdf import create_pdf  # та же функция, что использует бот
from app.config import CFG

app = FastAPI(title="QR PDF API (reuse bot pipeline)", version="1.0")

def _normalize_price(p: str) -> str:
    # бот сам добавляет "€" внутри create_pdf → убираем любые евро из входа
    p = (p or "").strip()
    p = p.replace("€", "").replace("EUR", "").replace("eur", "")
    return p.strip()

def _normalize_url(u: str) -> str:
    u = (u or "").strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u

@app.post("/v1/qr/pdf", response_class=Response, summary="PDF как у бота (Figma+ReportLab, QR локально)")
async def pdf_endpoint(
    title: str = Form(..., description="Название товара"),
    price: str = Form(..., description="Цена (без валюты, бот добавит €)"),
    qr_url: str = Form(..., description="Куда ведёт QR"),
    photo: Optional[UploadFile] = File(None, description="Скриншот/фото товара (опционально)"),
):
    os.makedirs(CFG.TEMP_DIR, exist_ok=True)

    # 1) нормализация входа как в боте
    price_in = _normalize_price(price)
    url_in = _normalize_url(qr_url)

    # 2) сохранить фото во временный файл (бот тоже работает с путём к файлу)
    photo_path = None
    if photo is not None:
        ext = os.path.splitext(photo.filename or "")[1] or ".jpg"
        photo_path = os.path.join(CFG.TEMP_DIR, f"upload_{uuid.uuid4()}{ext}")
        try:
            with open(photo_path, "wb") as f:
                f.write(await photo.read())
        except Exception:
            photo_path = None  # продолжим без фото

    # 3) вызвать РОВНО тот же пайплайн, что у бота
    pdf_path = None
    processed_photo = None
    qr_path = None
    try:
        pdf_path, processed_photo, qr_path = create_pdf(
            nazvanie=title.strip(),
            price=price_in,
            photo_path=photo_path,
            url=url_in,
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": 'inline; filename="MARKTPLAATS.pdf"'},
        )
    except Exception as e:
        raise HTTPException(500, f"render error: {e}")
    finally:
        # 4) подчистка временных файлов — так же, как бот
        for p in (photo_path, processed_photo, qr_path, os.path.join(CFG.TEMP_DIR, "template.png"), pdf_path):
            try:
                if p and os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass

@app.get("/healthz")
def health():
    return {"ok": True}
