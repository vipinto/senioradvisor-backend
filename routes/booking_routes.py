from fastapi import APIRouter, Request, HTTPException
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from enum import Enum
import uuid
import asyncio

from database import db
from auth import get_current_user
from routes.notification_routes import create_notification
from email_service import (
    send_email,
    booking_request_email,
    booking_confirmed_email,
    booking_rejected_email
)

router = APIRouter()


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BookingCreate(BaseModel):
    provider_id: str
    service_type: str
    start_date: str  # ISO date string
    end_date: Optional[str] = None  # ISO date string, optional for single-day services
    pet_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class BookingUpdate(BaseModel):
    status: BookingStatus
    provider_notes: Optional[str] = None


# ============= CLIENT ENDPOINTS =============

@router.post("/bookings")
async def create_booking(booking_data: BookingCreate, request: Request):
    """Create a new booking request (Client)"""
    user = await get_current_user(request, db)
    
    # Check if user has active subscription
    subscription = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"}
    )
    if not subscription:
        raise HTTPException(status_code=403, detail="Necesitas una suscripcion activa para hacer reservas")
    
    # Verify provider exists
    provider = await db.providers.find_one({"provider_id": booking_data.provider_id})
    if not provider:
        raise HTTPException(status_code=404, detail="Cuidador no encontrado")
    
    # Verify pets belong to user
    pets_info = []
    for pet_id in booking_data.pet_ids:
        pet = await db.pets.find_one({"pet_id": pet_id, "user_id": user["user_id"]}, {"_id": 0})
        if not pet:
            raise HTTPException(status_code=400, detail=f"Mascota {pet_id} no encontrada")
        pets_info.append({
            "pet_id": pet["pet_id"],
            "name": pet["name"],
            "species": pet.get("species", "perro"),
            "breed": pet.get("breed"),
            "size": pet.get("size"),
            "age": pet.get("age"),
            "sex": pet.get("sex"),
            "photo": pet.get("photo"),
            "notes": pet.get("notes")
        })
    
    # Parse dates
    try:
        start_date = datetime.fromisoformat(booking_data.start_date.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(booking_data.end_date.replace('Z', '+00:00')) if booking_data.end_date else start_date
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de fecha invalido")
    
    booking_id = f"book_{uuid.uuid4().hex[:12]}"
    booking = {
        "booking_id": booking_id,
        "client_user_id": user["user_id"],
        "client_name": user["name"],
        "client_email": user.get("email"),
        "client_phone": user.get("phone"),
        "provider_id": booking_data.provider_id,
        "provider_user_id": provider["user_id"],
        "provider_name": provider["business_name"],
        "service_type": booking_data.service_type,
        "start_date": start_date,
        "end_date": end_date,
        "pets": pets_info,
        "notes": booking_data.notes,
        "status": BookingStatus.PENDING.value,
        "provider_notes": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.bookings.insert_one(booking)
    booking.pop("_id", None)
    
    # Create notification for provider
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": provider["user_id"],
        "type": "new_booking",
        "title": "Nueva reserva",
        "message": f"{user['name']} ha solicitado una reserva de {booking_data.service_type}",
        "data": {"booking_id": booking_id},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.notifications.insert_one(notification)
    
    # Send email notification to provider
    provider_email = provider.get("email") or (await db.users.find_one({"user_id": provider["user_id"]})).get("email")
    if provider_email:
        pet_names = [p["name"] for p in pets_info]
        subject, html = booking_request_email(
            provider_name=provider["business_name"],
            client_name=user["name"],
            service_type=booking_data.service_type,
            start_date=start_date.strftime("%d/%m/%Y"),
            end_date=end_date.strftime("%d/%m/%Y"),
            pet_names=pet_names,
            notes=booking_data.notes or ""
        )
        asyncio.create_task(send_email(provider_email, subject, html))

    # Create in-app notification for provider
    await create_notification(
        user_id=provider["user_id"],
        title="Nueva reserva",
        message=f"{user['name']} solicito {booking_data.service_type} para {', '.join([p['name'] for p in pets_info])}",
        notification_type="new_booking"
    )
    
    return booking


@router.get("/bookings/my")
async def get_my_bookings(
    request: Request,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """Get bookings for current user (as client)"""
    user = await get_current_user(request, db)
    
    query = {"client_user_id": user["user_id"]}
    if status:
        query["status"] = status
    
    bookings = await db.bookings.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return bookings


@router.put("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: Request):
    """Cancel a booking (Client)"""
    user = await get_current_user(request, db)
    
    booking = await db.bookings.find_one({
        "booking_id": booking_id,
        "client_user_id": user["user_id"]
    })
    
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    
    if booking["status"] not in [BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value]:
        raise HTTPException(status_code=400, detail="Esta reserva no puede ser cancelada")
    
    await db.bookings.update_one(
        {"booking_id": booking_id},
        {"$set": {
            "status": BookingStatus.CANCELLED.value,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Notify provider
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": booking["provider_user_id"],
        "type": "booking_cancelled",
        "title": "Reserva cancelada",
        "message": f"{user['name']} ha cancelado su reserva",
        "data": {"booking_id": booking_id},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.notifications.insert_one(notification)
    
    return {"message": "Reserva cancelada"}


# ============= PROVIDER ENDPOINTS =============

@router.get("/bookings/provider")
async def get_provider_bookings(
    request: Request,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50
):
    """Get bookings for current provider"""
    user = await get_current_user(request, db)
    
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    
    query = {"provider_id": provider["provider_id"]}
    if status:
        query["status"] = status
    
    bookings = await db.bookings.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return bookings


@router.put("/bookings/{booking_id}/respond")
async def respond_to_booking(
    booking_id: str,
    update_data: BookingUpdate,
    request: Request
):
    """Accept or reject a booking (Provider)"""
    user = await get_current_user(request, db)
    
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    
    booking = await db.bookings.find_one({
        "booking_id": booking_id,
        "provider_id": provider["provider_id"]
    })
    
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    
    if booking["status"] != BookingStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Esta reserva ya fue procesada")
    
    if update_data.status not in [BookingStatus.CONFIRMED, BookingStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Estado no valido. Use 'confirmed' o 'rejected'")
    
    update_fields = {
        "status": update_data.status.value,
        "updated_at": datetime.now(timezone.utc)
    }
    if update_data.provider_notes:
        update_fields["provider_notes"] = update_data.provider_notes
    
    await db.bookings.update_one(
        {"booking_id": booking_id},
        {"$set": update_fields}
    )
    
    # Notify client
    status_text = "confirmada" if update_data.status == BookingStatus.CONFIRMED else "rechazada"
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": booking["client_user_id"],
        "type": f"booking_{update_data.status.value}",
        "title": f"Reserva {status_text}",
        "message": f"{provider['business_name']} ha {status_text} tu reserva",
        "data": {"booking_id": booking_id},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.notifications.insert_one(notification)
    
    # Send email to client
    client = await db.users.find_one({"user_id": booking["client_user_id"]})
    if client and client.get("email"):
        if update_data.status == BookingStatus.CONFIRMED:
            subject, html = booking_confirmed_email(
                client_name=client.get("name", "Cliente"),
                provider_name=provider["business_name"],
                service_type=booking["service_type"],
                start_date=booking["start_date"].strftime("%d/%m/%Y"),
                end_date=booking["end_date"].strftime("%d/%m/%Y"),
                provider_notes=update_data.provider_notes or ""
            )
        else:
            subject, html = booking_rejected_email(
                client_name=client.get("name", "Cliente"),
                provider_name=provider["business_name"],
                service_type=booking["service_type"],
                provider_notes=update_data.provider_notes or ""
            )
        asyncio.create_task(send_email(client["email"], subject, html))
    
    return {"message": f"Reserva {status_text}"}


@router.put("/bookings/{booking_id}/complete")
async def complete_booking(booking_id: str, request: Request):
    """Mark a booking as completed (Provider)"""
    user = await get_current_user(request, db)
    
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    
    booking = await db.bookings.find_one({
        "booking_id": booking_id,
        "provider_id": provider["provider_id"]
    })
    
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    
    if booking["status"] != BookingStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail="Solo se pueden completar reservas confirmadas")
    
    await db.bookings.update_one(
        {"booking_id": booking_id},
        {"$set": {
            "status": BookingStatus.COMPLETED.value,
            "completed_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    
    # Notify client to leave a review
    notification = {
        "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
        "user_id": booking["client_user_id"],
        "type": "booking_completed",
        "title": "Servicio completado",
        "message": f"Tu servicio con {provider['business_name']} ha sido completado. Dejale una resena!",
        "data": {"booking_id": booking_id, "provider_id": provider["provider_id"]},
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.notifications.insert_one(notification)
    
    return {"message": "Reserva completada"}


# ============= SHARED ENDPOINTS =============
# NOTE: Static routes (/history, /stats/summary) must be defined BEFORE dynamic route (/{booking_id})

@router.get("/bookings/history")
async def get_service_history(
    request: Request,
    skip: int = 0,
    limit: int = 50
):
    """Get completed/finished service history for the current user (client or provider)"""
    user = await get_current_user(request, db)

    # Check if user is a provider
    provider = await db.providers.find_one({"user_id": user["user_id"]})

    if provider:
        # Provider: get bookings as provider
        query = {
            "provider_id": provider["provider_id"],
            "status": {"$in": ["completed", "confirmed", "rejected", "cancelled"]}
        }
    else:
        # Client: get bookings as client
        query = {
            "client_user_id": user["user_id"],
            "status": {"$in": ["completed", "confirmed", "rejected", "cancelled"]}
        }

    bookings = await db.bookings.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    return bookings


@router.get("/bookings/stats/summary")
async def get_booking_stats(request: Request):
    """Get booking statistics for provider"""
    user = await get_current_user(request, db)
    
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=404, detail="No tienes perfil de proveedor")
    
    pipeline = [
        {"$match": {"provider_id": provider["provider_id"]}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    results = await db.bookings.aggregate(pipeline).to_list(10)
    
    stats = {
        "pending": 0,
        "confirmed": 0,
        "completed": 0,
        "rejected": 0,
        "cancelled": 0,
        "total": 0
    }
    
    for r in results:
        if r["_id"] in stats:
            stats[r["_id"]] = r["count"]
        stats["total"] += r["count"]
    
    return stats


@router.get("/bookings/{booking_id}")
async def get_booking_details(booking_id: str, request: Request):
    """Get booking details"""
    user = await get_current_user(request, db)
    
    booking = await db.bookings.find_one(
        {"booking_id": booking_id},
        {"_id": 0}
    )
    
    if not booking:
        raise HTTPException(status_code=404, detail="Reserva no encontrada")
    
    # Check access - must be client or provider
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    is_provider = provider and provider["provider_id"] == booking["provider_id"]
    is_client = booking["client_user_id"] == user["user_id"]
    
    if not (is_client or is_provider):
        raise HTTPException(status_code=403, detail="No autorizado")
    
    return booking
