from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid, random, string, io
import httpx, os, logging, asyncio
import bcrypt as bcrypt_lib

from database import db
from auth import get_current_user, require_admin
from routes.notification_routes import create_notification

router = APIRouter(prefix="/admin")


import unicodedata
import re

VALID_AMENITIES = [
    'Acceso silla de ruedas', 'Acompañamiento', 'Aire acondicionado', 'Alimentación especial',
    'Áreas verdes', 'Calefacción', 'Enfermería', 'Estacionamiento',
    'Habitación privada', 'Jardín', 'Kinesiología', 'Lavandería',
    'Sala de estar', 'Terapia ocupacional', 'Terraza', 'WiFi'
]

def _normalize_text(text):
    """Remove accents, lowercase, strip extra spaces"""
    text = text.strip().lower()
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'\s+', ' ', text)
    return text

_AMENITY_MAP = {_normalize_text(a): a for a in VALID_AMENITIES}

def normalize_amenities(raw_list):
    """Match raw amenity strings to valid ones using fuzzy matching"""
    result = []
    for raw in raw_list:
        norm = _normalize_text(raw)
        # Exact normalized match
        if norm in _AMENITY_MAP:
            result.append(_AMENITY_MAP[norm])
            continue
        # Partial / contains match
        matched = False
        for key, valid in _AMENITY_MAP.items():
            if norm in key or key in norm:
                result.append(valid)
                matched = True
                break
        if not matched:
            # Check if any word significantly overlaps
            for key, valid in _AMENITY_MAP.items():
                norm_words = set(norm.split())
                key_words = set(key.split())
                overlap = norm_words & key_words
                if len(overlap) >= 1 and len(overlap) / max(len(key_words), 1) >= 0.5:
                    result.append(valid)
                    matched = True
                    break
        if not matched:
            # Keep as-is if no match found
            result.append(raw.strip())
    # Deduplicate preserving order
    seen = set()
    deduped = []
    for a in result:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return deduped


class PlanCreateUpdate(BaseModel):
    name: str
    duration_months: int
    price_clp: int
    features: List[str] = []
    popular: bool = False


# ============= PROVIDER MANAGEMENT =============

@router.get("/providers/pending")
async def get_pending_providers(request: Request):
    """Get providers awaiting approval"""
    user = await get_current_user(request, db)
    await require_admin(user)
    providers = await db.providers.find({"approved": False}, {"_id": 0}).to_list(100)
    return providers


@router.get("/providers/all")
async def get_all_providers(request: Request):
    """Get all providers for admin"""
    user = await get_current_user(request, db)
    await require_admin(user)
    providers = await db.providers.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return providers


@router.post("/providers/{provider_id}/approve")
async def approve_provider(provider_id: str, request: Request):
    """Approve provider"""
    user = await get_current_user(request, db)
    await require_admin(user)

    result = await db.providers.update_one(
        {"provider_id": provider_id},
        {"$set": {"approved": True, "approved_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    provider = await db.providers.find_one({"provider_id": provider_id})
    if provider:
        await create_notification(
            user_id=provider["user_id"],
            title="¡Tu perfil fue aprobado!",
            message="Tu perfil de proveedor ha sido aprobado. Ya apareces en las búsquedas.",
            notification_type="provider_approved"
        )
    return {"message": "Proveedor aprobado"}


@router.post("/providers/{provider_id}/reject")
async def reject_provider(provider_id: str, request: Request):
    """Reject provider"""
    user = await get_current_user(request, db)
    await require_admin(user)

    body = await request.json()
    reason = body.get("reason", "No cumple con los requisitos")

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    await db.providers.delete_one({"provider_id": provider_id})
    await db.users.update_one(
        {"user_id": provider["user_id"]},
        {"$set": {"role": "user"}}
    )

    await create_notification(
        user_id=provider["user_id"],
        title="Perfil rechazado",
        message=f"Tu perfil de proveedor fue rechazado. Razón: {reason}",
        notification_type="provider_rejected"
    )
    return {"message": "Proveedor rechazado"}


@router.post("/providers/{provider_id}/verify")
async def verify_provider(provider_id: str, request: Request):
    """Mark provider as verified"""
    user = await get_current_user(request, db)
    await require_admin(user)

    result = await db.providers.update_one(
        {"provider_id": provider_id},
        {"$set": {"verified": True, "verified_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    provider = await db.providers.find_one({"provider_id": provider_id})
    if provider:
        await create_notification(
            user_id=provider["user_id"],
            title="¡Cuenta verificada!",
            message="Tu cuenta ha sido verificada. Ahora tienes el badge de proveedor verificado.",
            notification_type="provider_verified"
        )
    return {"message": "Proveedor verificado"}


@router.post("/providers/{provider_id}/unverify")
async def unverify_provider(provider_id: str, request: Request):
    """Remove verified badge"""
    user = await get_current_user(request, db)
    await require_admin(user)

    result = await db.providers.update_one(
        {"provider_id": provider_id},
        {"$set": {"verified": False, "verified_at": None}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return {"message": "Verificación removida"}



@router.post("/providers/{provider_id}/toggle-featured")
async def toggle_featured(provider_id: str, request: Request):
    """Admin toggle featured status (bypasses rating restriction)"""
    user = await get_current_user(request, db)
    await require_admin(user)
    provider = await db.providers.find_one({"provider_id": provider_id}, {"_id": 0, "is_featured_admin": 1})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    new_val = not provider.get("is_featured_admin", False)
    await db.providers.update_one({"provider_id": provider_id}, {"$set": {"is_featured_admin": new_val}})
    return {"is_featured_admin": new_val}


@router.post("/providers/{provider_id}/toggle-subscribed")
async def toggle_subscribed(provider_id: str, request: Request):
    """Admin toggle subscribed status (bypasses rating restriction)"""
    user = await get_current_user(request, db)
    await require_admin(user)
    provider = await db.providers.find_one({"provider_id": provider_id}, {"_id": 0, "is_subscribed": 1})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    new_val = not provider.get("is_subscribed", False)
    await db.providers.update_one({"provider_id": provider_id}, {"$set": {"is_subscribed": new_val}})
    return {"is_subscribed": new_val}



# ============= STATS & METRICS =============

@router.get("/stats")
async def get_admin_stats(request: Request):
    """Get admin dashboard stats"""
    user = await get_current_user(request, db)
    await require_admin(user)

    total_users = await db.users.count_documents({})
    total_providers = await db.providers.count_documents({"approved": True})
    pending_providers = await db.providers.count_documents({"approved": False})
    verified_providers = await db.providers.count_documents({"verified": True})
    active_subscriptions = await db.providers.count_documents({"plan_active": True, "plan_type": {"$in": ["destacado", "premium", "premium_plus"]}})
    total_reviews = await db.reviews.count_documents({})

    return {
        "total_users": total_users,
        "total_providers": total_providers,
        "pending_providers": pending_providers,
        "verified_providers": verified_providers,
        "active_subscriptions": active_subscriptions,
        "total_reviews": total_reviews
    }


@router.get("/metrics")
async def get_admin_metrics(request: Request):
    """Get time-series metrics for admin dashboard charts"""
    user = await get_current_user(request, db)
    await require_admin(user)

    months = []
    now = datetime.now(timezone.utc)
    for i in range(5, -1, -1):
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if i > 0:
            m = month_start.month - i
            y = month_start.year
            while m <= 0:
                m += 12
                y -= 1
            month_start = month_start.replace(year=y, month=m)

        next_month = month_start.month + 1
        next_year = month_start.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        month_end = month_start.replace(year=next_year, month=next_month)

        users_count = await db.users.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })
        providers_count = await db.providers.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })
        subs_count = await db.subscriptions.count_documents({
            "start_date": {"$gte": month_start, "$lt": month_end}
        })
        reviews_count = await db.reviews.count_documents({
            "created_at": {"$gte": month_start, "$lt": month_end}
        })

        month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        months.append({
            "month": month_names[month_start.month - 1],
            "users": users_count,
            "providers": providers_count,
            "subscriptions": subs_count,
            "reviews": reviews_count
        })

    return months


# ============= PLAN MANAGEMENT =============

@router.get("/plans")
async def get_all_plans(request: Request):
    """Get all plans for admin"""
    user = await get_current_user(request, db)
    await require_admin(user)
    plans = await db.subscription_plans.find({}, {"_id": 0}).sort("price_clp", 1).to_list(50)
    return plans


@router.post("/plans")
async def create_plan(data: PlanCreateUpdate, request: Request):
    """Create a new subscription plan"""
    user = await get_current_user(request, db)
    await require_admin(user)

    plan_id = f"plan_{uuid.uuid4().hex[:8]}"
    plan = {
        "plan_id": plan_id,
        **data.model_dump(),
        "active": True,
        "created_at": datetime.now(timezone.utc)
    }
    await db.subscription_plans.insert_one(plan)
    plan.pop("_id", None)
    return plan


@router.put("/plans/{plan_id}")
async def update_plan(plan_id: str, data: PlanCreateUpdate, request: Request):
    """Update a subscription plan"""
    user = await get_current_user(request, db)
    await require_admin(user)

    result = await db.subscription_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {**data.model_dump(), "updated_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    updated = await db.subscription_plans.find_one({"plan_id": plan_id}, {"_id": 0})
    return updated


@router.post("/plans/{plan_id}/toggle")
async def toggle_plan(plan_id: str, request: Request):
    """Activate/deactivate a plan"""
    user = await get_current_user(request, db)
    await require_admin(user)

    plan = await db.subscription_plans.find_one({"plan_id": plan_id})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    new_active = not plan.get("active", True)
    await db.subscription_plans.update_one(
        {"plan_id": plan_id},
        {"$set": {"active": new_active}}
    )
    return {"message": f"Plan {'activado' if new_active else 'desactivado'}", "active": new_active}


@router.delete("/plans/{plan_id}")
async def delete_plan(plan_id: str, request: Request):
    """Delete a subscription plan"""
    user = await get_current_user(request, db)
    await require_admin(user)

    result = await db.subscription_plans.delete_one({"plan_id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    return {"message": "Plan eliminado"}


# ============= MAKE ADMIN =============

@router.post("/make-admin")
async def make_admin(request: Request):
    """Make a user admin by email"""
    body = await request.json()
    email = body.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email requerido")

    admin_count = await db.users.count_documents({"role": "admin"})
    if admin_count > 0:
        user = await get_current_user(request, db)
        await require_admin(user)

    result = await db.users.update_one(
        {"email": email},
        {"$set": {"role": "admin"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"message": f"Usuario {email} ahora es admin"}


# ============= SOS CONFIGURATION =============

@router.get("/sos")
async def get_sos_config(request: Request):
    """Get SOS configuration"""
    user = await get_current_user(request, db)
    await require_admin(user)
    config = await db.sos_config.find_one({}, {"_id": 0})
    if not config:
        return {"active": False, "phone": "", "schedule": "", "vet_name": "", "start_hour": 8, "end_hour": 20}
    return config


@router.put("/sos")
async def update_sos_config(request: Request):
    """Update SOS configuration"""
    user = await get_current_user(request, db)
    await require_admin(user)
    data = await request.json()

    allowed = ['phone', 'schedule', 'vet_name', 'active', 'start_hour', 'end_hour']
    update_data = {k: v for k, v in data.items() if k in allowed}
    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.sos_config.update_one(
        {},
        {"$set": update_data},
        upsert=True
    )
    config = await db.sos_config.find_one({}, {"_id": 0})
    return config


# --- Create Residencia ---

class ResidenciaCreate(BaseModel):
    business_name: str
    email: str
    password: Optional[str] = None
    phone: Optional[str] = ""
    address: Optional[str] = ""
    region: Optional[str] = ""
    comuna: Optional[str] = ""
    website: Optional[str] = ""
    facebook: Optional[str] = ""
    instagram: Optional[str] = ""
    place_id: Optional[str] = ""
    service_type: Optional[str] = "residencias"
    price_from: Optional[int] = 0
    services: Optional[list] = None
    partner_provider_id: Optional[str] = ""

def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def _hash_password(password: str) -> str:
    return bcrypt_lib.hashpw(password.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8')

def _hash_password_fast(password: str) -> str:
    return bcrypt_lib.hashpw(password.encode('utf-8'), bcrypt_lib.gensalt(rounds=6)).decode('utf-8')

@router.post("/residencias/create")
async def create_residencia(data: ResidenciaCreate, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)
    
    # Check for partner or existing user
    existing = None
    if data.partner_provider_id:
        partner = await db.providers.find_one({"provider_id": data.partner_provider_id})
        if partner:
            existing = await db.users.find_one({"user_id": partner["user_id"]})
            if not data.email:
                data.email = existing["email"] if existing else ""
    
    if not existing:
        existing = await db.users.find_one({"email": data.email})
    
    provider_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    if existing:
        user_id = existing["user_id"]
    else:
        password = data.password or generate_password()
        user_id = str(uuid.uuid4())
        user = {
            "user_id": user_id,
            "email": data.email,
            "name": data.business_name,
            "role": "provider",
            "hashed_password": _hash_password(password),
            "created_at": now.isoformat(),
            "active": True,
        }
        await db.users.insert_one(user)
    
    provider = {
        "provider_id": provider_id,
        "user_id": user_id,
        "business_name": data.business_name,
        "phone": data.phone or "",
        "whatsapp": data.phone or "",
        "address": data.address or "",
        "region": data.region or "",
        "comuna": data.comuna or "",
        "description": "",
        "services": data.services if data.services else [{"service_type": data.service_type or "residencias", "price_from": data.price_from or 0, "description": ""}],
        "photos": [],
        "gallery": [],
        "amenities": [],
        "social_links": {
            k: v for k, v in {
                "website": data.website or "",
                "facebook": data.facebook or "",
                "instagram": data.instagram or "",
            }.items() if v
        },
        "personal_info": {"housing_type": "residencia"},
        "rating": 0,
        "total_reviews": 0,
        "approved": True,
        "verified": False,
        "latitude": 0,
        "longitude": 0,
        "place_id": data.place_id or "",
        "coverage_zone": "10",
        "created_at": now,
        "approved_at": now,
    }
    await db.providers.insert_one(provider)
    
    # Auto-fetch Google data if place_id is provided
    if data.place_id:
        try:
            api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
            if api_key:
                google_data = await fetch_google_place_data(data.place_id, api_key)
                if google_data:
                    await db.providers.update_one(
                        {"provider_id": provider_id},
                        {"$set": {
                            "google_rating": google_data["google_rating"],
                            "google_total_reviews": google_data["google_total_reviews"],
                            "google_reviews": google_data["google_reviews"],
                            "rating": google_data["google_rating"] or 0,
                            "total_reviews": google_data["google_total_reviews"],
                            "latitude": google_data.get("latitude", 0),
                            "longitude": google_data.get("longitude", 0),
                        }}
                    )
        except Exception as e:
            logging.error(f"Error fetching Google data for {data.business_name}: {e}")
    
    result = {
        "provider_id": provider_id,
        "user_id": user_id,
        "business_name": data.business_name,
        "email": data.email,
        "status": "created"
    }
    if existing:
        result["note"] = "Nueva sede agregada a empresa existente"
    else:
        result["password"] = password
    return result

class BulkResidenciaItem(BaseModel):
    business_name: str
    email: str
    phone: Optional[str] = ""
    whatsapp: Optional[str] = ""
    address: Optional[str] = ""
    comuna: Optional[str] = ""
    description: Optional[str] = ""
    service_type: Optional[str] = "residencias"
    price_from: Optional[int] = 0
    place_id: Optional[str] = ""

class BulkResidenciaCreate(BaseModel):
    residencias: List[BulkResidenciaItem]

@router.post("/residencias/bulk-create")
async def bulk_create_residencias(data: BulkResidenciaCreate, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)
    
    results = []
    now = datetime.now(timezone.utc)
    
    for item in data.residencias:
        existing = await db.users.find_one({"email": item.email})
        if existing:
            results.append({"business_name": item.business_name, "email": item.email, "status": "error", "detail": "Email ya registrado"})
            continue
        
        password = generate_password()
        user_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())
        
        user = {
            "user_id": user_id,
            "email": item.email,
            "name": item.business_name,
            "role": "provider",
            "hashed_password": _hash_password_fast(password),
            "created_at": now.isoformat(),
            "active": True,
        }
        await db.users.insert_one(user)
        
        provider = {
            "provider_id": provider_id,
            "user_id": user_id,
            "business_name": item.business_name,
            "phone": item.phone or "",
            "whatsapp": item.whatsapp or "",
            "address": item.address or "",
            "comuna": item.comuna or "",
            "description": item.description or "",
            "services": [{"service_type": item.service_type or "residencias", "price_from": item.price_from or 0, "description": ""}],
            "photos": [],
            "gallery": [],
            "amenities": [],
            "social_links": {},
            "personal_info": {},
            "rating": 0,
            "total_reviews": 0,
            "approved": True,
            "verified": False,
            "latitude": 0,
            "longitude": 0,
            "coverage_zone": "10",
            "place_id": item.place_id or "",
            "created_at": now,
            "approved_at": now,
        }
        await db.providers.insert_one(provider)
        
        # Auto-fetch Google data if place_id is provided
        if item.place_id:
            try:
                api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
                if api_key:
                    google_data = await fetch_google_place_data(item.place_id, api_key)
                    if google_data:
                        await db.providers.update_one(
                            {"provider_id": provider_id},
                            {"$set": {
                                "google_rating": google_data["google_rating"],
                                "google_total_reviews": google_data["google_total_reviews"],
                                "google_reviews": google_data["google_reviews"],
                                "rating": google_data["google_rating"] or 0,
                                "total_reviews": google_data["google_total_reviews"],
                                "latitude": google_data.get("latitude", 0),
                                "longitude": google_data.get("longitude", 0),
                            }}
                        )
            except Exception as e:
                logging.error(f"Error fetching Google data for {item.business_name}: {e}")
        
        results.append({
            "business_name": item.business_name,
            "email": item.email,
            "password": password,
            "provider_id": provider_id,
            "status": "created"
        })
    
    created = len([r for r in results if r["status"] == "created"])
    errors = len([r for r in results if r["status"] == "error"])
    return {"total": len(results), "created": created, "errors": errors, "results": results}


@router.post("/residencias/upload-excel")
async def upload_excel_residencias(request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request, db)
    await require_admin(user)

    import pandas as pd
    content = await file.read()
    filename = (file.filename or "").lower()

    # Parse CSV or XLSX
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), encoding="utf-8", dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(io.BytesIO(content), dtype=str, keep_default_na=False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer archivo: {str(e)}")

    # Normalize column names to lowercase stripped
    df.columns = [c.strip().lower() for c in df.columns]

    # Build column map for flexible naming
    col_map = {}
    for col in df.columns:
        if col in ("codigo", "código", "id", "code"):
            col_map["codigo"] = col
        elif col in ("nombre residencia", "nombre_residencia", "nombre", "business_name", "residencia"):
            col_map["business_name"] = col
        elif col in ("correo", "email", "mail", "correo electrónico", "correo electronico"):
            col_map["email"] = col
        elif col in ("telefono", "teléfono", "phone", "fono"):
            col_map["phone"] = col
        elif col in ("direccion", "dirección", "address"):
            col_map["address"] = col
        elif col == "comuna":
            col_map["comuna"] = col
        elif col == "ciudad":
            col_map["ciudad"] = col
        elif col in ("descripcion", "descripción", "description"):
            col_map["description"] = col
        elif col == "rating":
            col_map["rating"] = col
        elif col == "website":
            col_map["website"] = col
        elif col in ("latitud", "latitude"):
            col_map["latitude"] = col
        elif col in ("longitud", "longitude"):
            col_map["longitude"] = col
        elif col == "imagen_1":
            col_map["imagen_1"] = col
        elif col == "imagen_2":
            col_map["imagen_2"] = col
        elif col == "imagen_3":
            col_map["imagen_3"] = col
        elif col in ("palabras clave", "keywords", "amenidades"):
            col_map["amenities"] = col
        elif col == "facebook":
            col_map["facebook"] = col
        elif col == "instagram":
            col_map["instagram"] = col
        elif col in ("cant reseñas", "cant_resenas", "total_reviews"):
            col_map["total_reviews"] = col
        elif col in ("precio", "price", "precio_desde", "price_from"):
            col_map["price_from"] = col
        elif col == "place_id":
            col_map["place_id"] = col
        elif col in ("tipo", "tipo servicio", "service_type", "categoria"):
            col_map["service_type"] = col
        elif col in ("servicios", "services"):
            col_map["servicios"] = col
        elif col == "logo":
            col_map["logo"] = col
        elif col in ("tipo personal", "staff_type"):
            col_map["staff_type"] = col
        elif col in ("region", "región"):
            col_map["region"] = col
        elif col in ("disponibilidad", "availability", "horario_atencion", "horario"):
            col_map["disponibilidad"] = col
        elif col in ("video promocional", "video", "youtube", "youtube_video_url"):
            col_map["video"] = col
        elif col == "whatsapp":
            col_map["whatsapp"] = col
        elif col in ("tipo_instalacion", "tipo instalacion", "housing_type"):
            col_map["housing_type"] = col
        elif col in ("bio", "descripcion_adicional"):
            col_map["bio"] = col
        elif col in ("precio_residencias", "precio residencias"):
            col_map["precio_residencias"] = col
        elif col in ("desc_residencias", "descripcion residencias"):
            col_map["desc_residencias"] = col
        elif col in ("precio_cuidado_domicilio", "precio cuidado domicilio"):
            col_map["precio_cuidado_domicilio"] = col
        elif col in ("desc_cuidado_domicilio", "descripcion cuidado domicilio"):
            col_map["desc_cuidado_domicilio"] = col
        elif col in ("precio_salud_mental", "precio salud mental"):
            col_map["precio_salud_mental"] = col
        elif col in ("desc_salud_mental", "descripcion salud mental"):
            col_map["desc_salud_mental"] = col
        elif col.startswith("imagen_premium_"):
            col_map[col] = col

    if "business_name" not in col_map:
        raise HTTPException(status_code=400, detail="El archivo debe tener la columna 'nombre residencia' o 'nombre'")

    def get_val(row, key):
        if key in col_map:
            v = str(row.get(col_map[key], "")).strip()
            return v if v and v != "nan" else ""
        return ""

    def parse_float(val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return 0.0

    def parse_int(val):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return 0

    # Pre-fetch all existing emails and codigos to avoid per-row queries
    all_emails_in_csv = set()
    all_codigos_in_csv = set()
    rows_data = []
    for _, row in df.iterrows():
        bname = get_val(row, "business_name")
        if not bname:
            continue
        email = get_val(row, "email")
        codigo = get_val(row, "codigo")
        if codigo and codigo.upper() in ("#N/A", "N/A", "NA", "NULL", "NONE", "-"):
            codigo = ""
        short_id = uuid.uuid4().hex[:8]
        if not email:
            slug = bname.lower().replace(" ", "-")[:30]
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            email = f"{slug}-{short_id}@senioradvisor.cl"
        all_emails_in_csv.add(email)
        if codigo:
            all_codigos_in_csv.add(codigo)
        rows_data.append((row, bname, email, codigo))

    # Batch check existing emails
    existing_emails_docs = await db.users.find(
        {"email": {"$in": list(all_emails_in_csv)}},
        {"_id": 0, "email": 1}
    ).to_list(len(all_emails_in_csv))
    existing_emails = {d["email"] for d in existing_emails_docs}

    # Batch check existing codigos
    existing_codigo_docs = []
    if all_codigos_in_csv:
        existing_codigo_docs = await db.providers.find(
            {"codigo": {"$in": list(all_codigos_in_csv)}},
            {"_id": 0, "codigo": 1, "user_id": 1, "provider_id": 1}
        ).to_list(len(all_codigos_in_csv))
    existing_codigo_map = {d["codigo"]: d["user_id"] for d in existing_codigo_docs}

    results = []
    users_to_insert = []
    providers_to_insert = []
    providers_to_update = []
    users_to_update = []
    now = datetime.now(timezone.utc)

    # Also fetch existing provider data for updates by email
    existing_users_docs = await db.users.find(
        {"email": {"$in": list(all_emails_in_csv)}},
        {"_id": 0, "email": 1, "user_id": 1}
    ).to_list(len(all_emails_in_csv))
    existing_user_map = {d["email"]: d["user_id"] for d in existing_users_docs}

    # Generate next codigo sequence
    last_provider = await db.providers.find(
        {"codigo": {"$exists": True, "$regex": "^SA-"}},
        {"_id": 0, "codigo": 1}
    ).sort("codigo", -1).to_list(1)
    next_seq = 1
    if last_provider:
        try:
            next_seq = int(last_provider[0]["codigo"].split("-")[1]) + 1
        except (ValueError, IndexError):
            next_seq = 1

    for row, bname, email, codigo in rows_data:
        phone = get_val(row, "phone")
        whatsapp = get_val(row, "whatsapp") or phone
        address = get_val(row, "address")
        comuna = get_val(row, "comuna") or get_val(row, "ciudad")
        description = get_val(row, "description")
        region = get_val(row, "region")
        rating = parse_float(get_val(row, "rating"))
        total_reviews = parse_int(get_val(row, "total_reviews"))
        latitude = parse_float(get_val(row, "latitude"))
        longitude = parse_float(get_val(row, "longitude"))
        website = get_val(row, "website")
        facebook = get_val(row, "facebook")
        instagram = get_val(row, "instagram")
        video = get_val(row, "video")
        place_id = get_val(row, "place_id")
        logo = get_val(row, "logo")
        staff_type = get_val(row, "staff_type")
        disponibilidad = get_val(row, "disponibilidad")
        housing_type = get_val(row, "housing_type") or "residencia"
        bio = get_val(row, "bio")

        gallery = []
        for img_key in ["imagen_1", "imagen_2", "imagen_3"]:
            img_url = get_val(row, img_key)
            if img_url and img_url.startswith("http"):
                gallery.append({
                    "photo_id": f"csv_{uuid.uuid4().hex[:8]}",
                    "url": img_url,
                    "thumbnail_url": img_url,
                    "uploaded_at": now.isoformat(),
                })

        premium_gallery = []
        for i in range(1, 11):
            pg_key = f"imagen_premium_{i}"
            pg_url = get_val(row, pg_key)
            if pg_url and pg_url.startswith("http"):
                premium_gallery.append({
                    "photo_id": f"csv_p_{uuid.uuid4().hex[:8]}",
                    "url": pg_url,
                    "thumbnail_url": pg_url,
                    "uploaded_at": now.isoformat(),
                })

        amenities_str = get_val(row, "amenities") or get_val(row, "servicios")
        amenities_raw = [a.strip() for a in amenities_str.split(",") if a.strip()] if amenities_str else []
        amenities = normalize_amenities(amenities_raw)

        social_links = {}
        if website:
            social_links["website"] = website
        if facebook:
            social_links["facebook"] = facebook
        if instagram:
            social_links["instagram"] = instagram
        if video:
            social_links["video"] = video

        service_type_raw = get_val(row, "service_type")
        price_from = parse_int(get_val(row, "price_from"))

        services = []
        p_res = parse_int(get_val(row, "precio_residencias"))
        d_res = get_val(row, "desc_residencias")
        if p_res or d_res:
            services.append({"service_type": "residencias", "price_from": p_res, "description": d_res})
        p_dom = parse_int(get_val(row, "precio_cuidado_domicilio"))
        d_dom = get_val(row, "desc_cuidado_domicilio")
        if p_dom or d_dom:
            services.append({"service_type": "cuidado-domicilio", "price_from": p_dom, "description": d_dom})
        p_sal = parse_int(get_val(row, "precio_salud_mental"))
        d_sal = get_val(row, "desc_salud_mental")
        if p_sal or d_sal:
            services.append({"service_type": "salud-mental", "price_from": p_sal, "description": d_sal})
        if not services:
            service_type = "residencias"
            if service_type_raw:
                st_lower = service_type_raw.lower()
                if "domicilio" in st_lower:
                    service_type = "cuidado-domicilio"
                elif "mental" in st_lower or "psico" in st_lower:
                    service_type = "salud-mental"
            if price_from:
                services.append({"service_type": service_type, "price_from": price_from, "description": ""})

        if codigo and codigo in existing_codigo_map:
            # UPDATE by codigo
            existing_uid = existing_codigo_map[codigo]

            update_fields = {"business_name": bname}
            if phone: update_fields["phone"] = phone
            if whatsapp: update_fields["whatsapp"] = whatsapp
            if address: update_fields["address"] = address
            if comuna: update_fields["comuna"] = comuna
            if region: update_fields["region"] = region
            if description: update_fields["description"] = description
            if services: update_fields["services"] = services
            if gallery: update_fields["gallery"] = gallery
            if premium_gallery: update_fields["premium_gallery"] = premium_gallery
            if amenities: update_fields["amenities"] = amenities
            if social_links: update_fields["social_links"] = social_links
            if latitude: update_fields["latitude"] = latitude
            if longitude: update_fields["longitude"] = longitude
            if place_id: update_fields["place_id"] = place_id
            if video: update_fields["youtube_video_url"] = video
            if housing_type and housing_type != "residencia":
                update_fields.setdefault("personal_info", {})["housing_type"] = housing_type
            if disponibilidad:
                update_fields.setdefault("personal_info", {})["daily_availability"] = disponibilidad
            if bio:
                update_fields.setdefault("personal_info", {})["bio"] = bio
            if rating: update_fields["rating"] = rating
            if total_reviews: update_fields["total_reviews"] = total_reviews
            if logo and logo.startswith("http"): update_fields["profile_photo"] = logo
            elif gallery: update_fields["profile_photo"] = gallery[0]["url"]

            providers_to_update.append({"user_id": existing_uid, "update": update_fields})
            users_to_update.append({"user_id": existing_uid, "name": bname})

            results.append({
                "business_name": bname,
                "codigo": codigo,
                "email": email,
                "status": "updated"
            })
            continue

        elif email in existing_emails:
            # UPDATE existing provider
            existing_uid = existing_user_map.get(email)
            if not existing_uid:
                results.append({"business_name": bname, "email": email, "status": "error", "detail": "Usuario existe pero no se encontro user_id"})
                continue

            update_fields = {"business_name": bname}
            if phone: update_fields["phone"] = phone
            if whatsapp: update_fields["whatsapp"] = whatsapp
            if address: update_fields["address"] = address
            if comuna: update_fields["comuna"] = comuna
            if region: update_fields["region"] = region
            if description: update_fields["description"] = description
            if services: update_fields["services"] = services
            if gallery: update_fields["gallery"] = gallery
            if premium_gallery: update_fields["premium_gallery"] = premium_gallery
            if amenities: update_fields["amenities"] = amenities
            if social_links: update_fields["social_links"] = social_links
            if latitude: update_fields["latitude"] = latitude
            if longitude: update_fields["longitude"] = longitude
            if place_id: update_fields["place_id"] = place_id
            if video: update_fields["youtube_video_url"] = video
            if housing_type and housing_type != "residencia":
                update_fields.setdefault("personal_info", {})["housing_type"] = housing_type
            if disponibilidad:
                update_fields.setdefault("personal_info", {})["daily_availability"] = disponibilidad
            if bio:
                update_fields.setdefault("personal_info", {})["bio"] = bio
            if rating: update_fields["rating"] = rating
            if total_reviews: update_fields["total_reviews"] = total_reviews
            if logo and logo.startswith("http"): update_fields["profile_photo"] = logo
            elif gallery: update_fields["profile_photo"] = gallery[0]["url"]

            providers_to_update.append({"user_id": existing_uid, "update": update_fields})
            users_to_update.append({"user_id": existing_uid, "name": bname})

            results.append({
                "business_name": bname,
                "email": email,
                "status": "updated"
            })
            continue

        # Generate credentials for NEW provider
        password = generate_password()
        user_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())
        new_codigo = f"SA-{next_seq:04d}"
        next_seq += 1

        users_to_insert.append({
            "user_id": user_id,
            "email": email,
            "name": bname,
            "role": "provider",
            "hashed_password": _hash_password_fast(password),
            "created_at": now.isoformat(),
            "active": True,
        })

        providers_to_insert.append({
            "provider_id": provider_id,
            "user_id": user_id,
            "codigo": new_codigo,
            "business_name": bname,
            "phone": phone,
            "whatsapp": whatsapp,
            "address": address,
            "comuna": comuna,
            "region": region,
            "description": description,
            "services": services,
            "photos": [],
            "gallery": gallery,
            "premium_gallery": premium_gallery,
            "amenities": amenities,
            "social_links": social_links,
            "personal_info": {
                "housing_type": housing_type,
                "daily_availability": disponibilidad,
                "bio": bio,
            },
            "rating": rating,
            "total_reviews": total_reviews,
            "approved": True,
            "verified": False,
            "latitude": latitude,
            "longitude": longitude,
            "place_id": place_id,
            "logo": logo,
            "staff_type": staff_type,
            "youtube_video_url": video,
            "coverage_zone": "10",
            "created_at": now,
            "approved_at": now,
            "profile_photo": logo if logo and logo.startswith("http") else (gallery[0]["url"] if gallery else ""),
        })

        # Mark as existing to handle intra-file duplicates
        existing_emails.add(email)

        results.append({
            "business_name": bname,
            "email": email,
            "password": password,
            "provider_id": provider_id,
            "codigo": new_codigo,
            "status": "created"
        })

    # Batch insert all at once
    if users_to_insert:
        await db.users.insert_many(users_to_insert)
    if providers_to_insert:
        await db.providers.insert_many(providers_to_insert)

    # Batch update providers using bulk_write
    from pymongo import UpdateOne
    if providers_to_update:
        provider_ops = [UpdateOne({"user_id": upd["user_id"]}, {"$set": upd["update"]}) for upd in providers_to_update]
        await db.providers.bulk_write(provider_ops, ordered=False)
    if users_to_update:
        user_ops = [UpdateOne({"user_id": u["user_id"]}, {"$set": {"name": u["name"]}}) for u in users_to_update]
        await db.users.bulk_write(user_ops, ordered=False)

    # Auto-fetch Google data for new providers with place_id
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if api_key:
        for p in providers_to_insert:
            pid = p.get("place_id", "").strip()
            if pid and not pid.startswith("ChIJtest"):
                try:
                    google_data = await fetch_google_place_data(pid, api_key)
                    if google_data:
                        await db.providers.update_one(
                            {"provider_id": p["provider_id"]},
                            {"$set": {
                                "google_rating": google_data["google_rating"],
                                "google_total_reviews": google_data["google_total_reviews"],
                                "google_reviews": google_data["google_reviews"],
                                "rating": google_data["google_rating"] or 0,
                                "total_reviews": google_data["google_total_reviews"],
                                "latitude": google_data.get("latitude", 0),
                                "longitude": google_data.get("longitude", 0),
                            }}
                        )
                except Exception as e:
                    logging.error(f"Excel Google sync error for {p['business_name']}: {e}")

    created = len([r for r in results if r["status"] == "created"])
    updated = len([r for r in results if r["status"] == "updated"])
    errors = len([r for r in results if r["status"] == "error"])
    return {"total": len(results), "created": created, "updated": updated, "errors": errors, "results": results}


@router.get("/residencias/export-csv")
async def export_residencias_csv(request: Request):
    """Export all providers as CSV with their codigo for re-upload/update"""
    from fastapi.responses import StreamingResponse
    user = await get_current_user(request, db)
    await require_admin(user)

    providers = await db.providers.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)

    # Assign codigos to providers that don't have one
    next_seq = 1
    last_with_code = await db.providers.find(
        {"codigo": {"$exists": True, "$regex": "^SA-"}},
        {"_id": 0, "codigo": 1}
    ).sort("codigo", -1).to_list(1)
    if last_with_code:
        try:
            next_seq = int(last_with_code[0]["codigo"].split("-")[1]) + 1
        except (ValueError, IndexError):
            next_seq = 1

    for p in providers:
        if not p.get("codigo"):
            new_code = f"SA-{next_seq:04d}"
            next_seq += 1
            await db.providers.update_one(
                {"provider_id": p["provider_id"]},
                {"$set": {"codigo": new_code}}
            )
            p["codigo"] = new_code

    # Fetch user emails
    user_ids = [p.get("user_id") for p in providers if p.get("user_id")]
    users_docs = await db.users.find(
        {"user_id": {"$in": user_ids}},
        {"_id": 0, "user_id": 1, "email": 1}
    ).to_list(len(user_ids))
    user_email_map = {u["user_id"]: u["email"] for u in users_docs}

    import csv
    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        "codigo", "nombre", "email", "telefono", "whatsapp", "direccion", "comuna", "region",
        "descripcion", "tipo", "tipo_instalacion", "horario_atencion", "bio", "youtube",
        "place_id", "precio_residencias", "desc_residencias", "precio_cuidado_domicilio",
        "desc_cuidado_domicilio", "precio_salud_mental", "desc_salud_mental", "amenidades",
        "website", "facebook", "instagram", "rating", "cant_resenas",
        "latitud", "longitud", "imagen_1", "imagen_2", "imagen_3"
    ]
    writer.writerow(headers)

    for p in providers:
        email = user_email_map.get(p.get("user_id"), "")
        services = p.get("services", [])
        # Extract prices per service type
        precio_res = ""
        desc_res = ""
        precio_dom = ""
        desc_dom = ""
        precio_sal = ""
        desc_sal = ""
        for svc in services:
            st = svc.get("service_type", "")
            if st == "residencias":
                precio_res = svc.get("price_from", 0) or ""
                desc_res = svc.get("description", "")
            elif st == "cuidado-domicilio":
                precio_dom = svc.get("price_from", 0) or ""
                desc_dom = svc.get("description", "")
            elif st == "salud-mental":
                precio_sal = svc.get("price_from", 0) or ""
                desc_sal = svc.get("description", "")

        social = p.get("social_links", {})
        personal = p.get("personal_info", {})
        gallery = p.get("gallery", [])
        amenities_str = ",".join(p.get("amenities", []))

        def get_gallery_url(gallery, idx):
            if len(gallery) <= idx:
                return ""
            item = gallery[idx]
            if isinstance(item, dict):
                return item.get("url", "")
            return str(item) if item else ""

        row = [
            p.get("codigo", ""),
            p.get("business_name", ""),
            email,
            p.get("phone", ""),
            p.get("whatsapp", ""),
            p.get("address", ""),
            p.get("comuna", ""),
            p.get("region", ""),
            p.get("description", ""),
            services[0].get("service_type", "residencias") if services else "residencias",
            personal.get("housing_type", ""),
            personal.get("daily_availability", ""),
            personal.get("bio", ""),
            p.get("youtube_video_url", "") or social.get("video", ""),
            p.get("place_id", ""),
            precio_res, desc_res,
            precio_dom, desc_dom,
            precio_sal, desc_sal,
            amenities_str,
            social.get("website", ""),
            social.get("facebook", ""),
            social.get("instagram", ""),
            p.get("rating", 0),
            p.get("total_reviews", 0),
            p.get("latitude", 0),
            p.get("longitude", 0),
            get_gallery_url(gallery, 0),
            get_gallery_url(gallery, 1),
            get_gallery_url(gallery, 2),
        ]
        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=residencias_export.csv"}
    )


@router.put("/providers/{provider_id}/credentials")
async def admin_update_provider_credentials(provider_id: str, request: Request):
    """Admin updates email and/or password for a provider"""
    user = await get_current_user(request, db)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Solo admin")
    
    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    body = await request.json()
    new_email = body.get("email", "").strip()
    new_password = body.get("password", "").strip()
    
    update = {}
    if new_email:
        existing = await db.users.find_one({"email": new_email, "user_id": {"$ne": provider["user_id"]}})
        if existing:
            raise HTTPException(status_code=400, detail="Ese email ya está en uso por otra cuenta")
        update["email"] = new_email
    if new_password:
        update["hashed_password"] = _hash_password(new_password)
    
    if update:
        await db.users.update_one({"user_id": provider["user_id"]}, {"$set": update})
    
    return {"status": "ok", "updated_fields": list(update.keys())}




# ============= ADMIN GALLERY & AMENITIES MANAGEMENT =============

@router.get("/providers/{provider_id}/detail")
async def admin_get_provider_detail(provider_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)
    provider = await db.providers.find_one({"provider_id": provider_id}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return provider


@router.post("/providers/{provider_id}/gallery/upload")
async def admin_upload_gallery(provider_id: str, request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request, db)
    await require_admin(user)

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    current_gallery = provider.get("gallery", [])
    if len(current_gallery) >= 3:
        raise HTTPException(status_code=400, detail="Máximo 3 fotos")

    import cloudinary.uploader
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        folder=f"providers/{provider_id}/gallery",
        transformation=[{"quality": "auto", "fetch_format": "auto", "width": 800, "crop": "limit"}]
    )

    photo_record = {
        "photo_id": result["public_id"],
        "url": result["secure_url"],
        "thumbnail_url": result["secure_url"].replace("/upload/", "/upload/w_300,h_200,c_fill,q_auto,f_auto/"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$push": {"gallery": photo_record}},
    )
    return {"message": "Foto subida", "photo": photo_record}


@router.delete("/providers/{provider_id}/gallery/{photo_id:path}")
async def admin_delete_gallery(provider_id: str, photo_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Try delete from Cloudinary
    try:
        import cloudinary.uploader
        cloudinary.uploader.destroy(photo_id, invalidate=True)
    except Exception:
        pass

    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$pull": {"gallery": {"photo_id": photo_id}}},
    )
    return {"message": "Foto eliminada"}


# ============= ADMIN PREMIUM GALLERY =============

@router.post("/providers/{provider_id}/premium-gallery/upload")
async def admin_upload_premium_gallery(provider_id: str, request: Request, file: UploadFile = File(...)):
    user = await get_current_user(request, db)
    await require_admin(user)

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imágenes")

    current_premium = provider.get("premium_gallery", [])
    if len(current_premium) >= 10:
        raise HTTPException(status_code=400, detail="Máximo 10 fotos en slider premium")

    import cloudinary.uploader
    contents = await file.read()
    result = cloudinary.uploader.upload(
        contents,
        folder=f"providers/{provider_id}/premium",
        transformation=[{"quality": "auto", "fetch_format": "auto", "width": 1200, "crop": "limit"}]
    )

    photo_record = {
        "photo_id": result["public_id"],
        "url": result["secure_url"],
        "thumbnail_url": result["secure_url"].replace("/upload/", "/upload/w_400,h_300,c_fill,q_auto,f_auto/"),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$push": {"premium_gallery": photo_record}},
    )
    return {"message": "Foto premium subida", "photo": photo_record}


@router.delete("/providers/{provider_id}/premium-gallery/{photo_id:path}")
async def admin_delete_premium_gallery(provider_id: str, photo_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    # Try delete from Cloudinary
    try:
        import cloudinary.uploader
        cloudinary.uploader.destroy(photo_id, invalidate=True)
    except Exception:
        pass

    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$pull": {"premium_gallery": {"photo_id": photo_id}}},
    )
    return {"message": "Foto premium eliminada"}




@router.put("/providers/{provider_id}/amenities")
async def admin_update_amenities(provider_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)

    body = await request.json()
    amenities = body.get("amenities", [])

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$set": {"amenities": amenities}},
    )
    return {"message": "Amenidades actualizadas", "amenities": amenities}


@router.put("/providers/{provider_id}/profile")
async def admin_update_provider_profile(provider_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)

    body = await request.json()
    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    allowed = ["business_name", "phone", "whatsapp", "address", "region", "comuna", "place_id",
               "social_links", "services", "amenities", "description", "youtube_video_url",
               "personal_info", "latitude", "longitude", "is_featured", "is_subscribed",
               "service_type", "service_comunas", "walking_zones", "coverage_radius_km",
               "profile_photo", "plan_type", "plan_active", "verified"]
    update = {k: v for k, v in body.items() if k in allowed}
    # Map admin toggles to admin-specific fields
    if "is_featured" in update:
        update["is_featured_admin"] = update.pop("is_featured")
    # Auto-activate plan when plan_type is set
    if "plan_type" in update and update["plan_type"] in ("destacado", "premium", "premium_plus"):
        update["plan_active"] = True
    elif "plan_type" in update and not update["plan_type"]:
        update["plan_active"] = False
    if update:
        await db.providers.update_one({"provider_id": provider_id}, {"$set": update})

    # Sync services to separate services collection if updated
    if "services" in update:
        await db.services.delete_many({"provider_id": provider_id})
        for svc in update["services"]:
            service_doc = {
                "service_id": f"serv_{uuid.uuid4().hex[:12]}",
                "provider_id": provider_id,
                "service_type": svc.get("service_type", "residencias"),
                "price_from": svc.get("price_from", 0),
                "description": svc.get("description", ""),
                "sub_prices": svc.get("sub_prices", []),
                "rules": svc.get("rules", ""),
                "pet_sizes": svc.get("pet_sizes", []),
                "created_at": datetime.now(timezone.utc),
            }
            await db.services.insert_one(service_doc)
    
    updated = await db.providers.find_one({"provider_id": provider_id}, {"_id": 0})
    return updated


# ============= GOOGLE RATINGS SYNC =============

async def fetch_google_place_data(place_id: str, api_key: str):
    """Fetch rating, review count, and reviews from Google Places API (New)"""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    params = {"fields": "rating,userRatingCount,reviews,location", "languageCode": "es"}
    headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json", "Referer": "https://senioradvisor.cl"}
    
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if "error" in data:
            return None
        
        reviews = []
        for r in (data.get("reviews") or [])[:20]:
            reviews.append({
                "author": r.get("authorAttribution", {}).get("displayName", "Usuario"),
                "author_photo": r.get("authorAttribution", {}).get("photoUri", ""),
                "rating": r.get("rating", 0),
                "text": r.get("text", {}).get("text", ""),
                "time_description": r.get("relativePublishTimeDescription", ""),
                "publish_time": r.get("publishTime", ""),
                "source": "google",
            })
        
        location = data.get("location", {})
        
        return {
            "google_rating": data.get("rating"),
            "google_total_reviews": data.get("userRatingCount", 0),
            "google_reviews": reviews,
            "latitude": location.get("latitude", 0),
            "longitude": location.get("longitude", 0),
        }


def calculate_blended_rating(google_rating, google_count, internal_rating, internal_count):
    """Weighted average of Google and internal ratings"""
    total_count = (google_count or 0) + (internal_count or 0)
    if total_count == 0:
        return 0, 0
    
    score = 0
    if google_rating and google_count:
        score += google_rating * google_count
    if internal_rating and internal_count:
        score += internal_rating * internal_count
    
    blended = round(score / total_count, 1)
    return blended, total_count


_sync_task_running = False

async def _run_google_sync(api_key: str):
    global _sync_task_running
    _sync_task_running = True
    try:
        providers = await db.providers.find(
            {"place_id": {"$exists": True, "$ne": "", "$ne": None}},
            {"_id": 0, "provider_id": 1, "place_id": 1, "business_name": 1,
             "internal_rating": 1, "internal_total_reviews": 1}
        ).to_list(200)
        
        synced = 0
        failed = 0
        
        for p in providers:
            place_id = p.get("place_id", "").strip()
            if not place_id or place_id.startswith("ChIJtest"):
                continue
            
            try:
                data = await fetch_google_place_data(place_id, api_key)
                if data:
                    g_rating = data["google_rating"]
                    g_count = data["google_total_reviews"]
                    i_rating = p.get("internal_rating", 0)
                    i_count = p.get("internal_total_reviews", 0)
                    
                    blended, total = calculate_blended_rating(g_rating, g_count, i_rating, i_count)
                    
                    await db.providers.update_one(
                        {"provider_id": p["provider_id"]},
                        {"$set": {
                            "google_rating": g_rating,
                            "google_total_reviews": g_count,
                            "google_reviews": data["google_reviews"],
                            "rating": blended,
                            "total_reviews": total,
                            "google_synced_at": datetime.now(timezone.utc).isoformat(),
                        }}
                    )
                    synced += 1
                else:
                    failed += 1
            except Exception as e:
                logging.error(f"Error syncing {p['business_name']}: {e}")
                failed += 1
            
            await asyncio.sleep(0.15)
        
        await db.system_config.update_one(
            {"key": "google_sync"},
            {"$set": {"key": "google_sync", "synced": synced, "failed": failed, "completed_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        logging.info(f"Google sync complete: {synced} synced, {failed} failed")
    except Exception as e:
        logging.error(f"Google sync error: {e}")
    finally:
        _sync_task_running = False


@router.post("/sync-google-ratings")
async def sync_google_ratings(request: Request):
    """Start Google ratings sync in background"""
    global _sync_task_running
    user = await get_current_user(request, db)
    await require_admin(user)
    
    if _sync_task_running:
        return {"message": "Sincronización ya en curso, espera unos minutos"}
    
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GOOGLE_PLACES_API_KEY no configurada")
    
    asyncio.create_task(_run_google_sync(api_key))
    return {"message": "Sincronización iniciada en segundo plano. Los ratings se actualizarán en ~2 minutos."}


@router.get("/sync-google-ratings/status")
async def sync_google_ratings_status(request: Request):
    """Check status of last Google sync"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    status = await db.system_config.find_one({"key": "google_sync"}, {"_id": 0})
    return {
        "running": _sync_task_running,
        "last_sync": status,
    }



# ============= REVIEW MODERATION =============

@router.get("/reviews")
async def get_all_reviews(request: Request, status: str = "pending"):
    """Get reviews for admin moderation"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    query = {}
    if status == "pending":
        query["approved"] = False
    elif status == "approved":
        query["approved"] = True
    
    reviews = await db.reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    
    for review in reviews:
        reviewer = await db.users.find_one({"user_id": review.get("user_id")}, {"_id": 0, "name": 1, "email": 1, "picture": 1})
        if reviewer:
            review["user_name"] = reviewer.get("name", "Usuario")
            review["user_email"] = reviewer.get("email", "")
        provider = await db.providers.find_one({"provider_id": review.get("provider_id")}, {"_id": 0, "business_name": 1})
        if provider:
            review["provider_name"] = provider.get("business_name", "")
    
    return {"reviews": reviews, "total": len(reviews)}


@router.post("/reviews/{review_id}/approve")
async def approve_review(review_id: str, request: Request):
    """Approve a review"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    result = await db.reviews.update_one(
        {"review_id": review_id},
        {"$set": {"approved": True, "moderated": True, "published": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Resena no encontrada")
    
    review = await db.reviews.find_one({"review_id": review_id}, {"_id": 0})
    if review:
        from routes.social_routes import _update_provider_rating
        await _update_provider_rating(review["provider_id"])
    
    return {"message": "Resena aprobada"}


@router.post("/reviews/{review_id}/reject")
async def reject_review(review_id: str, request: Request):
    """Reject a review"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    result = await db.reviews.delete_one({"review_id": review_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Resena no encontrada")
    
    return {"message": "Resena eliminada"}


# ============= LEADS / TRÁFICO =============

@router.get("/leads")
async def get_admin_leads(request: Request):
    """Get all contact requests and care requests as leads for admin"""
    user = await get_current_user(request, db)
    await require_admin(user)

    # Get all contact requests
    contact_requests = await db.contact_requests.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    # Get all care requests
    care_requests = await db.care_requests.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    # Get all proposals
    proposals = await db.proposals.find(
        {}, {"_id": 0}
    ).sort("created_at", -1).to_list(500)

    # Enrich contact requests
    for cr in contact_requests:
        cr["lead_type"] = "contact_request"
        # Get client info
        client = await db.users.find_one(
            {"user_id": cr.get("client_user_id")},
            {"_id": 0, "name": 1, "email": 1, "phone": 1, "picture": 1}
        )
        if client:
            cr["client_email"] = client.get("email", "")
            cr["client_phone"] = client.get("phone", "")
            if not cr.get("client_name"):
                cr["client_name"] = client.get("name", "Cliente")
        # Get provider/residence info
        provider = await db.providers.find_one(
            {"user_id": cr.get("provider_user_id")},
            {"_id": 0, "business_name": 1, "provider_id": 1, "comuna": 1}
        )
        if provider:
            cr["provider_business_name"] = provider.get("business_name", "")
            cr["provider_provider_id"] = provider.get("provider_id", "")
            cr["provider_comuna"] = provider.get("comuna", "")

    # Enrich care requests
    for req in care_requests:
        req["lead_type"] = "care_request"
        # Get client info
        client = await db.users.find_one(
            {"user_id": req.get("client_id")},
            {"_id": 0, "name": 1, "email": 1, "phone": 1}
        )
        if client:
            req["client_email"] = client.get("email", "")
            req["client_phone"] = client.get("phone", "")

    # Enrich proposals with care request info
    for prop in proposals:
        prop["lead_type"] = "proposal"
        care_req = await db.care_requests.find_one(
            {"request_id": prop.get("care_request_id")},
            {"_id": 0, "patient_name": 1, "service_type": 1, "comuna": 1, "client_id": 1, "client_name": 1}
        )
        if care_req:
            prop["care_request_info"] = care_req
            client = await db.users.find_one(
                {"user_id": care_req.get("client_id")},
                {"_id": 0, "name": 1, "email": 1}
            )
            if client:
                prop["client_name"] = client.get("name", "")
                prop["client_email"] = client.get("email", "")

    return {
        "contact_requests": contact_requests,
        "care_requests": care_requests,
        "proposals": proposals
    }


@router.get("/leads/metrics")
async def get_admin_leads_metrics(request: Request):
    """Get aggregated lead metrics for admin dashboard"""
    user = await get_current_user(request, db)
    await require_admin(user)

    # Contact request counts
    cr_total = await db.contact_requests.count_documents({})
    cr_pending = await db.contact_requests.count_documents({"status": "pending"})
    cr_accepted = await db.contact_requests.count_documents({"status": "accepted"})
    cr_rejected = await db.contact_requests.count_documents({"status": "rejected"})

    # Care request counts
    care_total = await db.care_requests.count_documents({})
    care_active = await db.care_requests.count_documents({"status": "active"})
    care_completed = await db.care_requests.count_documents({"status": "completed"})

    # Proposal counts
    prop_total = await db.proposals.count_documents({})
    prop_pending = await db.proposals.count_documents({"status": "pending"})
    prop_accepted = await db.proposals.count_documents({"status": "accepted"})
    prop_rejected = await db.proposals.count_documents({"status": "rejected"})

    total_leads = cr_total + care_total
    total_conversions = cr_accepted + care_completed
    conversion_rate = round((total_conversions / total_leads * 100), 1) if total_leads > 0 else 0

    # Per-residence metrics (from contact requests)
    all_contact_requests = await db.contact_requests.find(
        {}, {"_id": 0, "provider_user_id": 1, "status": 1}
    ).to_list(1000)

    # Build per-residence map
    residence_map = {}
    for cr in all_contact_requests:
        puid = cr.get("provider_user_id", "unknown")
        if puid not in residence_map:
            residence_map[puid] = {"total": 0, "pending": 0, "accepted": 0, "rejected": 0}
        residence_map[puid]["total"] += 1
        status = cr.get("status", "pending")
        if status in residence_map[puid]:
            residence_map[puid][status] += 1

    # Also count proposals per provider
    all_proposals = await db.proposals.find(
        {}, {"_id": 0, "provider_id": 1, "status": 1}
    ).to_list(1000)
    for prop in all_proposals:
        puid = prop.get("provider_id", "unknown")
        if puid not in residence_map:
            residence_map[puid] = {"total": 0, "pending": 0, "accepted": 0, "rejected": 0}
        residence_map[puid]["total"] += 1
        status = prop.get("status", "pending")
        if status in residence_map[puid]:
            residence_map[puid][status] += 1

    # Enrich with provider names
    per_residence = []
    for puid, counts in residence_map.items():
        provider = await db.providers.find_one(
            {"user_id": puid},
            {"_id": 0, "business_name": 1, "provider_id": 1, "comuna": 1, "is_subscribed": 1}
        )
        rate = round((counts["accepted"] / counts["total"] * 100), 1) if counts["total"] > 0 else 0
        per_residence.append({
            "provider_user_id": puid,
            "business_name": provider.get("business_name", "Desconocido") if provider else "Desconocido",
            "provider_id": provider.get("provider_id", "") if provider else "",
            "comuna": provider.get("comuna", "") if provider else "",
            "is_subscribed": provider.get("is_subscribed", False) if provider else False,
            "total": counts["total"],
            "pending": counts["pending"],
            "accepted": counts["accepted"],
            "rejected": counts["rejected"],
            "conversion_rate": rate
        })

    # Sort by total leads descending
    per_residence.sort(key=lambda x: x["total"], reverse=True)

    return {
        "summary": {
            "total_leads": total_leads,
            "contact_requests": {
                "total": cr_total, "pending": cr_pending,
                "accepted": cr_accepted, "rejected": cr_rejected
            },
            "care_requests": {
                "total": care_total, "active": care_active,
                "completed": care_completed
            },
            "proposals": {
                "total": prop_total, "pending": prop_pending,
                "accepted": prop_accepted, "rejected": prop_rejected
            },
            "conversion_rate": conversion_rate,
            "total_conversions": total_conversions
        },
        "per_residence": per_residence
    }
