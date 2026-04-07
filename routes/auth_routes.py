from fastapi import APIRouter, Request, Response, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import os

from database import db
from auth import (
    get_current_user, register_user, login_user,
    google_auth_login, forgot_password, reset_password
)

router = APIRouter(prefix="/auth")


class EmailRegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    role: Optional[str] = "client"


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    code: Optional[str] = None
    redirect_uri: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.get("/me")
async def get_me(request: Request):
    """Get current authenticated user"""
    user = await get_current_user(request, db)

    provider = None
    has_subscription = False
    if user["role"] == "provider":
        provider = await db.providers.find_one(
            {"user_id": user["user_id"]},
            {"_id": 0}
        )
        if provider and provider.get("plan_active") and provider.get("plan_type") in ("premium", "premium_plus"):
            has_subscription = True
    elif user["role"] == "client":
        has_subscription = True

    return {
        **user,
        "has_subscription": has_subscription,
        "provider": provider
    }


@router.post("/register")
async def email_register(data: EmailRegisterRequest):
    """Register with email and password"""
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    result = await register_user(data.email, data.password, data.name, db, data.role)
    return result


@router.post("/login")
async def email_login(data: EmailLoginRequest):
    """Login with email and password"""
    import traceback
    import logging
    logger = logging.getLogger(__name__)
    try:
        result = await login_user(data.email, data.password, db)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


#@router.post("/google")
#async def google_login(data: GoogleAuthRequest):
#    """Login/register with Google OAuth (supports both popup and redirect flows)"""
#    result = await google_auth_login(
#        credential=data.credential,
#        code=data.code,
#        redirect_uri=data.redirect_uri,
#        db=db
#    )
#    return result


@router.post("/forgot-password")
async def handle_forgot_password(data: ForgotPasswordRequest, request: Request):
    """Send password reset email"""
    frontend_url = request.headers.get("origin")
    if not frontend_url:
        frontend_url = os.environ.get("FRONTEND_URL", "")
    if not frontend_url:
        raise HTTPException(status_code=400, detail="No se pudo determinar la URL de origen")
    result = await forgot_password(data.email, db, frontend_url)
    return result


@router.post("/reset-password")
async def handle_reset_password(data: ResetPasswordRequest):
    """Reset password with token"""
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    result = await reset_password(data.token, data.password, db)
    return result


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user and delete session"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie(key="session_token", path="/")
    return {"message": "Logged out successfully"}


@router.post("/add-role")
async def add_role(request: Request):
    """Add a new role to the current user (client can become cuidador)"""
    import uuid
    from datetime import datetime, timezone
    
    user = await get_current_user(request, db)
    data = await request.json()
    new_role = data.get("role")
    
    if new_role not in ["client", "provider"]:
        raise HTTPException(status_code=400, detail="Rol inválido")
    
    # Get current roles
    current_roles = user.get("roles", [user.get("role", "client")])
    if isinstance(current_roles, str):
        current_roles = [current_roles]
    
    if new_role in current_roles:
        raise HTTPException(status_code=400, detail="Ya tienes este rol")
    
    # Add new role
    new_roles = list(set(current_roles + [new_role]))
    
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"roles": new_roles, "role": new_role}}  # role field for backwards compatibility
    )
    
    # If adding provider role, create provider profile
    if new_role == "provider":
        existing_provider = await db.providers.find_one({"user_id": user["user_id"]})
        if not existing_provider:
            provider_id = f"prov_{uuid.uuid4().hex[:12]}"
            provider = {
                "provider_id": provider_id,
                "user_id": user["user_id"],
                "business_name": user.get("name", ""),
                "description": "",
                "phone": user.get("phone"),
                "address": user.get("address"),
                "comuna": user.get("comuna"),
                "latitude": None,
                "longitude": None,
                "services": [],
                "photos": [],
                "verified": False,
                "is_featured": False,
                "rating": 0,
                "total_reviews": 0,
                "created_at": datetime.now(timezone.utc)
            }
            await db.providers.insert_one(provider)
    
    return {"message": "Rol agregado", "roles": new_roles}


@router.post("/select-role")
async def select_role(request: Request):
    """Select active role for current session"""
    user = await get_current_user(request, db)
    data = await request.json()
    selected_role = data.get("role")
    
    # Get current roles
    current_roles = user.get("roles", [user.get("role", "client")])
    if isinstance(current_roles, str):
        current_roles = [current_roles]
    
    if selected_role not in current_roles:
        raise HTTPException(status_code=400, detail="No tienes este rol")
    
    # Update active role
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"role": selected_role}}
    )
    
    # Get updated user
    updated_user = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "hashed_password": 0})
    
    return {"message": "Rol seleccionado", "user": updated_user}



@router.post("/profile/photos")
async def upload_client_photo(request: Request, file: UploadFile = File(...), photo_type: str = Form(...)):
    """Upload a photo for client profile (yard or pets)"""
    import uuid
    import os
    user = await get_current_user(request, db)
    
    if photo_type not in ['yard', 'pets']:
        raise HTTPException(status_code=400, detail="Tipo de foto inválido")
    
    # Save file
    photo_id = f"photo_{uuid.uuid4().hex[:12]}"
    upload_dir = "/app/uploads/client_photos"
    os.makedirs(upload_dir, exist_ok=True)
    
    ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
    filename = f"{photo_id}.{ext}"
    filepath = os.path.join(upload_dir, filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    
    photo_data = {
        "photo_id": photo_id,
        "url": f"/uploads/client_photos/{filename}",
        "type": photo_type
    }
    
    field_name = "yard_photos" if photo_type == "yard" else "pets_photos"
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$push": {field_name: photo_data}}
    )
    
    return photo_data


@router.delete("/profile/photos/{photo_id}")
async def delete_client_photo(request: Request, photo_id: str):
    """Delete a photo from client profile"""
    import os
    user = await get_current_user(request, db)
    
    # Remove from both arrays
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {
            "$pull": {
                "yard_photos": {"photo_id": photo_id},
                "pets_photos": {"photo_id": photo_id}
            }
        }
    )
    
    # Try to delete file
    for ext in ['jpg', 'jpeg', 'png', 'webp']:
        filepath = f"/app/uploads/client_photos/{photo_id}.{ext}"
        if os.path.exists(filepath):
            os.remove(filepath)
            break
    
    return {"message": "Foto eliminada"}


# ============= PUBLIC PROVIDER REGISTRATION =============

class ProviderRegistrationRequest(BaseModel):
    # Step 1: Basic info
    business_name: str
    email: str
    password: str
    # Step 2: Contact
    phone: Optional[str] = ""
    address: Optional[str] = ""
    comuna: Optional[str] = ""
    region: Optional[str] = ""
    website: Optional[str] = ""
    # Step 3: Social
    facebook: Optional[str] = ""
    instagram: Optional[str] = ""
    # Step 4: Services
    services: Optional[list] = []
    # Step 5: Amenities
    amenities: Optional[list] = []


@router.post("/register-provider")
async def register_provider_public(data: ProviderRegistrationRequest):
    """Public registration for a new residence/provider. Requires admin approval."""
    import uuid
    from datetime import datetime, timezone
    import bcrypt as bcrypt_lib

    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    if not data.business_name.strip():
        raise HTTPException(status_code=400, detail="El nombre de la residencia es obligatorio")
    if not data.email.strip():
        raise HTTPException(status_code=400, detail="El correo electrónico es obligatorio")

    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    provider_id = f"prov_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    # Create user
    user_doc = {
        "user_id": user_id,
        "email": data.email,
        "name": data.business_name,
        "role": "provider",
        "hashed_password": bcrypt_lib.hashpw(data.password.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8'),
        "auth_type": "email",
        "created_at": now,
        "active": True,
    }
    await db.users.insert_one(user_doc)

    # Build social links
    social_links = {}
    if data.website:
        social_links["website"] = data.website
    if data.facebook:
        social_links["facebook"] = data.facebook
    if data.instagram:
        social_links["instagram"] = data.instagram

    # Build services array
    services = []
    for svc in (data.services or []):
        if isinstance(svc, dict):
            price = int(svc.get("price_from", 0) or 0)
            desc = svc.get("description", "")
            stype = svc.get("service_type", "residencias")
            if price > 0 or desc:
                services.append({"service_type": stype, "price_from": price, "description": desc})

    # Create provider with approved=False (pending admin approval)
    provider_doc = {
        "provider_id": provider_id,
        "user_id": user_id,
        "business_name": data.business_name,
        "phone": data.phone or "",
        "whatsapp": data.phone or "",
        "address": data.address or "",
        "comuna": data.comuna or "",
        "region": data.region or "",
        "description": "",
        "services": services if services else [],
        "photos": [],
        "gallery": [],
        "amenities": data.amenities or [],
        "social_links": social_links,
        "personal_info": {"housing_type": "residencia"},
        "rating": 0,
        "total_reviews": 0,
        "approved": False,
        "verified": False,
        "latitude": 0,
        "longitude": 0,
        "place_id": "",
        "coverage_zone": "10",
        "created_at": now,
        "registration_source": "public_form",
    }
    await db.providers.insert_one(provider_doc)

    return {
        "message": "Registro exitoso. Tu residencia será revisada por un administrador antes de aparecer en el directorio.",
        "provider_id": provider_id,
        "status": "pending_approval"
    }

