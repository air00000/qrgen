import base64
import os
import shutil
import tempfile
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.services.apikey import get_all_keys  # ← добавим импорт
from app.services.pdf import create_pdf
from app.services.subito import create_subito_image
from app.utils.io import cleanup_paths

app = FastAPI(title="QR Generator API")


# ✅ Проверка API-ключа из заголовка
async def validate_api_key(x_api_key: str = Header(...)):
    keys = get_all_keys()
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@app.post("/generate/")
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


class SubitoPayload(BaseModel):
    title: str
    price: float
    url: str
    name: str | None = ""
    address: str | None = ""
    photo_base64: str | None = None


@app.post("/generate/subito/")
async def generate_subito_image(payload: SubitoPayload, api_key: str = Depends(validate_api_key)):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            photo_path = None
            processed_photo = qr_path = image_path = None
            try:
                if payload.photo_base64:
                    photo_path = os.path.join(tmp_dir, f"photo_{uuid.uuid4()}.png")
                    with open(photo_path, "wb") as f:
                        f.write(base64.b64decode(payload.photo_base64))

                image_path, processed_photo, qr_path = create_subito_image(
                    payload.title,
                    payload.price,
                    payload.url,
                    name=payload.name or "",
                    address=payload.address or "",
                    photo_path=photo_path,
                    temp_dir=tmp_dir,
                )

                with open(image_path, "rb") as f:
                    data = f.read()

                return Response(content=data, media_type="image/png")
            finally:
                cleanup_paths(photo_path, processed_photo, qr_path, image_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
