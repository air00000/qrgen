from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends, Header, BackgroundTasks
from fastapi.responses import FileResponse
import tempfile
import shutil
import os

from app.services.apikey import get_all_keys  # ← добавим импорт
from app.services.render import generate_listing_image
from app.utils.io import cleanup_paths

app = FastAPI(title="QR Generator API")


# ✅ Проверка API-ключа из заголовка
async def validate_api_key(x_api_key: str = Header(...)):
    keys = get_all_keys()
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@app.post("/generate/")
async def generate_listing(
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(...),
    template: str = Form("marktplaats"),
    name: str = Form(""),
    address: str = Form(""),
    api_key: str = Depends(validate_api_key)  # 👈 вот тут проверяется ключ
):
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Сохраняем фото
            photo_path = os.path.join(tmp_dir, photo.filename)
            with open(photo_path, "wb") as f:
                shutil.copyfileobj(photo.file, f)

            result = generate_listing_image(
                template=template,
                nazvanie=title,
                price=price,
                photo_path=photo_path,
                url=url,
                name=name,
                address=address,
            )

            background = BackgroundTasks()
            background.add_task(cleanup_paths, result.processed_photo_path, result.qr_path, result.path)

            return FileResponse(
                path=result.path,
                media_type="image/png",
                filename=os.path.basename(result.path),
                background=background,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
