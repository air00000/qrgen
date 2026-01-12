# app/api.py
import base64
import io

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Header, Depends
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from app.services.pdf import (
    create_image_marktplaats, create_image_subito, create_image_wallapop,
    create_image_wallapop_email, create_image_wallapop_sms, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError
)
from app.services.twodehands import create_2dehands_image, DehandsGenerationError
from app.services.kleize import create_kleize_image, KleizeGenerationError
from app.services.conto import create_conto_image, ContoGenerationError
from app.services.depop import create_depop_image, DepopGenerationError
from app.services.apikey import validate_key, get_key_name
from app.utils.notifications import send_api_notification_sync

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
    title: str
    price: float
    photo: str = None
    url: str

class ImageSubito(BaseModel):
    title: str
    price: float
    photo: str= None
    url: str
    name: str = ""
    address: str = ""

class ImageWallapop(BaseModel):
    lang: str
    title: str
    price: float
    photo: str = None

class ImageWallapopEmail(BaseModel):
    lang: str
    title: str
    price: float
    photo: str = None
    seller_name: str
    seller_photo: str = None

class ImageWallapopSMS(BaseModel):
    lang: str
    title: str
    price: float
    photo: str = None

class Image2dehands(BaseModel):
    """Модель для 2dehands (нидерландский)"""
    title: str
    price: float
    photo: str = None
    url: str

class Image2ememain(BaseModel):
    """Модель для 2ememain (французский)"""
    title: str
    price: float
    photo: str = None
    url: str

class ImageKleize(BaseModel):
    """Модель для Kleize"""
    title: str
    price: float
    photo: str = None
    url: str

class ImageConto(BaseModel):
    """Модель для Conto (Subito Payment)"""
    title: str
    price: float

class ImageDepop(BaseModel):
    """Модель для Depop (AU)"""
    title: str
    price: float
    seller_name: str
    photo: str = None
    avatar: str = None
    url: str

# ======== Защищенные эндпоинты ========
@app.post("/generate_image_marktplaats")
async def generate_image_marktplaats_endpoint(
        req: ImageMarktplaats,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Marktplaats (JSON)"""
    try:
        image_data = create_image_marktplaats(req.title, req.price, req.photo, req.url)
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_subito")
async def generate_image_subito_endpoint(
        req: ImageSubito,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Subito (JSON)"""
    try:
        image_data = create_image_subito(req.title, req.price, req.photo, req.url, req.name, req.address)
        send_api_notification_sync(service="subito", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="subito", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="subito", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop")
async def generate_image_wallapop_endpoint(
        req: ImageWallapop,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop (JSON)"""
    try:
        image_data = create_image_wallapop(req.lang, req.title, req.price, req.photo)
        send_api_notification_sync(service="wallapop", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_email")
async def generate_image_wallapop_email_endpoint(
        req: ImageWallapopEmail,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop Email (JSON)"""
    try:
        image_data = create_image_wallapop_email(req.lang, req.title, req.price, req.photo, req.seller_name, req.seller_photo)
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_sms")
async def generate_image_wallapop_sms_endpoint(
        req: ImageWallapopSMS,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop SMS (JSON)"""
    try:
        image_data = create_image_wallapop_sms(req.lang, req.title, req.price, req.photo)
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_marktplaats_form")
async def generate_image_marktplaats_form(
        title: str = Form(...),
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

        image_data = create_image_marktplaats(title, price, photo_b64, url)
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="marktplaats", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_subito_form")
async def generate_image_subito_form(
        title: str = Form(...),
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

        image_data = create_image_subito(title, price, photo_b64, url, name, address)
        send_api_notification_sync(service="subito", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="subito", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="subito", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_form")
async def generate_image_wallapop_form(
        lang: str = Form(...),
        title: str = Form(...),
        price: float = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_image_wallapop(lang, title, price, photo_b64)
        send_api_notification_sync(service="wallapop", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_email_form")
async def generate_image_wallapop_email_form(
        lang: str = Form(...),
        title: str = Form(...),
        price: float = Form(...),
        seller_name: str = Form(...),
        photo: UploadFile = File(None),
        seller_photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop Email (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        seller_photo_b64 = None
        if seller_photo:
            seller_photo_b64 = base64.b64encode(await seller_photo.read()).decode("utf-8")

        image_data = create_image_wallapop_email(lang, title, price, photo_b64, seller_name, seller_photo_b64)
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop_email", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_wallapop_sms_form")
async def generate_image_wallapop_sms_form(
        lang: str = Form(...),
        title: str = Form(...),
        price: float = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Wallapop SMS (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_image_wallapop_sms(lang, title, price, photo_b64)
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="wallapop_sms", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_2dehands")
async def generate_image_2dehands_endpoint(
        req: Image2dehands,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для 2dehands - нидерландский (JSON)"""
    try:
        image_data = create_2dehands_image(req.title, req.price, req.photo, req.url, "nl")
        send_api_notification_sync(service="2dehands", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DehandsGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="2dehands", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="2dehands", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_2ememain")
async def generate_image_2ememain_endpoint(
        req: Image2ememain,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для 2ememain - французский (JSON)"""
    try:
        image_data = create_2dehands_image(req.title, req.price, req.photo, req.url, "fr")
        send_api_notification_sync(service="2ememain", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DehandsGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="2ememain", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="2ememain", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_2dehands_form")
async def generate_image_2dehands_form(
        title: str = Form(...),
        price: float = Form(...),
        url: str = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для 2dehands - нидерландский (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_2dehands_image(title, price, photo_b64, url, "nl")
        send_api_notification_sync(service="2dehands", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DehandsGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="2dehands", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="2dehands", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_2ememain_form")
async def generate_image_2ememain_form(
        title: str = Form(...),
        price: float = Form(...),
        url: str = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для 2ememain - французский (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_2dehands_image(title, price, photo_b64, url, "fr")
        send_api_notification_sync(service="2ememain", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DehandsGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="2ememain", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="2ememain", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_image_kleize")
async def generate_image_kleize_endpoint(
        req: ImageKleize,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Kleize (JSON)"""
    try:
        image_data = create_kleize_image(req.title, req.price, req.photo, req.url)
        send_api_notification_sync(service="kleize", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (KleizeGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="kleize", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="kleize", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_kleize_form")
async def generate_image_kleize_form(
        title: str = Form(...),
        price: float = Form(...),
        url: str = Form(...),
        photo: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Kleize (Form Data)"""
    try:
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")

        image_data = create_kleize_image(title, price, photo_b64, url)
        send_api_notification_sync(service="kleize", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (KleizeGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="kleize", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="kleize", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_conto")
async def generate_image_conto_endpoint(
        req: ImageConto,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Conto (Subito Payment) - JSON"""
    try:
        image_data = create_conto_image(req.title, req.price)
        send_api_notification_sync(service="conto", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (ContoGenerationError, PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="conto", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="conto", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_conto_form")
async def generate_image_conto_form(
        title: str = Form(...),
        price: float = Form(...),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Conto (Subito Payment) - Form Data"""
    try:
        image_data = create_conto_image(title, price)
        send_api_notification_sync(service="conto", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (ContoGenerationError, PDFGenerationError, FigmaNodeNotFoundError) as e:
        send_api_notification_sync(service="conto", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="conto", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_depop")
async def generate_image_depop_endpoint(
        req: ImageDepop,
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Depop (AU) - JSON"""
    try:
        image_data = create_depop_image(
            req.title, 
            req.price, 
            req.seller_name, 
            req.photo, 
            req.avatar, 
            req.url
        )
        send_api_notification_sync(service="depop", key_name=key_name, title=req.title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DepopGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="depop", key_name=key_name, title=req.title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="depop", key_name=key_name, title=req.title if hasattr(req, 'title') else "Unknown", success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate_image_depop_form")
async def generate_image_depop_form(
        title: str = Form(...),
        price: float = Form(...),
        seller_name: str = Form(...),
        url: str = Form(...),
        photo: UploadFile = File(None),
        avatar: UploadFile = File(None),
        key_name: str = Depends(verify_api_key)
):
    """Генерация изображения для Depop (AU) - Form Data"""
    try:
        # Обработка фото товара
        photo_b64 = None
        if photo:
            photo_b64 = base64.b64encode(await photo.read()).decode("utf-8")
        
        # Обработка аватара
        avatar_b64 = None
        if avatar:
            avatar_b64 = base64.b64encode(await avatar.read()).decode("utf-8")
        
        image_data = create_depop_image(
            title, 
            price, 
            seller_name, 
            photo_b64, 
            avatar_b64, 
            url
        )
        send_api_notification_sync(service="depop", key_name=key_name, title=title, success=True)
        return Response(content=image_data, media_type="image/png")
    except (DepopGenerationError, PDFGenerationError, FigmaNodeNotFoundError, QRGenerationError) as e:
        send_api_notification_sync(service="depop", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        send_api_notification_sync(service="depop", key_name=key_name, title=title, success=False, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def api_status(key_name: str = Depends(verify_api_key)):
    """Проверка статуса API"""
    return {
        "status": "active",
        "key_name": key_name,
        "message": "API key is valid"
    }
