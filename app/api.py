import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.pdf import create_image_marktplaats, create_image_subito

app = FastAPI(title="QR Generator API")

# ======== JSON-модели (старый вариант) ========
class ImageMarktplaats(BaseModel):
    nazvanie: str
    price: float
    photo: str | None
    url: str

class ImageSubito(BaseModel):
    nazvanie: str
    price: float
    photo: str | None
    url: str
    name: str | None = ""
    address: str | None = ""

# ======== JSON эндпоинты ========
@app.post("/generate_image_marktplaats")
async def generate_image_marktplaats_endpoint(req: ImageMarktplaats):
    try:
        data = create_image_marktplaats(req.nazvanie, req.price, req.photo, req.url)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_subito")
async def generate_image_subito_endpoint(req: ImageSubito):
    try:
        data = create_image_subito(req.nazvanie, req.price, req.photo, req.url, req.name or "", req.address or "")
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======== FORM эндпоинты (с загрузкой фото) ========
@app.post("/generate_image_marktplaats_form")
async def generate_image_marktplaats_form(
    nazvanie: str = Form(...),
    price: float = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(None)
):
    """Загрузка фото через Swagger (multipart/form-data) для Marktplaats"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        data = create_image_marktplaats(nazvanie, price, photo_b64, url)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_image_subito_form")
async def generate_image_subito_form(
    nazvanie: str = Form(...),
    price: float = Form(...),
    url: str = Form(...),
    name: str = Form(""),
    address: str = Form(""),
    photo: UploadFile = File(None)
):
    """Загрузка фото через Swagger (multipart/form-data) для Subito"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        data = create_image_subito(nazvanie, price, photo_b64, url, name, address)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
