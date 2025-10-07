from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, Header
from fastapi.responses import FileResponse
import tempfile
import shutil
import os

from app.services.qr_local import generate_qr
from app.services.pdf import create_pdf
from app.services.apikey import get_all_keys  # ← добавим импорт

app = FastAPI(title="QR Generator API")


# ✅ Проверка API-ключа из заголовка
async def validate_api_key(x_api_key: str = Header(...)):
    keys = get_all_keys()
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@app.post("/generate_markrplaats/")
async def generate_pdf_from_form(
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(...),
    api_key: str = Depends(validate_api_key)  # 👈 вот тут проверяется ключ
):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Сохраняем фото
            photo_path = os.path.join(tmp_dir, photo.filename)
            with open(photo_path, "wb") as f:
                shutil.copyfileobj(photo.file, f)

            # Генерируем QR-код
            qr_path = generate_qr(url, temp_dir=tmp_dir)

            # Создаем PDF
            pdf_path, _, _ = create_pdf(
                nazvanie=title,
                price=price,
                photo_path=photo_path,
                url=url
            )

            # Возвращаем PDF
            return FileResponse(
                path=pdf_path,
                media_type="application/pdf",
                filename=os.path.basename(pdf_path)
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")

# Эндпоинт для генерации изображения
@app.post("/generate_subito")
async def generate_pdf_from_form(
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(...),
    api_key: str = Depends(validate_api_key)
):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Сохраняем фото
            photo_path = os.path.join(tmp_dir, photo.filename)
            with open(photo_path, "wb") as f:
                shutil.copyfileobj(photo.file, f)

            # Генерируем QR-код
            qr_path = generate_qr(url, temp_dir=tmp_dir)

            # Создаем PDF
            pdf_path, _, _ = create_pdf(
                nazvanie=title,
                price=price,
                photo_path=photo_path,
                url=url
            )

            # Возвращаем PDF
            return FileResponse(
                path=pdf_path,
                media_type="application/pdf",
                filename=os.path.basename(pdf_path)
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
