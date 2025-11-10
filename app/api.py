# app/api.py
import base64
import io

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from app.services.pdf import create_image_marktplaats, create_image_subito, create_image_wallapop
from app.services.apikey import validate_key, get_key_name

app = FastAPI(title="QR Generator API")

# ======== Зависимость для проверки API ключа ========
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Please provide X-API-Key header"
        )

    if not validate_key(x_api_key):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return get_key_name(x_api_key)

# ======== JSON-модели ========
class ImageMarktplaats(BaseModel):
    nazvanie: str
    price: float
    photo: str | None = None
    url: str

class ImageSubito(BaseModel):
    nazvanie: str
    price: float
    photo: str | None = None
    url: str
    name: str = ""
    address: str = ""

class ImageWallapop(BaseModel):
    lang: str
    nazvanie: str
    price: float
    photo: str | None = None

# ======== Защищенные эндпоинты ========
@app.post("/generate_image_marktplaats")
async def generate_image_marktplaats_endpoint(
        req: ImageMarktplaats,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Marktplaats (JSON)"""
    try:
        image_data = create_image_marktplaats(req.nazvanie, req.price, req.photo, req.url)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_subito")
async def generate_image_subito_endpoint(
        req: ImageSubito,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Subito (JSON)"""
    try:
        image_data = create_image_subito(req.nazvanie, req.price, req.photo, req.url, req.name, req.address)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop")
async def generate_image_wallapop_endpoint(
        req: ImageWallapop,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop (JSON)"""
    try:
        image_data = create_image_wallapop(req.lang, req.nazvanie, req.price, req.photo)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_marktplaats_form")
async def generate_image_marktplaats_form(
        nazvanie: str = Form(...),
        price: float = Form(...),
        url: str = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Marktplaats (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_image_marktplaats(nazvanie, price, photo_b64, url)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_subito_form")
async def generate_image_subito_form(
        nazvanie: str = Form(...),
        price: float = Form(...),
        url: str = Form(...),
        name: str = Form(""),
        address: str = Form(""),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Subito (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_image_subito(nazvanie, price, photo_b64, url, name, address)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_form")
async def generate_image_wallapop_form(
        lang: str = Form(...),
        nazvanie: str = Form(...),
        price: float = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_image_wallapop(lang, nazvanie, price, photo_b64)
        return Response(content=image_data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def api_status(key_name: str = Depends(verify_api_key)):
    """Проверка статуса API"""
    return {
        "status": "active",
        "key_name": key_name,
        "message": "API key is valid"
    }