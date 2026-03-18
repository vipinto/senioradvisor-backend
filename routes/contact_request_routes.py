from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
import asyncio

from database import db
from auth import get_current_user
from email_service import send_email, new_message_email
from routes.notification_routes import create_notification

router = APIRouter()


# ==================== HELPERS ====================

async def create_connection(client_user_id: str, provider_user_id: str, connection_type: str, source_id: str = None):
    """Create a connection between a client and provider (unlocks chat)"""
    # Check if connection already exists
    existing = await db.connections.find_one({
        "client_user_id": client_user_id,
        "provider_user_id": provider_user_id,
        "status": "active"
    })
    if existing:
        return existing

    connection_id = f"conn_{uuid.uuid4().hex[:12]}"
    connection = {
        "connection_id": connection_id,
        "client_user_id": client_user_id,
        "provider_user_id": provider_user_id,
        "type": connection_type,
        "source_id": source_id,
        "status": "active",
        "created_at": datetime.now(timezone.utc)
    }
    await db.connections.insert_one(connection)
    connection.pop("_id", None)
    return connection


async def check_connection(user_id_1: str, user_id_2: str) -> bool:
    """Check if two users have an active connection"""
    conn = await db.connections.find_one({
        "status": "active",
        "$or": [
            {"client_user_id": user_id_1, "provider_user_id": user_id_2},
            {"client_user_id": user_id_2, "provider_user_id": user_id_1}
        ]
    })
    return conn is not None


# ==================== CONTACT REQUESTS (Direct) ====================

class ContactRequestCreate(BaseModel):
    provider_user_id: str
    message: Optional[str] = ""


@router.post("/contact-requests")
async def send_contact_request(data: ContactRequestCreate, request: Request):
    """Premium client sends a direct contact request to a carer"""
    user = await get_current_user(request, db)

    # Must be a client (not provider)
    if user.get("role") == "provider":
        raise HTTPException(status_code=403, detail="Solo clientes pueden enviar solicitudes de contacto")

    # Must have premium subscription
    subscription = await db.subscriptions.find_one({"user_id": user["user_id"], "status": "active"})
    if not subscription:
        raise HTTPException(status_code=403, detail="Necesitas suscripcion Premium para contactar proveedores directamente")

    # Provider must exist
    provider = await db.providers.find_one({"user_id": data.provider_user_id, "approved": True})
    if not provider:
        raise HTTPException(status_code=404, detail="Cuidador no encontrado")

    # Check for existing pending request
    existing = await db.contact_requests.find_one({
        "client_user_id": user["user_id"],
        "provider_user_id": data.provider_user_id,
        "status": "pending"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya tienes una solicitud pendiente con este proveedor")

    # Check if already connected
    already_connected = await check_connection(user["user_id"], data.provider_user_id)
    if already_connected:
        raise HTTPException(status_code=400, detail="Ya estas conectado con este proveedor")

    request_id = f"cr_{uuid.uuid4().hex[:12]}"
    contact_request = {
        "request_id": request_id,
        "client_user_id": user["user_id"],
        "client_name": user.get("name", "Cliente"),
        "client_picture": user.get("picture"),
        "provider_user_id": data.provider_user_id,
        "provider_name": provider.get("business_name", "Cuidador"),
        "message": data.message or "Hola, me gustaria contactarte para un servicio.",
        "status": "pending",
        "created_at": datetime.now(timezone.utc)
    }

    await db.contact_requests.insert_one(contact_request)
    contact_request.pop("_id", None)

    # Notify provider
    await create_notification(
        user_id=data.provider_user_id,
        title="Nueva solicitud de contacto",
        message=f"{user.get('name', 'Un cliente')} quiere contactarte",
        notification_type="contact_request"
    )

    # Email notification
    provider_user = await db.users.find_one({"user_id": data.provider_user_id}, {"_id": 0, "email": 1, "name": 1})
    if provider_user and provider_user.get("email"):
        subject, html = new_message_email(
            recipient_name=provider_user.get("name", "Cuidador"),
            sender_name=user.get("name", "Cliente"),
            message_preview=f"Solicitud de contacto: {data.message or 'Quiero contactarte'}"
        )
        asyncio.create_task(send_email(provider_user["email"], subject, html))

    return contact_request


@router.get("/contact-requests/received")
async def get_received_contact_requests(request: Request):
    """Get contact requests received by the current carer"""
    user = await get_current_user(request, db)

    requests_list = await db.contact_requests.find(
        {"provider_user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    # Enrich with client info
    for req in requests_list:
        client = await db.users.find_one(
            {"user_id": req["client_user_id"]},
            {"_id": 0, "name": 1, "picture": 1, "email": 1}
        )
        if client:
            req["client_name"] = client.get("name", "Cliente")
            req["client_picture"] = client.get("picture")

    return requests_list


@router.get("/contact-requests/sent")
async def get_sent_contact_requests(request: Request):
    """Get contact requests sent by the current client"""
    user = await get_current_user(request, db)

    requests_list = await db.contact_requests.find(
        {"client_user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    # Enrich with provider info
    for req in requests_list:
        provider = await db.providers.find_one(
            {"user_id": req["provider_user_id"]},
            {"_id": 0, "business_name": 1, "photos": 1, "provider_id": 1, "rating": 1, "verified": 1}
        )
        if provider:
            req["provider_business_name"] = provider.get("business_name")
            req["provider_photo"] = (provider.get("photos") or [None])[0]
            req["provider_provider_id"] = provider.get("provider_id")
            req["provider_rating"] = provider.get("rating")
            req["provider_verified"] = provider.get("verified")

    return requests_list


@router.put("/contact-requests/{request_id}/{action}")
async def respond_contact_request(request_id: str, action: str, request: Request):
    """Accept or reject a contact request (carer only)"""
    user = await get_current_user(request, db)

    if action not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="Accion debe ser 'accept' o 'reject'")

    contact_req = await db.contact_requests.find_one(
        {"request_id": request_id, "provider_user_id": user["user_id"]},
        {"_id": 0}
    )
    if not contact_req:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    if contact_req["status"] != "pending":
        raise HTTPException(status_code=400, detail="Esta solicitud ya fue respondida")

    new_status = "accepted" if action == "accept" else "rejected"
    await db.contact_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": new_status, "responded_at": datetime.now(timezone.utc)}}
    )

    if action == "accept":
        # Create connection → unlocks chat
        await create_connection(
            client_user_id=contact_req["client_user_id"],
            provider_user_id=user["user_id"],
            connection_type="contact_request_accepted",
            source_id=request_id
        )

        await create_notification(
            user_id=contact_req["client_user_id"],
            title="Solicitud aceptada!",
            message=f"{contact_req.get('provider_name', 'El servicio')} acepto tu solicitud. Ya puedes chatear.",
            notification_type="contact_accepted"
        )
    else:
        await create_notification(
            user_id=contact_req["client_user_id"],
            title="Solicitud rechazada",
            message=f"{contact_req.get('provider_name', 'El servicio')} no acepto tu solicitud.",
            notification_type="contact_rejected"
        )

    updated = await db.contact_requests.find_one({"request_id": request_id}, {"_id": 0})
    return updated


# ==================== CONNECTION STATUS ====================

@router.get("/connections/check/{other_user_id}")
async def check_user_connection(other_user_id: str, request: Request):
    """Check if current user has a connection with another user"""
    user = await get_current_user(request, db)
    connected = await check_connection(user["user_id"], other_user_id)
    return {"connected": connected}


@router.get("/connections")
async def get_my_connections(request: Request):
    """Get all active connections for the current user"""
    user = await get_current_user(request, db)

    connections = await db.connections.find(
        {
            "status": "active",
            "$or": [
                {"client_user_id": user["user_id"]},
                {"provider_user_id": user["user_id"]}
            ]
        },
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Enrich with other user info
    for conn in connections:
        other_id = conn["provider_user_id"] if conn["client_user_id"] == user["user_id"] else conn["client_user_id"]
        other_user = await db.users.find_one(
            {"user_id": other_id},
            {"_id": 0, "user_id": 1, "name": 1, "picture": 1, "role": 1}
        )
        conn["other_user"] = other_user

    return connections
