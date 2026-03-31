from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import uuid
import random
import string
import io
from passlib.hash import bcrypt

from database import db
from auth import get_current_user, require_admin
from routes.notification_routes import create_notification
from google_places_service import fetch_place_details

router = APIRouter(prefix="/admin")


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
    providers = await db.providers.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
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
    active_subscriptions = await db.subscriptions.count_documents({"status": "active"})
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
    # Google Places data (sent from frontend)
    latitude: Optional[float] = 0
    longitude: Optional[float] = 0
    google_rating: Optional[float] = 0
    google_total_reviews: Optional[int] = 0
    google_reviews: Optional[list] = None

def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# Faster bcrypt for bulk operations (reduced rounds)
_bcrypt_bulk = bcrypt.using(rounds=6)

@router.post("/residencias/create")
async def create_residencia(data: ResidenciaCreate, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)
    
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail=f"El email {data.email} ya está registrado")
    
    password = data.password or generate_password()
    user_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    
    # Use Google data from frontend or try backend fetch as fallback
    latitude = data.latitude or 0
    longitude = data.longitude or 0
    google_rating = data.google_rating or 0
    google_total_reviews = data.google_total_reviews or 0
    google_reviews = data.google_reviews or []
    
    # If no lat/lng provided but place_id exists, try backend fetch
    if data.place_id and not (latitude and longitude):
        place_data = await fetch_place_details(data.place_id)
        if place_data and not place_data.get("error"):
            latitude = place_data.get("latitude", 0) or latitude
            longitude = place_data.get("longitude", 0) or longitude
            google_rating = place_data.get("google_rating", 0) or google_rating
            google_total_reviews = place_data.get("google_total_reviews", 0) or google_total_reviews
            if not google_reviews:
                google_reviews = place_data.get("google_reviews", [])
    
    new_user = {
        "user_id": user_id,
        "email": data.email,
        "name": data.business_name,
        "role": "provider",
        "hashed_password": bcrypt.hash(password),
        "created_at": now.isoformat(),
        "active": True,
    }
    await db.users.insert_one(new_user)
    
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
        "rating": google_rating or 0,
        "total_reviews": google_total_reviews or 0,
        "approved": True,
        "verified": False,
        "latitude": latitude,
        "longitude": longitude,
        "place_id": data.place_id or "",
        "google_rating": google_rating,
        "google_total_reviews": google_total_reviews,
        "google_reviews": google_reviews,
        "coverage_zone": "10",
        "created_at": now,
        "approved_at": now,
    }
    await db.providers.insert_one(provider)
    
    response = {
        "provider_id": provider_id,
        "user_id": user_id,
        "business_name": data.business_name,
        "email": data.email,
        "password": password,
        "status": "created",
        "google_data": {
            "latitude": latitude,
            "longitude": longitude,
            "google_rating": google_rating,
            "google_total_reviews": google_total_reviews,
            "reviews_count": len(google_reviews),
        }
    }
    
    return response


@router.get("/google-place/{place_id}")
async def get_google_place_details(place_id: str, request: Request):
    """Fetch Google Place details for preview"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    place_data = await fetch_place_details(place_id)
    if not place_data:
        raise HTTPException(status_code=404, detail="No se encontraron datos para este Place ID")
    if place_data.get("error"):
        raise HTTPException(status_code=400, detail=place_data.get("error_message", place_data.get("error")))
    return place_data


@router.post("/providers/{provider_id}/refresh-google")
async def refresh_google_data(provider_id: str, request: Request):
    """Refresh Google Place data for an existing provider"""
    user = await get_current_user(request, db)
    await require_admin(user)
    
    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    
    place_id = provider.get("place_id", "")
    if not place_id:
        raise HTTPException(status_code=400, detail="Este proveedor no tiene Place ID configurado")
    
    place_data = await fetch_place_details(place_id)
    if not place_data or place_data.get("error"):
        raise HTTPException(status_code=400, detail=place_data.get("error_message", "Error al obtener datos de Google"))
    
    update = {
        "latitude": place_data.get("latitude", 0),
        "longitude": place_data.get("longitude", 0),
        "google_rating": place_data.get("google_rating", 0),
        "google_total_reviews": place_data.get("google_total_reviews", 0),
        "google_reviews": place_data.get("google_reviews", []),
        "rating": place_data.get("google_rating", 0),
        "total_reviews": place_data.get("google_total_reviews", 0),
    }
    
    await db.providers.update_one({"provider_id": provider_id}, {"$set": update})
    
    return {
        "message": "Datos de Google actualizados",
        **{k: v for k, v in update.items() if k != "google_reviews"},
        "reviews_count": len(place_data.get("google_reviews", [])),
    }



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
            "hashed_password": _bcrypt_bulk.hash(password),
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
            "created_at": now,
            "approved_at": now,
        }
        await db.providers.insert_one(provider)
        
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
        if col in ("nombre residencia", "nombre_residencia", "nombre", "business_name", "residencia"):
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
        elif col in ("disponibilidad", "availability"):
            col_map["disponibilidad"] = col
        elif col in ("video promocional", "video"):
            col_map["video"] = col
        elif col == "whatsapp":
            col_map["whatsapp"] = col

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

    # Pre-fetch all existing emails to avoid per-row queries
    all_emails_in_csv = set()
    rows_data = []
    for _, row in df.iterrows():
        bname = get_val(row, "business_name")
        if not bname:
            continue
        email = get_val(row, "email")
        short_id = uuid.uuid4().hex[:8]
        if not email:
            slug = bname.lower().replace(" ", "-")[:30]
            slug = "".join(c for c in slug if c.isalnum() or c == "-")
            email = f"{slug}-{short_id}@senioradvisor.cl"
        all_emails_in_csv.add(email)
        rows_data.append((row, bname, email))

    # Batch check existing emails
    existing_emails_docs = await db.users.find(
        {"email": {"$in": list(all_emails_in_csv)}},
        {"_id": 0, "email": 1}
    ).to_list(len(all_emails_in_csv))
    existing_emails = {d["email"] for d in existing_emails_docs}

    results = []
    users_to_insert = []
    providers_to_insert = []
    now = datetime.now(timezone.utc)

    for row, bname, email in rows_data:
        if email in existing_emails:
            results.append({"business_name": bname, "email": email, "status": "error", "detail": "Email ya registrado"})
            continue

        password = generate_password()
        user_id = str(uuid.uuid4())
        provider_id = str(uuid.uuid4())

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

        amenities_str = get_val(row, "amenities") or get_val(row, "servicios")
        amenities = [a.strip() for a in amenities_str.split(",") if a.strip()] if amenities_str else []

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
        service_type = "residencias"
        if service_type_raw:
            st_lower = service_type_raw.lower()
            if "domicilio" in st_lower:
                service_type = "cuidado-domicilio"
            elif "mental" in st_lower or "psico" in st_lower:
                service_type = "salud-mental"

        price_from = parse_int(get_val(row, "price_from"))

        users_to_insert.append({
            "user_id": user_id,
            "email": email,
            "name": bname,
            "role": "provider",
            "hashed_password": _bcrypt_bulk.hash(password),
            "created_at": now.isoformat(),
            "active": True,
        })

        providers_to_insert.append({
            "provider_id": provider_id,
            "user_id": user_id,
            "business_name": bname,
            "phone": phone,
            "whatsapp": whatsapp,
            "address": address,
            "comuna": comuna,
            "region": region,
            "description": description,
            "services": [{"service_type": service_type, "price_from": price_from, "description": ""}],
            "photos": [],
            "gallery": gallery,
            "amenities": amenities,
            "social_links": social_links,
            "personal_info": {"housing_type": "residencia", "animal_experience": "N/A"},
            "rating": rating,
            "total_reviews": total_reviews,
            "approved": True,
            "verified": False,
            "latitude": latitude,
            "longitude": longitude,
            "place_id": place_id,
            "logo": logo,
            "staff_type": staff_type,
            "disponibilidad": disponibilidad,
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
            "status": "created"
        })

    # Batch insert all at once
    if users_to_insert:
        await db.users.insert_many(users_to_insert)
    if providers_to_insert:
        await db.providers.insert_many(providers_to_insert)

    created = len([r for r in results if r["status"] == "created"])
    errors = len([r for r in results if r["status"] == "error"])
    return {"total": len(results), "created": created, "errors": errors, "results": results}



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

    contents = await file.read()
    current_gallery = provider.get("gallery", [])
    if len(current_gallery) >= 10:
        raise HTTPException(status_code=400, detail="Máximo 10 fotos")

    from pathlib import Path
    from routes.provider_routes import compress_image, GALLERY_DIR
    compressed_data, thumbnail_data = compress_image(contents)
    photo_id = f"gallery_{uuid.uuid4().hex[:12]}"
    main_path = GALLERY_DIR / f"{photo_id}.jpg"
    thumb_path = GALLERY_DIR / f"{photo_id}_thumb.jpg"
    with open(main_path, "wb") as f:
        f.write(compressed_data)
    with open(thumb_path, "wb") as f:
        f.write(thumbnail_data)

    photo_record = {
        "photo_id": photo_id,
        "url": f"/api/uploads/gallery/{photo_id}.jpg",
        "thumbnail_url": f"/api/uploads/gallery/{photo_id}_thumb.jpg",
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$push": {"gallery": photo_record}},
    )
    return {"message": "Foto subida", "photo": photo_record}


@router.delete("/providers/{provider_id}/gallery/{photo_id}")
async def admin_delete_gallery(provider_id: str, photo_id: str, request: Request):
    user = await get_current_user(request, db)
    await require_admin(user)

    provider = await db.providers.find_one({"provider_id": provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")

    await db.providers.update_one(
        {"provider_id": provider_id},
        {"$pull": {"gallery": {"photo_id": photo_id}}},
    )
    return {"message": "Foto eliminada"}


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

    allowed = ["business_name", "phone", "address", "region", "comuna", "place_id",
               "social_links", "services", "amenities", "description"]
    update = {k: v for k, v in body.items() if k in allowed}
    if update:
        await db.providers.update_one({"provider_id": provider_id}, {"$set": update})
    
    updated = await db.providers.find_one({"provider_id": provider_id}, {"_id": 0})
    return updated
