import os
import shutil
import tempfile
import uuid

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.services.apikey import get_all_keys
from app.services.pdf import create_marktplaats_image
from app.services.subito import create_subito_image, create_subito_pdf
from app.utils.time import normalize_hhmm

app = FastAPI(title="QR Generator API")


def _cleanup_tmpdir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _parse_price(value: str) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid price format") from None


def _normalize_url(url: str) -> str:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return f"https://{url}"
    return url


def _save_upload(upload: UploadFile | None, directory: str) -> str | None:
    if upload is None:
        return None
    filename = upload.filename or f"upload_{uuid.uuid4().hex}"
    path = os.path.join(directory, filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    return path


async def validate_api_key(x_api_key: str = Header(...)):
    keys = get_all_keys()
    if x_api_key not in keys:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


@app.post("/generate/subito")
async def generate_subito(
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    name: str = Form(""),
    address: str = Form(""),
    output: str = Form("image"),
    photo: UploadFile | None = File(None),
    api_key: str = Depends(validate_api_key),
):
    tmp_dir = tempfile.mkdtemp(prefix="qrgen_subito_")
    try:
        photo_path = _save_upload(photo, tmp_dir)
        price_value = _parse_price(price)
        safe_url = _normalize_url(url)

        mode = output.lower()
        if mode not in {"image", "pdf"}:
            raise HTTPException(status_code=400, detail="output must be 'image' or 'pdf'")

        if mode == "image":
            image_path, _, _ = create_subito_image(
                title,
                price_value,
                safe_url,
                name=name,
                address=address,
                photo_path=photo_path,
                temp_dir=tmp_dir,
            )
            background = BackgroundTask(_cleanup_tmpdir, tmp_dir)
            return FileResponse(
                image_path,
                media_type="image/png",
                filename=os.path.basename(image_path),
                background=background,
            )

        pdf_path, image_path, processed_photo, qr_path = create_subito_pdf(
            title,
            price_value,
            safe_url,
            name=name,
            address=address,
            photo_path=photo_path,
            temp_dir=tmp_dir,
        )
        background = BackgroundTask(_cleanup_tmpdir, tmp_dir)
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path),
            background=background,
        )
    except HTTPException:
        _cleanup_tmpdir(tmp_dir)
        raise
    except Exception as exc:
        _cleanup_tmpdir(tmp_dir)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")


@app.post("/generate/marktplaats")
async def generate_marktplaats(
    title: str = Form(...),
    price: str = Form(...),
    url: str = Form(...),
    photo: UploadFile | None = File(None),
    time_text: str | None = Form(None),
    api_key: str = Depends(validate_api_key),
):
    tmp_dir = tempfile.mkdtemp(prefix="qrgen_marktplaats_")
    try:
        photo_path = _save_upload(photo, tmp_dir)
        safe_url = _normalize_url(url)

        normalized_time = normalize_hhmm(time_text)
        if time_text and normalized_time is None:
            raise HTTPException(status_code=400, detail="time_text must be in HH:MM format")

        image_path, _, _ = create_marktplaats_image(
            title,
            price,
            photo_path,
            safe_url,
            temp_dir=tmp_dir,
            time_text=normalized_time,
        )
        background = BackgroundTask(_cleanup_tmpdir, tmp_dir)
        return FileResponse(
            image_path,
            media_type="image/png",
            filename=os.path.basename(image_path),
            background=background,
        )
    except HTTPException:
        _cleanup_tmpdir(tmp_dir)
        raise
    except Exception as exc:
        _cleanup_tmpdir(tmp_dir)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")
