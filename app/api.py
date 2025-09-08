# app/api.py
from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, HttpUrl
from services.image_card import render_card_png

app = FastAPI(title="QR Screenshot API")

class ShotPayload(BaseModel):
    title: str
    price: str
    source_url: HttpUrl
    landing_url: HttpUrl
    photo_url: HttpUrl | None = None

@app.post("/api/screenshot", response_class=Response)
def screenshot(payload: ShotPayload):
    try:
        png_bytes = render_card_png(
            title=payload.title,
            price=payload.price,
            photo_url=str(payload.photo_url) if payload.photo_url else None,
            landing_url=str(payload.landing_url),
        )
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
