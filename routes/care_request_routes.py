from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import asyncio

from database import db
from auth import get_current_user
from email_service import send_email, new_proposal_email
from routes.notification_routes import create_notification
from routes.contact_request_routes import create_connection

router = APIRouter()


class CareRequestCreate(BaseModel):
    service_type: str  # residencia, cuidado_domicilio, salud_mental
    patient_name: str
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = ""  # masculino, femenino, otro
    relationship: Optional[str] = ""  # hijo/a, nieto/a, conyuge, otro
    room_type: Optional[str] = ""  # individual, compartida, no_aplica
    special_needs: List[str] = []  # demencia, movilidad_reducida, oxigeno, medicacion, etc
    urgency: Optional[str] = "explorando"  # inmediata, dentro_1_mes, dentro_3_meses, explorando
    budget_min: Optional[int] = 0
    budget_max: Optional[int] = 0
    comuna: str
    region: Optional[str] = ""
    description: str


class CareRequestUpdate(BaseModel):
    description: Optional[str] = None
    preferred_dates: Optional[List[str]] = None
    comuna: Optional[str] = None
    flexible_dates: Optional[bool] = None
    status: Optional[str] = None


class ProposalCreate(BaseModel):
    care_request_id: str
    price: int  # CLP
    message: str
    available_dates: List[str] = []


class ProposalRespond(BaseModel):
    status: str  # "accepted" or "rejected"


@router.post("/care-requests")
async def create_care_request(data: CareRequestCreate, request: Request):
    """Create a senior care service request (client only)"""
    user = await get_current_user(request, db)

    if not data.patient_name.strip():
        raise HTTPException(status_code=400, detail="El nombre del paciente es obligatorio")
    if not data.description.strip():
        raise HTTPException(status_code=400, detail="La descripción es obligatoria")
    if not data.comuna.strip():
        raise HTTPException(status_code=400, detail="La comuna es obligatoria")

    request_id = f"care_{uuid.uuid4().hex[:12]}"
    care_request = {
        "request_id": request_id,
        "client_id": user["user_id"],
        "client_name": user.get("name", "Cliente"),
        "service_type": data.service_type,
        "patient_name": data.patient_name,
        "patient_age": data.patient_age,
        "patient_gender": data.patient_gender or "",
        "relationship": data.relationship or "",
        "room_type": data.room_type or "",
        "special_needs": data.special_needs or [],
        "urgency": data.urgency or "explorando",
        "budget_min": data.budget_min or 0,
        "budget_max": data.budget_max or 0,
        "comuna": data.comuna,
        "region": data.region or "",
        "description": data.description,
        "status": "active",
        "proposal_count": 0,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await db.care_requests.insert_one(care_request)
    care_request.pop("_id", None)
    return care_request


@router.get("/care-requests/my-requests")
async def get_my_care_requests(request: Request):
    """Get care requests created by the current client"""
    user = await get_current_user(request, db)
    
    requests = await db.care_requests.find(
        {"client_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return requests


@router.get("/care-requests")
async def get_care_requests_for_providers(
    request: Request,
    service_type: Optional[str] = None,
    comuna: Optional[str] = None
):
    """Get active care requests (subscribed providers only)"""
    user = await get_current_user(request, db)
    
    # Check if user is a provider
    provider = await db.providers.find_one({"user_id": user["user_id"], "approved": True})
    if not provider:
        raise HTTPException(status_code=403, detail="Solo proveedores pueden ver solicitudes")
    
    # Must have active subscription (premium carers only)
    subscription = await db.subscriptions.find_one({
        "user_id": user["user_id"],
        "status": "active"
    })
    
    if not subscription:
        raise HTTPException(status_code=403, detail="Necesitas suscripcion Premium para ver solicitudes de clientes")
    
    # Full access for subscribed providers
    query = {"status": "active"}
    if service_type:
        query["service_type"] = service_type
    if comuna:
        query["comuna"] = {"$regex": comuna, "$options": "i"}
    
    requests = await db.care_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    
    # Add client info for subscribed providers
    for req in requests:
        client = await db.users.find_one(
            {"user_id": req["client_id"]},
            {"_id": 0, "picture": 1}
        )
        if client:
            req["client_picture"] = client.get("picture")
        req["contact_hidden"] = False
    
    return requests


@router.get("/care-requests/{request_id}")
async def get_care_request(request_id: str, request: Request):
    """Get a specific care request"""
    user = await get_current_user(request, db)
    
    care_request = await db.care_requests.find_one(
        {"request_id": request_id},
        {"_id": 0}
    )
    
    if not care_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    # If requesting user is the client, return full info
    if care_request["client_id"] == user["user_id"]:
        return care_request
    
    # If requesting user is a provider, check subscription
    provider = await db.providers.find_one({"user_id": user["user_id"], "approved": True})
    if not provider:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    subscription = await db.subscriptions.find_one({
        "user_id": user["user_id"],
        "status": "active"
    })
    
    if not subscription:
        # Limited info for non-subscribed providers
        care_request["client_name"] = care_request.get("client_name", "Cliente").split()[0]
        care_request["contact_hidden"] = True
        return care_request
    
    # Full info for subscribed providers
    client = await db.users.find_one(
        {"user_id": care_request["client_id"]},
        {"_id": 0, "email": 1, "phone": 1, "picture": 1}
    )
    if client:
        care_request["client_email"] = client.get("email")
        care_request["client_phone"] = client.get("phone")
        care_request["client_picture"] = client.get("picture")
    care_request["contact_hidden"] = False
    
    return care_request


@router.put("/care-requests/{request_id}")
async def update_care_request(request_id: str, data: CareRequestUpdate, request: Request):
    """Update a care request (client only)"""
    user = await get_current_user(request, db)
    
    care_request = await db.care_requests.find_one({
        "request_id": request_id,
        "client_id": user["user_id"]
    })
    
    if not care_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)
    
    await db.care_requests.update_one(
        {"request_id": request_id},
        {"$set": update_data}
    )
    
    updated = await db.care_requests.find_one({"request_id": request_id}, {"_id": 0})
    return updated


@router.delete("/care-requests/{request_id}")
async def delete_care_request(request_id: str, request: Request):
    """Delete a care request (client only)"""
    user = await get_current_user(request, db)
    
    result = await db.care_requests.delete_one({
        "request_id": request_id,
        "client_id": user["user_id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    
    return {"message": "Solicitud eliminada"}


# ==================== PROPOSALS ====================

@router.post("/proposals")
async def create_proposal(data: ProposalCreate, request: Request):
    """Create a proposal for a care request (subscribed provider only)"""
    user = await get_current_user(request, db)

    # Must be an approved provider
    provider = await db.providers.find_one({"user_id": user["user_id"], "approved": True})
    if not provider:
        raise HTTPException(status_code=403, detail="Solo proveedores aprobados pueden enviar propuestas")

    # Must have active subscription
    subscription = await db.subscriptions.find_one({"user_id": user["user_id"], "status": "active"})
    if not subscription:
        raise HTTPException(status_code=403, detail="Necesitas una suscripcion Premium para enviar propuestas")

    # Care request must exist and be active
    care_request = await db.care_requests.find_one({"request_id": data.care_request_id, "status": "active"})
    if not care_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada o no esta activa")

    # Can't propose to own request
    if care_request["client_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="No puedes enviar propuesta a tu propia solicitud")

    # Check for existing pending proposal
    existing = await db.proposals.find_one({
        "care_request_id": data.care_request_id,
        "provider_id": user["user_id"],
        "status": "pending"
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya enviaste una propuesta para esta solicitud")

    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
    proposal = {
        "proposal_id": proposal_id,
        "care_request_id": data.care_request_id,
        "provider_id": user["user_id"],
        "provider_name": user.get("name", "Cuidador"),
        "provider_business_name": provider.get("business_name", "Cuidador"),
        "provider_photo": provider.get("photos", [None])[0],
        "provider_verified": provider.get("verified", False),
        "provider_rating": provider.get("rating"),
        "provider_provider_id": provider.get("provider_id"),
        "price": data.price,
        "message": data.message,
        "available_dates": data.available_dates,
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    await db.proposals.insert_one(proposal)
    proposal.pop("_id", None)

    # Update proposal count on care request
    await db.care_requests.update_one(
        {"request_id": data.care_request_id},
        {"$inc": {"proposal_count": 1}}
    )

    # Send email notification to client
    client = await db.users.find_one(
        {"user_id": care_request["client_id"]},
        {"_id": 0, "email": 1, "name": 1}
    )
    if client and client.get("email"):
        subject, html = new_proposal_email(
            client_name=client.get("name", "Cliente"),
            provider_name=provider.get("business_name", user.get("name", "Cuidador")),
            price=data.price,
            message=data.message,
            pet_name=care_request.get("pet_name", "tu mascota"),
            service_type=care_request.get("service_type", "cuidado")
        )
        asyncio.create_task(send_email(client["email"], subject, html))

    # Create in-app notification for client
    await create_notification(
        user_id=care_request["client_id"],
        title="Nueva propuesta recibida",
        message=f"{provider.get('business_name', 'Cuidador')} te envio una propuesta por ${'{:,}'.format(data.price).replace(',','.')} para {care_request.get('pet_name', 'tu mascota')}",
        notification_type="new_proposal"
    )

    return proposal


@router.get("/proposals/my-sent")
async def get_my_sent_proposals(request: Request):
    """Get proposals sent by the current provider"""
    user = await get_current_user(request, db)

    proposals = await db.proposals.find(
        {"provider_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    # Enrich with care request info
    for prop in proposals:
        care_req = await db.care_requests.find_one(
            {"request_id": prop["care_request_id"]},
            {"_id": 0, "pet_name": 1, "service_type": 1, "comuna": 1, "client_name": 1}
        )
        if care_req:
            prop["care_request_info"] = care_req

    return proposals


@router.get("/proposals/received")
async def get_received_proposals(request: Request):
    """Get all proposals received by the current client"""
    user = await get_current_user(request, db)

    # Get client's care requests
    my_requests = await db.care_requests.find(
        {"client_id": user["user_id"]},
        {"_id": 0, "request_id": 1}
    ).to_list(100)
    request_ids = [r["request_id"] for r in my_requests]

    if not request_ids:
        return []

    proposals = await db.proposals.find(
        {"care_request_id": {"$in": request_ids}},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Enrich with care request info
    for prop in proposals:
        care_req = await db.care_requests.find_one(
            {"request_id": prop["care_request_id"]},
            {"_id": 0, "pet_name": 1, "service_type": 1, "comuna": 1, "description": 1}
        )
        if care_req:
            prop["care_request_info"] = care_req

    return proposals


@router.get("/proposals/for-request/{request_id}")
async def get_proposals_for_request(request_id: str, request: Request):
    """Get proposals for a specific care request (client only)"""
    user = await get_current_user(request, db)

    # Verify client owns this request
    care_request = await db.care_requests.find_one({
        "request_id": request_id,
        "client_id": user["user_id"]
    })
    if not care_request:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    proposals = await db.proposals.find(
        {"care_request_id": request_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return proposals


@router.put("/proposals/{proposal_id}/respond")
async def respond_to_proposal(proposal_id: str, data: ProposalRespond, request: Request):
    """Accept or reject a proposal (client only)"""
    user = await get_current_user(request, db)

    if data.status not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="Estado debe ser 'accepted' o 'rejected'")

    proposal = await db.proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})
    if not proposal:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")

    # Verify client owns the care request
    care_request = await db.care_requests.find_one({
        "request_id": proposal["care_request_id"],
        "client_id": user["user_id"]
    })
    if not care_request:
        raise HTTPException(status_code=403, detail="No autorizado")

    await db.proposals.update_one(
        {"proposal_id": proposal_id},
        {"$set": {"status": data.status, "updated_at": datetime.now(timezone.utc)}}
    )

    # If accepted, update care request status, reject other proposals, and create connection
    if data.status == "accepted":
        await db.care_requests.update_one(
            {"request_id": proposal["care_request_id"]},
            {"$set": {"status": "completed", "accepted_proposal_id": proposal_id, "updated_at": datetime.now(timezone.utc)}}
        )
        # Reject other pending proposals for this request
        await db.proposals.update_many(
            {
                "care_request_id": proposal["care_request_id"],
                "proposal_id": {"$ne": proposal_id},
                "status": "pending"
            },
            {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc)}}
        )
        # Create connection → unlocks chat
        await create_connection(
            client_user_id=user["user_id"],
            provider_user_id=proposal["provider_id"],
            connection_type="proposal_accepted",
            source_id=proposal_id
        )

    updated = await db.proposals.find_one({"proposal_id": proposal_id}, {"_id": 0})

    # Notify provider about response
    if data.status == "accepted":
        await create_notification(
            user_id=proposal["provider_id"],
            title="Propuesta aceptada!",
            message=f"Tu propuesta por ${'{:,}'.format(proposal['price']).replace(',','.')} fue aceptada. Contacta al cliente para coordinar.",
            notification_type="proposal_accepted"
        )
    else:
        await create_notification(
            user_id=proposal["provider_id"],
            title="Propuesta rechazada",
            message=f"Tu propuesta por ${'{:,}'.format(proposal['price']).replace(',','.')} no fue aceptada.",
            notification_type="proposal_rejected"
        )

    return updated
