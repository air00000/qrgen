import base64
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.pdf import create_image_marktplaats, create_image_subito
from app.services.apikey import verify_key

app = FastAPI(title="QR Generator API")


def api_key_auth(x_api_key: str = Header(default=None, alias="X-API-Key")):
    """Авторизация по API ключу через заголовок X-API-Key"""
    if not x_api_key or not verify_key(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


# ======== JSON-модели ========
class ImageMarktplaats(BaseModel):
    nazvanie: str
    price: float
    photo: str
    url: str


class ImageSubito(BaseModel):
    nazvanie: str
    price: float
    photo: str
    url: str
    name: str = ""
    address: str = ""


# ======== JSON эндпоинты ========
@app.post("/generate_image_marktplaats", dependencies=[Depends(api_key_auth)])
async def generate_image_marktplaats_endpoint(req: ImageMarktplaats):
    try:
        data = create_image_marktplaats(req.nazvanie, req.price, req.photo, req.url)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_image_subito", dependencies=[Depends(api_key_auth)])
async def generate_image_subito_endpoint(req: ImageSubito):
    try:
        data = create_image_subito(
            req.nazvanie, req.price, req.photo, req.url, req.name or "", req.address or ""
        )
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ======== FORM эндпоинты ========
@app.post("/generate_image_marktplaats_form", dependencies=[Depends(api_key_auth)])
async def generate_image_marktplaats_form(
    nazvanie: str = Form(...),
    price: float = Form(...),
    url: str = Form(...),
    photo: UploadFile = File(None)
):
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        data = create_image_marktplaats(nazvanie, price, photo_b64, url)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_image_subito_form", dependencies=[Depends(api_key_auth)])
async def generate_image_subito_form(
    nazvanie: str = Form(...),
    price: float = Form(...),
    url: str = Form(...),
    name: str = Form(""),
    address: str = Form(""),
    photo: UploadFile = File(None)
):
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        data = create_image_subito(nazvanie, price, photo_b64, url, name, address)
        return Response(content=data, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
