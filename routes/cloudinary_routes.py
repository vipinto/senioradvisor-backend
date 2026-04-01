import time
import os
import cloudinary
import cloudinary.utils
import cloudinary.uploader
from fastapi import APIRouter, Query, HTTPException, Request
from database import db
from auth import get_current_user

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

router = APIRouter()

ALLOWED_FOLDERS = ("providers/", "profiles/", "gallery/", "premium/")


@router.get("/cloudinary/signature")
async def generate_signature(
    request: Request,
    folder: str = "providers/gallery",
):
    user = await get_current_user(request, db)
    if not folder.startswith(ALLOWED_FOLDERS):
        raise HTTPException(status_code=400, detail="Carpeta no permitida")

    timestamp = int(time.time())
    params = {
        "timestamp": timestamp,
        "folder": folder,
    }

    signature = cloudinary.utils.api_sign_request(
        params,
        os.environ.get("CLOUDINARY_API_SECRET")
    )

    return {
        "signature": signature,
        "timestamp": timestamp,
        "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME"),
        "api_key": os.environ.get("CLOUDINARY_API_KEY"),
        "folder": folder,
    }


@router.delete("/cloudinary/delete")
async def delete_asset(request: Request):
    user = await get_current_user(request, db)
    data = await request.json()
    public_id = data.get("public_id")
    if not public_id:
        raise HTTPException(status_code=400, detail="public_id requerido")
    result = cloudinary.uploader.destroy(public_id, invalidate=True)
    return {"result": result.get("result", "error")}


from fastapi import UploadFile, File

@router.post("/cloudinary/upload")
async def upload_to_cloudinary(
    request: Request,
    file: UploadFile = File(...),
    folder: str = "blog",
):
    user = await get_current_user(request, db)
    if not os.environ.get("CLOUDINARY_CLOUD_NAME"):
        raise HTTPException(status_code=500, detail="Cloudinary no configurado")
    
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo muy grande (max 10MB)")
    
    result = cloudinary.uploader.upload(
        contents,
        folder=folder,
        resource_type="image",
    )
    
    return {
        "url": result.get("secure_url"),
        "public_id": result.get("public_id"),
    }
