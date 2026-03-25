from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from datetime import datetime, timezone
import uuid

from database import db, UPLOADS_DIR
from models import PetCreate, RequestCreate
from auth import get_current_user, require_subscription

router = APIRouter()


# ============= PET ENDPOINTS =============

@router.post("/pets/upload-photo")
async def upload_pet_photo(file: UploadFile = File(...), request: Request = None):
    """Upload a photo for a pet"""
    user = await get_current_user(request, db)

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imagenes")

    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"pet_{uuid.uuid4().hex[:16]}.{ext}"
    filepath = UPLOADS_DIR / "pets" / filename
    (UPLOADS_DIR / "pets").mkdir(exist_ok=True)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar los 5MB")

    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/pets/{filename}"}


@router.post("/pets")
async def create_pet(pet_data: PetCreate, request: Request):
    """Create pet for current user"""
    user = await get_current_user(request, db)

    pet_id = f"pet_{uuid.uuid4().hex[:12]}"
    pet = {
        "pet_id": pet_id,
        "user_id": user["user_id"],
        **pet_data.model_dump(),
        "created_at": datetime.now(timezone.utc)
    }
    await db.pets.insert_one(pet)
    pet.pop("_id", None)
    return pet


@router.get("/pets")
async def get_my_pets(request: Request):
    """Get current user's pets"""
    user = await get_current_user(request, db)
    pets = await db.pets.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(50)
    return pets


@router.get("/pets/user/{user_id}")
async def get_user_pets(user_id: str, request: Request):
    """Get pets for a specific user (visible to carers)"""
    await get_current_user(request, db)
    pets = await db.pets.find(
        {"user_id": user_id},
        {"_id": 0}
    ).to_list(50)
    return pets


@router.put("/pets/{pet_id}")
async def update_pet(pet_id: str, request: Request):
    """Update a pet"""
    user = await get_current_user(request, db)
    data = await request.json()

    allowed = ['name', 'species', 'breed', 'size', 'age', 'sex', 'photo', 'notes']
    update_data = {k: v for k, v in data.items() if k in allowed}
    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await db.pets.update_one(
        {"pet_id": pet_id, "user_id": user["user_id"]},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")

    updated = await db.pets.find_one({"pet_id": pet_id}, {"_id": 0})
    return updated


@router.delete("/pets/{pet_id}")
async def delete_pet(pet_id: str, request: Request):
    """Delete a pet"""
    user = await get_current_user(request, db)
    result = await db.pets.delete_one({"pet_id": pet_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mascota no encontrada")
    return {"message": "Mascota eliminada"}


# ============= PROFILE PHOTO =============

@router.post("/profile/upload-photo")
async def upload_profile_photo(file: UploadFile = File(...), request: Request = None):
    """Upload/update profile photo"""
    user = await get_current_user(request, db)

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imagenes")

    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"profile_{uuid.uuid4().hex[:16]}.{ext}"
    filepath = UPLOADS_DIR / "profiles" / filename
    (UPLOADS_DIR / "profiles").mkdir(exist_ok=True)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar los 5MB")

    with open(filepath, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/profiles/{filename}"
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"picture": photo_url}}
    )
    return {"url": photo_url}



@router.put("/profile/update")
async def update_profile(request: Request):
    """Update current user's profile (any role)"""
    user = await get_current_user(request, db)
    data = await request.json()
    allowed_fields = ['name', 'phone', 'address', 'comuna', 'emergency_contact', 'emergency_phone',
                      'housing_type', 'has_yard', 'yard_description', 'has_own_pets',
                      'own_pets_description', 'additional_info']
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    if update_data:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": update_data})
    return {"message": "Perfil actualizado"}


# ============= VERIFICATION DOCUMENTS =============

@router.post("/verification/upload")
async def upload_verification_document(
    file: UploadFile = File(...),
    request: Request = None,
    doc_type: str = "id_front"
):
    """Upload verification document (id_front, id_back, selfie, background_certificate)"""
    user = await get_current_user(request, db)

    allowed_types = ["id_front", "id_back", "selfie", "background_certificate"]
    if doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Tipo de documento no valido. Use: {', '.join(allowed_types)}")

    # Check file type - allow images and PDFs for certificates
    is_image = file.content_type.startswith("image/")
    is_pdf = file.content_type == "application/pdf"
    
    if doc_type == "background_certificate":
        if not (is_image or is_pdf):
            raise HTTPException(status_code=400, detail="Solo se permiten imagenes o PDF")
    else:
        if not is_image:
            raise HTTPException(status_code=400, detail="Solo se permiten imagenes")

    ext = file.filename.split(".")[-1] if "." in file.filename else ("pdf" if is_pdf else "jpg")
    filename = f"verify_{doc_type}_{user['user_id']}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = UPLOADS_DIR / "verification" / filename
    (UPLOADS_DIR / "verification").mkdir(exist_ok=True)

    content = await file.read()
    max_size = 10 * 1024 * 1024  # 10MB for certificates
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="El archivo no puede superar los 10MB")

    with open(filepath, "wb") as f:
        f.write(content)

    return {"url": f"/uploads/verification/{filename}", "doc_type": doc_type}


# ============= SOS ENDPOINT =============

@router.get("/sos/info")
async def get_sos_info(request: Request):
    """Get SOS emergency info for carers - includes schedule availability check"""
    await get_current_user(request, db)
    config = await db.sos_config.find_one({}, {"_id": 0})
    if not config or not config.get("active"):
        return {"active": False}
    
    # Check if current time is within schedule
    # Use Chile timezone (UTC-3 or UTC-4 depending on DST)
    from datetime import timedelta
    chile_offset = timedelta(hours=-3)  # Chile summer time
    now_chile = datetime.now(timezone.utc) + chile_offset
    current_hour = now_chile.hour
    
    start_hour = config.get("start_hour", 8)
    end_hour = config.get("end_hour", 20)
    
    is_available = start_hour <= current_hour < end_hour
    
    return {
        **config,
        "is_available": is_available,
        "current_hour": current_hour,
        "schedule_text": f"{start_hour}:00 - {end_hour}:00 hrs"
    }


# ============= REQUEST ENDPOINTS =============

@router.post("/requests")
async def create_request(request_data: RequestCreate, request: Request):
    """Create service request"""
    user = await get_current_user(request, db)
    # Sin restricción de suscripción para clientes

    request_id = f"req_{uuid.uuid4().hex[:12]}"
    request_obj = {
        "request_id": request_id,
        "user_id": user["user_id"],
        **request_data.model_dump(),
        "status": "new",
        "created_at": datetime.now(timezone.utc)
    }
    await db.requests.insert_one(request_obj)
    request_obj.pop("_id", None)
    return request_obj


@router.get("/requests")
async def get_my_requests(request: Request):
    """Get user's requests"""
    user = await get_current_user(request, db)
    requests = await db.requests.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return requests
