from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import uuid
import math
from PIL import Image
import io

from database import db
from models import ProviderCreate, ProviderUpdate, ServiceCreate
from auth import (
    get_current_user, get_current_user_optional,
    require_provider, require_subscription
)
from routes.contact_request_routes import check_connection

router = APIRouter()

# Upload directories
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOADS_DIR = BASE_DIR / "uploads"
GALLERY_DIR = UPLOADS_DIR / "gallery"
PERSONAL_PHOTOS_DIR = UPLOADS_DIR / "personal"
PROFILE_PHOTOS_DIR = UPLOADS_DIR / "profile"

PREMIUM_GALLERY_DIR = UPLOADS_DIR / "premium_gallery"

GALLERY_DIR.mkdir(parents=True, exist_ok=True)
PERSONAL_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
PREMIUM_GALLERY_DIR.mkdir(parents=True, exist_ok=True)

# Max image dimensions and quality for compression
MAX_IMAGE_WIDTH = 1200
MAX_IMAGE_HEIGHT = 900
THUMBNAIL_SIZE = (400, 300)
JPEG_QUALITY = 75  # Good balance between quality and size


def compress_image(image_data: bytes, max_size_kb: int = 200) -> tuple:
    """
    Compress image to reduce file size while maintaining quality.
    Returns (compressed_bytes, thumbnail_bytes)
    """
    img = Image.open(io.BytesIO(image_data))

    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if too large
    if img.width > MAX_IMAGE_WIDTH or img.height > MAX_IMAGE_HEIGHT:
        img.thumbnail((MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)

    # Compress main image
    output = io.BytesIO()
    quality = JPEG_QUALITY
    img.save(output, format="JPEG", quality=quality, optimize=True)

    # If still too large, reduce quality further
    while output.tell() > max_size_kb * 1024 and quality > 40:
        output = io.BytesIO()
        quality -= 10
        img.save(output, format="JPEG", quality=quality, optimize=True)

    # Create thumbnail
    thumb = img.copy()
    thumb.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    thumb_output = io.BytesIO()
    thumb.save(thumb_output, format="JPEG", quality=70, optimize=True)

    return output.getvalue(), thumb_output.getvalue()


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# NOTE: my-profile endpoints must be defined BEFORE {provider_id} routes

def calculate_profile_completeness(provider: dict, services: list) -> dict:
    """Calculate profile completeness and return missing sections"""
    sections = {
        "profile": {
            "name": "Mi Perfil",
            "complete": False,
            "missing": [],
        },
        "personal_info": {
            "name": "Más Datos",
            "complete": False,
            "missing": [],
        },
        "gallery": {
            "name": "Galería",
            "complete": False,
            "missing": [],
        },
        "zones": {
            "name": "Zonas",
            "complete": False,
            "missing": [],
        },
        "availability": {
            "name": "Disponibilidad",
            "complete": False,
            "missing": [],
        },
        "services": {
            "name": "Servicios",
            "complete": False,
            "missing": [],
        },
    }

    # Check Mi Perfil (profile_photo is optional/recommended, not required)
    profile_fields = ["business_name", "description", "phone", "address", "comuna"]
    profile_missing = []
    for field in profile_fields:
        if not provider.get(field):
            profile_missing.append(field)

    sections["profile"]["complete"] = len(profile_missing) == 0
    sections["profile"]["missing"] = profile_missing
    if not provider.get("profile_photo"):
        sections["profile"]["missing"].append("profile_photo (recomendado)")

    # Check Más Datos (Personal Info)
    pi = provider.get("personal_info", {})
    pi_required = ["housing_type", "animal_experience"]
    pi_missing = []
    for field in pi_required:
        if not pi.get(field):
            pi_missing.append(field)
    sections["personal_info"]["complete"] = len(pi_missing) == 0
    sections["personal_info"]["missing"] = pi_missing

    # Check Galería (at least 1 photo)
    gallery = provider.get("gallery", [])
    sections["gallery"]["complete"] = len(gallery) >= 1
    if not sections["gallery"]["complete"]:
        sections["gallery"]["missing"] = ["Sube al menos 1 foto a tu galería"]

    # Check Zonas
    has_zona = bool(provider.get("comuna"))
    sections["zones"]["complete"] = has_zona
    if not has_zona:
        sections["zones"]["missing"] = ["comuna"]

    # Check Disponibilidad
    always_active = provider.get("always_active", True)
    available_dates = provider.get("available_dates", [])
    sections["availability"]["complete"] = always_active or len(available_dates) > 0
    if not sections["availability"]["complete"]:
        sections["availability"]["missing"] = ["Configura tu disponibilidad"]

    # Check Services (at least 1 service)
    sections["services"]["complete"] = len(services) >= 1
    if not sections["services"]["complete"]:
        sections["services"]["missing"] = ["Agrega al menos 1 servicio"]

    completed = sum(1 for s in sections.values() if s["complete"])
    total = len(sections)
    is_complete = completed == total

    return {
        "sections": sections,
        "completed_count": completed,
        "total_count": total,
        "percentage": round((completed / total) * 100),
        "is_complete": is_complete,
    }


@router.get("/providers/my-profile")
async def get_my_provider_profile(request: Request):
    """Get current user's provider profile"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0},
    )
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    services = await db.services.find(
        {"provider_id": provider["provider_id"]},
        {"_id": 0},
    ).to_list(10)
    provider["services"] = services
    provider["profile_completeness"] = calculate_profile_completeness(provider, services)

    # Check subscription status
    sub = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0},
    )
    # Admin override: if is_subscribed stored in provider doc, use that
    if "is_subscribed" in provider:
        pass  # keep admin-set value
    else:
        provider["is_subscribed"] = sub is not None
    provider["has_active_subscription"] = sub is not None or provider.get("is_subscribed", False)

    return provider


@router.put("/providers/my-profile")
async def update_my_provider_profile(request: Request):
    """Update current user's provider profile"""
    user = await get_current_user(request, db)
    data = await request.json()

    allowed_fields = [
        "business_name", "description", "phone", "whatsapp", "address",
        "comuna", "region", "services", "always_active", "available_dates",
        "latitude", "longitude", "amenities", "social_links", "place_id",
        "price_from", "youtube_video_url"
    ]
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.providers.update_one(
        {"user_id": user["user_id"]},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return {"message": "Perfil actualizado"}


@router.put("/providers/my-profile/services")
async def update_my_profile_services(request: Request):
    """Update provider's services"""
    user = await get_current_user(request, db)
    data = await request.json()

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    provider_id = provider["provider_id"]
    services = data.get("services", [])

    await db.services.delete_many({"provider_id": provider_id})

    if services:
        for svc in services:
            service_doc = {
                "service_id": f"serv_{uuid.uuid4().hex[:12]}",
                "provider_id": provider_id,
                "service_type": svc.get("service_type"),
                "price_from": svc.get("price_from", 0),
                "description": svc.get("description", ""),
                "rules": svc.get("rules", ""),
                "pet_sizes": svc.get("pet_sizes", []),
                "created_at": datetime.now(timezone.utc),
            }
            await db.services.insert_one(service_doc)

    return {"message": f"{len(services)} servicio(s) actualizado(s)"}


@router.put("/providers/my-profile/amenities")
async def update_my_amenities(request: Request):
    """Update provider's amenities"""
    user = await get_current_user(request, db)
    data = await request.json()
    amenities = data.get("amenities", [])

    result = await db.providers.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"amenities": amenities}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return {"message": "Amenidades actualizadas", "amenities": amenities}


@router.put("/providers/my-profile/social")
async def update_my_social(request: Request):
    """Update provider's social links"""
    user = await get_current_user(request, db)
    data = await request.json()

    social_links = {}
    if data.get("instagram"):
        social_links["instagram"] = data["instagram"]
    if data.get("facebook"):
        social_links["facebook"] = data["facebook"]
    if data.get("website"):
        social_links["website"] = data["website"]

    result = await db.providers.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"social_links": social_links}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return {"message": "Redes sociales actualizadas", "social_links": social_links}


@router.put("/providers/my-profile/personal-info")
async def update_personal_info(request: Request):
    """Update carer's personal information (Más Datos)"""
    user = await get_current_user(request, db)
    data = await request.json()

    allowed_fields = [
        "housing_type", "has_yard", "yard_description",
        "has_own_pets", "own_pets_description",
        "animal_experience", "daily_availability", "additional_info",
    ]
    personal_info = {k: v for k, v in data.items() if k in allowed_fields}
    personal_info["updated_at"] = datetime.now(timezone.utc).isoformat()

    provider = await db.providers.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "personal_info": 1},
    )
    if provider and provider.get("personal_info"):
        existing = provider["personal_info"]
        for key in ["yard_photos", "pets_photos"]:
            if key in existing:
                personal_info[key] = existing[key]

    result = await db.providers.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"personal_info": personal_info}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return {"message": "Información personal actualizada", "personal_info": personal_info}


@router.get("/providers/my-profile/personal-info")
async def get_personal_info(request: Request):
    """Get carer's personal information"""
    user = await get_current_user(request, db)
    provider = await db.providers.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "personal_info": 1},
    )
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return provider.get("personal_info", {})



@router.put("/providers/my-profile/youtube-video")
async def update_youtube_video(request: Request):
    """Update provider's YouTube video URL (subscription required)"""
    user = await get_current_user(request, db)
    await require_subscription(user, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    body = await request.json()
    youtube_url = body.get("youtube_video_url", "").strip()

    await db.providers.update_one(
        {"provider_id": provider["provider_id"]},
        {"$set": {"youtube_video_url": youtube_url}},
    )
    return {"message": "Video actualizado", "youtube_video_url": youtube_url}



@router.post("/providers/my-profile/photo")
async def upload_profile_photo(request: Request, file: UploadFile = File(...)):
    """Upload provider profile photo"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    contents = await file.read()

    try:
        compressed_data, _thumbnail_data = compress_image(contents, max_size_kb=300)
        photo_id = f"profile_{provider['provider_id']}_{uuid.uuid4().hex[:8]}"
        main_filename = f"{photo_id}.jpg"

        with open(PROFILE_PHOTOS_DIR / main_filename, "wb") as f:
            f.write(compressed_data)

        photo_url = f"/api/uploads/profile/{main_filename}"

        old_photo = provider.get("profile_photo")
        if old_photo:
            old_filename = old_photo.split("/")[-1]
            old_path = PROFILE_PHOTOS_DIR / old_filename
            if old_path.exists():
                try:
                    old_path.unlink()
                except Exception:
                    pass

        await db.providers.update_one(
            {"provider_id": provider["provider_id"]},
            {"$set": {"profile_photo": photo_url, "updated_at": datetime.now(timezone.utc)}},
        )

        return {"message": "Foto de perfil actualizada", "photo_url": photo_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


@router.post("/providers/my-profile/personal-info/photos")
async def upload_personal_photo(request: Request, file: UploadFile = File(...), category: str = "yard"):
    """Upload a photo for personal info (yard or pets)"""
    user = await get_current_user(request, db)

    if category not in ("yard", "pets"):
        raise HTTPException(status_code=400, detail="Categoría debe ser 'yard' o 'pets'")

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    personal_info = provider.get("personal_info", {})
    photos_key = f"{category}_photos"
    current_photos = personal_info.get(photos_key, [])
    if len(current_photos) >= 3:
        raise HTTPException(status_code=400, detail=f"Máximo 3 fotos para {category}")

    contents = await file.read()

    try:
        compressed_data, thumbnail_data = compress_image(contents)
        photo_id = f"personal_{category}_{uuid.uuid4().hex[:12]}"
        main_filename = f"{photo_id}.jpg"
        thumb_filename = f"{photo_id}_thumb.jpg"

        with open(PERSONAL_PHOTOS_DIR / main_filename, "wb") as f:
            f.write(compressed_data)
        with open(PERSONAL_PHOTOS_DIR / thumb_filename, "wb") as f:
            f.write(thumbnail_data)

        photo_record = {
            "photo_id": photo_id,
            "category": category,
            "url": f"/api/uploads/personal/{main_filename}",
            "thumbnail_url": f"/api/uploads/personal/{thumb_filename}",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.providers.update_one(
            {"user_id": user["user_id"]},
            {"$push": {f"personal_info.{photos_key}": photo_record}},
        )

        return {"message": "Foto subida", "photo": photo_record}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


@router.delete("/providers/my-profile/personal-info/photos/{photo_id}")
async def delete_personal_photo(photo_id: str, request: Request):
    """Delete a personal info photo"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    personal_info = provider.get("personal_info", {})
    for photos_key in ["yard_photos", "pets_photos"]:
        for photo in personal_info.get(photos_key, []):
            if photo["photo_id"] == photo_id:
                try:
                    for fname in [f"{photo_id}.jpg", f"{photo_id}_thumb.jpg"]:
                        fpath = PERSONAL_PHOTOS_DIR / fname
                        if fpath.exists():
                            fpath.unlink()
                except Exception:
                    pass

                await db.providers.update_one(
                    {"user_id": user["user_id"]},
                    {"$pull": {f"personal_info.{photos_key}": {"photo_id": photo_id}}},
                )
                return {"message": "Foto eliminada"}

    raise HTTPException(status_code=404, detail="Foto no encontrada")


@router.put("/providers/my-services")
async def update_my_services(request: Request):
    """Update services for current provider"""
    user = await get_current_user(request, db)
    data = await request.json()
    services = data.get("services", [])

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    provider_id = provider["provider_id"]
    await db.services.delete_many({"provider_id": provider_id})

    for svc in services:
        service_doc = {
            "service_id": f"serv_{uuid.uuid4().hex[:12]}",
            "provider_id": provider_id,
            "service_type": svc["service_type"],
            "price_from": svc.get("price_from"),
            "description": svc.get("description"),
            "rules": svc.get("rules"),
            "pet_sizes": svc.get("pet_sizes", []),
            "created_at": datetime.now(timezone.utc),
        }
        await db.services.insert_one(service_doc)

    return {"message": "Servicios actualizados"}


@router.post("/providers/gallery/upload")
async def upload_gallery_photo(request: Request, file: UploadFile = File(...)):
    """Upload a photo to provider's gallery with automatic compression"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    contents = await file.read()
    original_size = len(contents)

    current_gallery = provider.get("gallery", [])
    if len(current_gallery) >= 3:
        raise HTTPException(status_code=400, detail="Máximo 3 fotos en la galería")

    try:
        compressed_data, thumbnail_data = compress_image(contents)
        compressed_size = len(compressed_data)

        photo_id = f"gallery_{uuid.uuid4().hex[:12]}"
        main_filename = f"{photo_id}.jpg"
        thumb_filename = f"{photo_id}_thumb.jpg"

        main_path = GALLERY_DIR / main_filename
        thumb_path = GALLERY_DIR / thumb_filename

        with open(main_path, "wb") as f:
            f.write(compressed_data)
        with open(thumb_path, "wb") as f:
            f.write(thumbnail_data)

        photo_record = {
            "photo_id": photo_id,
            "url": f"/api/uploads/gallery/{main_filename}",
            "thumbnail_url": f"/api/uploads/gallery/{thumb_filename}",
            "original_size_kb": round(original_size / 1024, 1),
            "compressed_size_kb": round(compressed_size / 1024, 1),
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.providers.update_one(
            {"provider_id": provider["provider_id"]},
            {"$push": {"gallery": photo_record}},
        )

        return {
            "message": "Foto subida exitosamente",
            "photo": photo_record,
            "compression": {
                "original_kb": round(original_size / 1024, 1),
                "compressed_kb": round(compressed_size / 1024, 1),
                "reduction": f"{round((1 - compressed_size / original_size) * 100)}%",
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


@router.delete("/providers/gallery/{photo_id}")
async def delete_gallery_photo(photo_id: str, request: Request):
    """Delete a photo from provider's gallery"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    gallery = provider.get("gallery", [])
    photo_to_delete = None
    for photo in gallery:
        if photo["photo_id"] == photo_id:
            photo_to_delete = photo
            break

    if not photo_to_delete:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    try:
        main_file = GALLERY_DIR / f"{photo_id}.jpg"
        thumb_file = GALLERY_DIR / f"{photo_id}_thumb.jpg"
        if main_file.exists():
            main_file.unlink()
        if thumb_file.exists():
            thumb_file.unlink()
    except Exception:
        pass

    await db.providers.update_one(
        {"provider_id": provider["provider_id"]},
        {"$pull": {"gallery": {"photo_id": photo_id}}},
    )

    return {"message": "Foto eliminada"}


@router.get("/providers/gallery")
async def get_my_gallery(request: Request):
    """Get current provider's gallery photos"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "gallery": 1},
    )
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    return provider.get("gallery", [])


@router.put("/providers/gallery/reorder")
async def reorder_gallery(request: Request):
    """Reorder gallery photos"""
    user = await get_current_user(request, db)
    data = await request.json()
    photo_ids = data.get("photo_ids", [])

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    current_gallery = provider.get("gallery", [])
    gallery_dict = {p["photo_id"]: p for p in current_gallery}

    new_gallery = []
    for pid in photo_ids:
        if pid in gallery_dict:
            new_gallery.append(gallery_dict[pid])

    for photo in current_gallery:
        if photo["photo_id"] not in photo_ids:
            new_gallery.append(photo)

    await db.providers.update_one(
        {"provider_id": provider["provider_id"]},
        {"$set": {"gallery": new_gallery}},
    )

    return {"message": "Galería reordenada", "gallery": new_gallery}



# ============= PREMIUM GALLERY (SUBSCRIPTION REQUIRED) =============

@router.get("/providers/my-profile/premium-gallery")
async def get_my_premium_gallery(request: Request):
    """Get current provider's premium gallery photos"""
    user = await get_current_user(request, db)
    provider = await db.providers.find_one(
        {"user_id": user["user_id"]},
        {"_id": 0, "premium_gallery": 1},
    )
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    return provider.get("premium_gallery", [])


@router.post("/providers/my-profile/premium-gallery")
async def upload_premium_gallery_photo(request: Request, file: UploadFile = File(...)):
    """Upload a photo to provider's premium gallery (subscription required)"""
    user = await get_current_user(request, db)
    await require_subscription(user, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    current_premium = provider.get("premium_gallery", [])
    if len(current_premium) >= 10:
        raise HTTPException(status_code=400, detail="Máximo 10 fotos en el slider premium")

    contents = await file.read()

    try:
        compressed_data, thumbnail_data = compress_image(contents)
        photo_id = f"premium_{uuid.uuid4().hex[:12]}"
        main_filename = f"{photo_id}.jpg"
        thumb_filename = f"{photo_id}_thumb.jpg"

        with open(PREMIUM_GALLERY_DIR / main_filename, "wb") as f:
            f.write(compressed_data)
        with open(PREMIUM_GALLERY_DIR / thumb_filename, "wb") as f:
            f.write(thumbnail_data)

        photo_record = {
            "photo_id": photo_id,
            "url": f"/api/uploads/premium_gallery/{main_filename}",
            "thumbnail_url": f"/api/uploads/premium_gallery/{thumb_filename}",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.providers.update_one(
            {"provider_id": provider["provider_id"]},
            {"$push": {"premium_gallery": photo_record}},
        )

        return {"message": "Foto premium subida exitosamente", "photo": photo_record}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar imagen: {str(e)}")


@router.delete("/providers/my-profile/premium-gallery/{photo_id}")
async def delete_premium_gallery_photo(photo_id: str, request: Request):
    """Delete a photo from provider's premium gallery"""
    user = await get_current_user(request, db)
    await require_subscription(user, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    premium_gallery = provider.get("premium_gallery", [])
    photo_found = any(p["photo_id"] == photo_id for p in premium_gallery)
    if not photo_found:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    try:
        for fname in [f"{photo_id}.jpg", f"{photo_id}_thumb.jpg"]:
            fpath = PREMIUM_GALLERY_DIR / fname
            if fpath.exists():
                fpath.unlink()
    except Exception:
        pass

    await db.providers.update_one(
        {"provider_id": provider["provider_id"]},
        {"$pull": {"premium_gallery": {"photo_id": photo_id}}},
    )

    return {"message": "Foto premium eliminada"}



@router.get("/providers")
async def search_providers(
    request: Request,
    comuna: Optional[str] = None,
    q: Optional[str] = None,
    service_type: Optional[str] = None,
    min_rating: Optional[float] = None,
    verified_only: bool = False,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: Optional[float] = None,
    bounds_south: Optional[float] = None,
    bounds_west: Optional[float] = None,
    bounds_north: Optional[float] = None,
    bounds_east: Optional[float] = None,
    dates: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    featured: bool = False,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
):
    """Search providers with filters"""
    user = await get_current_user_optional(request, db)
    has_subscription = False
    if user:
        sub = await db.subscriptions.find_one(
            {"user_id": user["user_id"], "status": "active"},
            {"_id": 0},
        )
        has_subscription = sub is not None

    query = {
        "approved": True,
        "business_name": {"$exists": True, "$ne": ""},
    }

    # Search by q (name, address, comuna) or just comuna
    search_term = q or comuna
    if search_term:
        query["$or"] = [
            {"business_name": {"$regex": search_term, "$options": "i"}},
            {"address": {"$regex": search_term, "$options": "i"}},
            {"comuna": {"$regex": search_term, "$options": "i"}},
        ]
    if verified_only:
        query["verified"] = True
    if min_rating:
        query["rating"] = {"$gte": min_rating}

    if min_price or max_price:
        price_filter = {}
        if min_price:
            price_filter["$gte"] = min_price
        if max_price:
            price_filter["$lte"] = max_price
        query["price_from"] = price_filter

    if all([bounds_south, bounds_west, bounds_north, bounds_east]):
        query["latitude"] = {"$gte": bounds_south, "$lte": bounds_north}
        query["longitude"] = {"$gte": bounds_west, "$lte": bounds_east}

    if service_type:
        services_coll = await db.services.find(
            {"service_type": service_type},
            {"_id": 0, "provider_id": 1},
        ).to_list(5000)
        provider_ids_from_collection = {s["provider_id"] for s in services_coll}
        svc_filter = {"$or": [
            {"provider_id": {"$in": list(provider_ids_from_collection)}},
            {"services": {"$elemMatch": {"service_type": service_type}}},
        ]}
        # Combine with $and to avoid $or conflict
        if "$or" in query:
            existing_or = query.pop("$or")
            query["$and"] = [{"$or": existing_or}, svc_filter]
        else:
            query.update(svc_filter)

    import logging
    logging.info(f"Provider search query: {query}")
    
    providers = await db.providers.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
    logging.info(f"Found {len(providers)} providers")

    if latitude and longitude and radius_km:
        filtered_providers = []
        for provider in providers:
            if provider.get("latitude") and provider.get("longitude"):
                distance = calculate_distance(latitude, longitude, provider["latitude"], provider["longitude"])
                if distance <= radius_km:
                    provider["distance_km"] = round(distance, 2)
                    filtered_providers.append(provider)
        providers = filtered_providers

    if dates:
        search_dates = [d.strip()[:10] for d in dates.split(",") if d.strip()]
        filtered = []
        for provider in providers:
            if provider.get("always_active", True):
                filtered.append(provider)
            elif provider.get("available_dates"):
                provider_dates = {d[:10] for d in provider["available_dates"]}
                if any(sd in provider_dates for sd in search_dates):
                    filtered.append(provider)
            else:
                filtered.append(provider)
        providers = filtered

    subscribed_provider_user_ids = set()
    if providers:
        all_user_ids = [p["user_id"] for p in providers]
        active_subs = await db.subscriptions.find(
            {"user_id": {"$in": all_user_ids}, "status": "active"},
            {"_id": 0, "user_id": 1},
        ).to_list(500)
        subscribed_provider_user_ids = {s["user_id"] for s in active_subs}

    all_provider_ids = [p["provider_id"] for p in providers]
    all_services = await db.services.find(
        {"provider_id": {"$in": all_provider_ids}},
        {"_id": 0},
    ).to_list(5000)

    services_by_provider = {}
    for svc in all_services:
        services_by_provider.setdefault(svc["provider_id"], []).append(svc)

    providers_with_services = []
    for provider in providers:
        # Check both services collection and embedded services array
        svc_from_collection = services_by_provider.get(provider["provider_id"], [])
        svc_embedded = provider.get("services", [])
        provider["services"] = svc_from_collection if svc_from_collection else svc_embedded
        providers_with_services.append(provider)
    providers = providers_with_services

    for provider in providers:
        is_verified = provider.get("verified", False)
        is_subscribed = provider["user_id"] in subscribed_provider_user_ids
        provider["is_featured"] = is_verified and is_subscribed
        provider["is_verified_only"] = is_verified and not is_subscribed

        # Clientes ven toda la información sin restricción
        # provider["phone"] = None
        # provider["whatsapp"] = None
        # provider["address"] = None
        provider["full_name_hidden"] = False  # Siempre mostrar nombre completo

    def sort_key(p):
        if p.get("is_featured"):
            return (0, -(p.get("rating") or 0))
        elif p.get("is_verified_only"):
            return (1, -(p.get("rating") or 0))
        else:
            return (2, -(p.get("rating") or 0))

    providers.sort(key=sort_key)

    # Filter featured only (with subscription) and minimum rating 4.0
    if featured:
        providers = [p for p in providers if p.get("is_featured") and (p.get("rating") or 0) >= 4.0]

    # Count total for pagination (re-run query without skip/limit)
    total_count = await db.providers.count_documents(query)

    return {"results": providers, "total": total_count, "skip": skip, "limit": limit}


@router.get("/providers/comunas")
async def get_comunas():
    """Get distinct comunas for autocomplete"""
    comunas = await db.providers.distinct("comuna", {"approved": True, "comuna": {"$exists": True, "$ne": ""}})
    comunas = sorted([c for c in comunas if c and c.strip()])
    return comunas


# ============= SUCURSALES (BRANCHES) =============
# NOTE: These routes must be BEFORE /providers/{provider_id} to avoid route conflicts

from pydantic import BaseModel as PydanticBaseModel

class BranchCreate(PydanticBaseModel):
    business_name: str
    phone: Optional[str] = ""
    address: Optional[str] = ""
    comuna: Optional[str] = ""
    region: Optional[str] = ""
    website: Optional[str] = ""
    facebook: Optional[str] = ""
    instagram: Optional[str] = ""


@router.get("/providers/my-branches")
async def get_my_branches(request: Request):
    """Get branches of the current provider"""
    user = await get_current_user(request, db)
    provider = await db.providers.find_one({"user_id": user["user_id"], "parent_provider_id": {"$exists": False}}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    branches = await db.providers.find(
        {"parent_provider_id": provider["provider_id"]},
        {"_id": 0}
    ).to_list(20)
    return branches


@router.post("/providers/my-branches")
async def create_branch(data: BranchCreate, request: Request):
    """Create a branch (sucursal) for the current provider"""
    user = await get_current_user(request, db)
    parent = await db.providers.find_one({"user_id": user["user_id"], "parent_provider_id": {"$exists": False}}, {"_id": 0})
    if not parent:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor principal")

    if not data.business_name.strip():
        raise HTTPException(status_code=400, detail="El nombre de la sucursal es obligatorio")

    branch_count = await db.providers.count_documents({"parent_provider_id": parent["provider_id"]})
    if branch_count >= 5:
        raise HTTPException(status_code=400, detail="Máximo 5 sucursales permitidas")

    branch_id = f"prov_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    social_links = {}
    if data.website:
        social_links["website"] = data.website
    if data.facebook:
        social_links["facebook"] = data.facebook
    if data.instagram:
        social_links["instagram"] = data.instagram

    branch_doc = {
        "provider_id": branch_id,
        "user_id": user["user_id"],
        "parent_provider_id": parent["provider_id"],
        "business_name": data.business_name,
        "phone": data.phone or parent.get("phone", ""),
        "whatsapp": data.phone or parent.get("whatsapp", ""),
        "address": data.address or "",
        "comuna": data.comuna or "",
        "region": data.region or "",
        "description": parent.get("description", ""),
        "services": parent.get("services", []),
        "photos": [],
        "gallery": parent.get("gallery", []),
        "amenities": parent.get("amenities", []),
        "social_links": social_links if social_links else parent.get("social_links", {}),
        "personal_info": parent.get("personal_info", {}),
        "rating": 0,
        "total_reviews": 0,
        "approved": parent.get("approved", True),
        "verified": parent.get("verified", False),
        "latitude": 0,
        "longitude": 0,
        "place_id": "",
        "coverage_zone": parent.get("coverage_zone", "10"),
        "created_at": now,
        "registration_source": "branch",
    }
    await db.providers.insert_one(branch_doc)

    return {
        "message": "Sucursal creada exitosamente",
        "provider_id": branch_id,
        "business_name": data.business_name,
    }


@router.delete("/providers/my-branches/{branch_id}")
async def delete_branch(branch_id: str, request: Request):
    """Delete a branch"""
    user = await get_current_user(request, db)
    parent = await db.providers.find_one({"user_id": user["user_id"], "parent_provider_id": {"$exists": False}})
    if not parent:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    branch = await db.providers.find_one({"provider_id": branch_id, "parent_provider_id": parent["provider_id"]})
    if not branch:
        raise HTTPException(status_code=404, detail="Sucursal no encontrada")

    await db.providers.delete_one({"provider_id": branch_id})
    return {"message": "Sucursal eliminada"}


@router.get("/providers/{provider_id}")
async def get_provider(provider_id: str, request: Request):
    """Get provider details"""
    user = await get_current_user_optional(request, db)

    provider = await db.providers.find_one(
        {"provider_id": provider_id},
        {"_id": 0},
    )
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    services = await db.services.find(
        {"provider_id": provider_id},
        {"_id": 0},
    ).to_list(10)
    # Merge services collection with embedded services array
    embedded_services = provider.get("services", [])
    provider["services"] = services if services else embedded_services

    reviews = await db.reviews.find(
        {
            "provider_id": provider_id,
            "approved": True,
            "$or": [{"published": True}, {"published": {"$exists": False}}],
        },
        {"_id": 0},
    ).sort("created_at", -1).limit(10).to_list(10)

    for review in reviews:
        reviewer = await db.users.find_one(
            {"user_id": review["user_id"]},
            {"_id": 0, "name": 1, "picture": 1},
        )
        if reviewer:
            review["user_name"] = reviewer["name"]
            review["user_picture"] = reviewer.get("picture")

    provider["reviews"] = reviews

    # Merge google reviews with internal reviews
    google_reviews = provider.get("google_reviews", [])
    merged_reviews = list(reviews)  # Internal first
    for gr in google_reviews[:20]:
        merged_reviews.append({
            "user_name": gr.get("author", "Usuario Google"),
            "user_picture": gr.get("author_photo", ""),
            "rating": gr.get("rating", 0),
            "overall_rating": gr.get("rating", 0),
            "comment": gr.get("text", ""),
            "time_description": gr.get("time_description", ""),
            "publish_time": gr.get("publish_time", ""),
            "source": "google",
        })
    # Sort by most recent first
    merged_reviews.sort(
        key=lambda r: r.get("publish_time") or r.get("created_at") or "",
        reverse=True,
    )
    provider["reviews"] = merged_reviews
    # Remove raw google_reviews from response to keep it clean
    provider.pop("google_reviews", None)

    has_subscription = False
    is_connected = False
    has_pending_request = False
    if user:
        subscription = await db.subscriptions.find_one(
            {"user_id": user["user_id"], "status": "active"},
            {"_id": 0},
        )
        has_subscription = subscription is not None
        is_connected = await check_connection(user["user_id"], provider["user_id"])
        if not is_connected:
            pending = await db.contact_requests.find_one({
                "client_user_id": user["user_id"],
                "provider_user_id": provider["user_id"],
                "status": "pending",
            })
            has_pending_request = pending is not None

    provider_sub = await db.subscriptions.find_one(
        {"user_id": provider["user_id"], "status": "active"},
        {"_id": 0},
    )
    provider_is_subscribed = provider_sub is not None
    # Admin override: if is_featured/is_subscribed stored in provider doc, use those
    if "is_featured" in provider:
        pass  # keep the stored value
    else:
        provider["is_featured"] = provider.get("verified", False) and provider_is_subscribed
    if "is_subscribed" in provider:
        provider["provider_is_subscribed"] = provider["is_subscribed"]
    else:
        provider["provider_is_subscribed"] = provider_is_subscribed
    provider["viewer_has_subscription"] = True  # Clientes siempre ven todo
    provider["viewer_is_connected"] = is_connected
    provider["viewer_has_pending_request"] = has_pending_request

    # Only include premium_gallery if provider is subscribed
    if not provider.get("provider_is_subscribed"):
        provider["premium_gallery"] = []

    # Clientes ven toda la información de contacto sin restricción
    provider["contact_blocked"] = False
    provider["contact_message"] = None

    provider["full_name_hidden"] = False

    return provider


@router.post("/providers")
async def create_provider(provider_data: ProviderCreate, request: Request):
    """Create provider profile"""
    user = await get_current_user(request, db)

    existing = await db.providers.find_one({"user_id": user["user_id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes un perfil de proveedor")

    if not provider_data.services_offered:
        raise HTTPException(status_code=400, detail="Debes seleccionar al menos un servicio")

    has_verification_docs = all([
        provider_data.id_front_photo,
        provider_data.id_back_photo,
        provider_data.selfie_photo,
        provider_data.background_certificate,
    ])

    provider_id = f"prov_{uuid.uuid4().hex[:12]}"
    provider_dict = provider_data.model_dump(exclude={"services_offered"})
    provider = {
        "provider_id": provider_id,
        "user_id": user["user_id"],
        **provider_dict,
        "latitude": provider_data.latitude,
        "longitude": provider_data.longitude,
        "verified": False,
        "rating": 0.0,
        "total_reviews": 0,
        "created_at": datetime.now(timezone.utc),
        "approved": not has_verification_docs,
        "approved_at": datetime.now(timezone.utc) if not has_verification_docs else None,
        "verification_status": "pending" if has_verification_docs else "none",
        "verification_submitted_at": datetime.now(timezone.utc) if has_verification_docs else None,
    }
    await db.providers.insert_one(provider)

    for svc in provider_data.services_offered:
        service_doc = {
            "service_id": f"serv_{uuid.uuid4().hex[:12]}",
            "provider_id": provider_id,
            "service_type": svc.service_type,
            "price_from": svc.price_from,
            "description": svc.description,
            "rules": svc.rules,
            "pet_sizes": svc.pet_sizes,
            "created_at": datetime.now(timezone.utc),
        }
        await db.services.insert_one(service_doc)

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"role": "provider"}},
    )

    provider.pop("_id", None)
    return provider


@router.put("/providers/{provider_id}")
async def update_provider(provider_id: str, provider_data: ProviderUpdate, request: Request):
    """Update provider profile"""
    user = await get_current_user(request, db)
    provider = await require_provider(user, db)

    if provider["provider_id"] != provider_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    update_data = {k: v for k, v in provider_data.model_dump().items() if v is not None}
    if update_data:
        await db.providers.update_one(
            {"provider_id": provider_id},
            {"$set": update_data},
        )

    updated_provider = await db.providers.find_one(
        {"provider_id": provider_id},
        {"_id": 0},
    )
    return updated_provider


# ============= SERVICE ENDPOINTS =============

@router.post("/providers/{provider_id}/services")
async def create_service(provider_id: str, service_data: ServiceCreate, request: Request):
    """Create service for provider"""
    user = await get_current_user(request, db)
    provider = await require_provider(user, db)

    if provider["provider_id"] != provider_id:
        raise HTTPException(status_code=403, detail="No autorizado")

    service_id = f"serv_{uuid.uuid4().hex[:12]}"
    service = {
        "service_id": service_id,
        "provider_id": provider_id,
        **service_data.model_dump(),
        "created_at": datetime.now(timezone.utc),
    }
    await db.services.insert_one(service)
    service.pop("_id", None)
    return service


@router.get("/providers/{provider_id}/services")
async def get_provider_services(provider_id: str):
    """Get all services for a provider"""
    services = await db.services.find(
        {"provider_id": provider_id},
        {"_id": 0},
    ).to_list(20)
    return services


# ============= PROVIDER DASHBOARD ENDPOINTS =============

@router.get("/provider/requests")
async def get_provider_requests(request: Request):
    """Get requests for current provider"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    requests_list = await db.requests.find(
        {"provider_id": provider["provider_id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)
    return requests_list


@router.post("/provider/requests/{request_id}/{action}")
async def handle_provider_request(request_id: str, action: str, request: Request):
    """Accept or reject a request"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    if action not in ["accept", "reject"]:
        raise HTTPException(status_code=400, detail="Acción no válida")

    status = "accepted" if action == "accept" else "rejected"
    result = await db.requests.update_one(
        {"request_id": request_id, "provider_id": provider["provider_id"]},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"message": f"Solicitud {status}"}


@router.get("/provider/reviews")
async def get_provider_reviews(request: Request):
    """Get reviews for current provider"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")

    reviews = await db.reviews.find(
        {"provider_id": provider["provider_id"]},
        {"_id": 0},
    ).sort("created_at", -1).to_list(100)

    for review in reviews:
        reviewer = await db.users.find_one({"user_id": review.get("user_id")})
        review["user_name"] = reviewer.get("name", "Usuario") if reviewer else "Usuario"

    return reviews
