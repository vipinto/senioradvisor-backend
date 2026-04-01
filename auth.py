from fastapi import HTTPException, Request
from typing import Optional
import httpx
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
from motor.motor_asyncio import AsyncIOMotorDatabase
import bcrypt as bcrypt_lib
import jwt
import os
import resend
import logging
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

load_dotenv(Path(__file__).parent / '.env')

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
resend.api_key = os.environ.get("RESEND_API_KEY")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")


def create_jwt_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS),
        "iat": datetime.now(timezone.utc),
        "type": "jwt"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


async def register_user(email: str, password: str, name: str, db: AsyncIOMotorDatabase, role: str = "client"):
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Este correo ya está registrado")

    # Validate role
    if role not in ["client", "provider"]:
        role = "client"

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    hashed = bcrypt_lib.hashpw(password.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8')

    user = {
        "user_id": user_id,
        "email": email,
        "name": name,
        "picture": None,
        "role": role,
        "phone": None,
        "hashed_password": hashed,
        "auth_type": "email",
        "created_at": datetime.now(timezone.utc)
    }

    await db.users.insert_one(user)
    
    # If registering as provider, create empty provider profile
    if role == "provider":
        provider_id = f"prov_{uuid.uuid4().hex[:12]}"
        provider = {
            "provider_id": provider_id,
            "user_id": user_id,
            "business_name": name,
            "description": "",
            "phone": None,
            "address": None,
            "comuna": None,
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
    
    token = create_jwt_token(user_id, email)

    return {
        "user": {
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": None,
            "role": role,
            "phone": None
        },
        "token": token
    }


async def login_user(email: str, password: str, db: AsyncIOMotorDatabase):
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    if not user.get("hashed_password"):
        raise HTTPException(
            status_code=401,
            detail="Esta cuenta usa inicio de sesión con Google. Por favor usa el botón de Google."
        )

    if not bcrypt_lib.checkpw(password.encode('utf-8'), user["hashed_password"].encode('utf-8')):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    token = create_jwt_token(user["user_id"], email)
    safe_user = {k: v for k, v in user.items() if k not in ("hashed_password",)}
    
    # Check if user has multiple roles
    roles = safe_user.get("roles", [safe_user.get("role", "client")])
    if isinstance(roles, str):
        roles = [roles]
    safe_user["roles"] = roles
    safe_user["needs_role_selection"] = len(roles) > 1

    return {
        "user": safe_user,
        "token": token
    }


async def google_auth_login(credential: str = None, code: str = None, redirect_uri: str = None, db: AsyncIOMotorDatabase = None):
    """Verify Google credential (ID token or auth code) and create/login user"""
    email = None
    name = None
    picture = None

    if code and redirect_uri:
        # Authorization Code flow (redirect-based, works on Safari)
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': code,
                    'client_id': GOOGLE_CLIENT_ID,
                    'client_secret': GOOGLE_CLIENT_SECRET,
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code'
                }
            )
            if token_response.status_code != 200:
                logger.error(f"Google token exchange failed: {token_response.text}")
                raise HTTPException(status_code=401, detail="Error al verificar con Google")

            tokens = token_response.json()
            id_token_str = tokens.get('id_token')

        try:
            idinfo = id_token.verify_oauth2_token(
                id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        except ValueError:
            raise HTTPException(status_code=401, detail="Token de Google inválido")

        email = idinfo.get("email")
        name = idinfo.get("name", email.split("@")[0] if email else "")
        picture = idinfo.get("picture")

    elif credential:
        # Legacy popup flow (ID token directly)
        try:
            idinfo = id_token.verify_oauth2_token(
                credential, google_requests.Request(), GOOGLE_CLIENT_ID
            )
        except ValueError:
            raise HTTPException(status_code=401, detail="Token de Google inválido")

        email = idinfo.get("email")
        name = idinfo.get("name", email.split("@")[0] if email else "")
        picture = idinfo.get("picture")
    else:
        raise HTTPException(status_code=400, detail="Se requiere credential o code")

    if not email:
        raise HTTPException(status_code=401, detail="No se pudo obtener el email de Google")

    existing = await db.users.find_one({"email": email}, {"_id": 0})

    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture, "auth_type": "google"}}
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "role": "client",
            "phone": None,
            "auth_type": "google",
            "created_at": datetime.now(timezone.utc)
        })

    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    safe_user = {k: v for k, v in user.items() if k not in ("hashed_password",)}
    token = create_jwt_token(user_id, email)

    return {
        "user": safe_user,
        "token": token
    }


async def forgot_password(email: str, db: AsyncIOMotorDatabase, frontend_url: str):
    """Generate reset token and send email"""
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        # Don't reveal if email exists
        return {"message": "Si el correo existe, recibirás un enlace de recuperación"}

    if user.get("auth_type") == "google" and not user.get("hashed_password"):
        return {"message": "Esta cuenta usa inicio de sesión con Google. No necesita contraseña."}

    reset_token = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await db.password_resets.delete_many({"email": email})
    await db.password_resets.insert_one({
        "email": email,
        "token": reset_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    })

    reset_link = f"{frontend_url}/reset-password?token={reset_token}"

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <div style="text-align: center; margin-bottom: 30px;">
            <div style="display: inline-block; background-color: #E6202E; border-radius: 12px; padding: 12px 16px;">
                <span style="color: white; font-size: 28px; font-weight: bold;">U</span>
            </div>
            <h1 style="color: #1a1a1a; margin-top: 16px;">SeniorAdvisor</h1>
        </div>
        <h2 style="color: #333;">Recuperar Contraseña</h2>
        <p style="color: #555;">Hola {user.get('name', '')},</p>
        <p style="color: #555;">Recibimos una solicitud para restablecer tu contraseña. Haz clic en el botón:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_link}" style="background-color: #E6202E; color: white; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px;">
                Restablecer Contraseña
            </a>
        </div>
        <p style="color: #888; font-size: 13px;">Este enlace expira en 1 hora. Si no solicitaste esto, ignora este correo.</p>
    </div>
    """

    try:
        params = {
            "from": SENDER_EMAIL,
            "to": [email],
            "subject": "SeniorAdvisor - Recuperar Contraseña",
            "html": html_content
        }
        await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send reset email: {str(e)}")
        raise HTTPException(status_code=500, detail="Error al enviar el correo de recuperación")

    return {"message": "Si el correo existe, recibirás un enlace de recuperación"}


async def reset_password(token: str, new_password: str, db: AsyncIOMotorDatabase):
    """Verify reset token and update password"""
    reset = await db.password_resets.find_one({"token": token})
    if not reset:
        raise HTTPException(status_code=400, detail="Enlace inválido o expirado")

    expires_at = reset["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        await db.password_resets.delete_one({"token": token})
        raise HTTPException(status_code=400, detail="El enlace ha expirado")

    hashed = bcrypt_lib.hashpw(new_password.encode('utf-8'), bcrypt_lib.gensalt()).decode('utf-8')
    await db.users.update_one(
        {"email": reset["email"]},
        {"$set": {"hashed_password": hashed}}
    )

    await db.password_resets.delete_many({"email": reset["email"]})

    return {"message": "Contraseña actualizada correctamente"}


async def get_current_user(request: Request, db: AsyncIOMotorDatabase):
    """Get current user from JWT (Authorization header) or session cookie"""
    session_token = request.cookies.get("session_token")
    auth_header = request.headers.get("Authorization")
    bearer_token = None

    if auth_header and auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:]

    # Try JWT first
    if bearer_token:
        try:
            payload = verify_jwt_token(bearer_token)
            if payload.get("type") == "jwt":
                user = await db.users.find_one(
                    {"user_id": payload["user_id"]},
                    {"_id": 0}
                )
                if user:
                    return {k: v for k, v in user.items() if k not in ("hashed_password",)}
        except HTTPException:
            pass

    # Try session cookie (legacy Emergent Google Auth)
    token = session_token or bearer_token
    if not token:
        raise HTTPException(status_code=401, detail="No autenticado")

    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Sesión inválida")

    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        await db.user_sessions.delete_one({"session_token": token})
        raise HTTPException(status_code=401, detail="Sesión expirada")

    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    return {k: v for k, v in user.items() if k not in ("hashed_password",)}


async def get_current_user_optional(request: Request, db: AsyncIOMotorDatabase) -> Optional[dict]:
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None


async def require_subscription(user: dict, db: AsyncIOMotorDatabase):
    subscription = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0}
    )
    if not subscription:
        raise HTTPException(
            status_code=403,
            detail="Suscripción activa requerida. Por favor suscríbete para acceder a esta función."
        )

    end_date = subscription.get("end_date") or subscription.get("expires_at")
    if not end_date:
        return subscription
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    if end_date < datetime.now(timezone.utc):
        await db.subscriptions.update_one(
            {"subscription_id": subscription["subscription_id"]},
            {"$set": {"status": "expired"}}
        )
        raise HTTPException(
            status_code=403,
            detail="Tu suscripción ha expirado. Por favor renueva tu plan."
        )
    return subscription


async def require_provider(user: dict, db: AsyncIOMotorDatabase):
    if user["role"] != "provider":
        raise HTTPException(status_code=403, detail="Solo proveedores pueden acceder")
    provider = await db.providers.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not provider:
        raise HTTPException(status_code=404, detail="Perfil de proveedor no encontrado")
    return provider


async def require_admin(user: dict):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden acceder")
    return user
