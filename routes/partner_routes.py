from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
import asyncio
import os
from database import db
from email_service import send_email

router = APIRouter(prefix="/partners", tags=["partners"])

# --- Convenios CRUD ---

class PlanModel(BaseModel):
    name: str
    category: str
    price: str
    uf: str
    currency: Optional[str] = "UF"
    popular: Optional[bool] = False

class ConvenioCreate(BaseModel):
    name: str
    slug: Optional[str] = ""
    logo: str
    description: str
    location: Optional[str] = ""
    plans: List[PlanModel] = []
    featured: bool = False
    active: bool = True
    discount_code: Optional[str] = ""
    contact_email: Optional[str] = ""
    website: Optional[str] = ""

class ConvenioUpdate(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    plans: Optional[List[PlanModel]] = None
    featured: Optional[bool] = None
    active: Optional[bool] = None
    discount_code: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None

@router.get("/convenios")
async def get_convenios(active_only: bool = True):
    query = {"active": True} if active_only else {}
    convenios = await db.convenios.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return convenios

@router.post("/convenios")
async def create_convenio(data: ConvenioCreate):
    slug = data.slug or data.name.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    convenio = {
        "convenio_id": str(uuid.uuid4()),
        "slug": slug,
        "name": data.name,
        "logo": data.logo,
        "description": data.description,
        "location": data.location,
        "plans": [p.dict() for p in data.plans],
        "featured": data.featured,
        "active": data.active,
        "discount_code": data.discount_code or "",
        "contact_email": data.contact_email or "",
        "website": data.website or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.convenios.insert_one(convenio)
    del convenio["_id"]
    return convenio

@router.put("/convenios/{convenio_id}")
async def update_convenio(convenio_id: str, data: ConvenioUpdate):
    update = {}
    for k, v in data.dict().items():
        if v is not None:
            if k == "plans":
                update[k] = [p for p in v]
            else:
                update[k] = v
    result = await db.convenios.update_one({"convenio_id": convenio_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    convenio = await db.convenios.find_one({"convenio_id": convenio_id}, {"_id": 0})
    return convenio

@router.delete("/convenios/{convenio_id}")
async def delete_convenio(convenio_id: str):
    result = await db.convenios.delete_one({"convenio_id": convenio_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Convenio no encontrado")
    return {"status": "deleted"}

# --- Leads ---

class PartnerLeadCreate(BaseModel):
    partner_slug: str
    name: str
    email: str
    phone: str
    contact_type: Optional[str] = ""
    plan_interest: Optional[str] = ""

@router.post("/leads")
async def create_lead(data: PartnerLeadCreate):
    lead = {
        "lead_id": str(uuid.uuid4()),
        "partner_slug": data.partner_slug,
        "name": data.name,
        "email": data.email,
        "phone": data.phone,
        "contact_type": data.contact_type,
        "plan_interest": data.plan_interest,
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.partner_leads.insert_one(lead)
    del lead["_id"]

    # Send email to convenio partners if configured
    convenio = await db.convenios.find_one({"slug": data.partner_slug}, {"_id": 0})
    if convenio and convenio.get("contact_email"):
        convenio_name = convenio.get("name", data.partner_slug)
        partner_html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
          <h2 style="color:#33404f;">Nueva solicitud desde SeniorAdvisor</h2>
          <p>Una persona está interesada en sus servicios a través de SeniorClub:</p>
          <table style="width:100%;border-collapse:collapse;">
            <tr><td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">Nombre</td><td style="padding:8px;border-bottom:1px solid #eee;">{data.name}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">Email</td><td style="padding:8px;border-bottom:1px solid #eee;">{data.email}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">Teléfono</td><td style="padding:8px;border-bottom:1px solid #eee;">{data.phone}</td></tr>
            <tr><td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;">Plan de interés</td><td style="padding:8px;border-bottom:1px solid #eee;">{data.plan_interest or '-'}</td></tr>
          </table>
          <p style="color:#999;font-size:12px;margin-top:20px;">Enviado desde SeniorAdvisor.cl</p>
        </div>
        """
        emails = [e.strip() for e in convenio["contact_email"].split(",") if e.strip()]
        for email_addr in emails:
            asyncio.create_task(send_email(email_addr, f"Nueva solicitud SeniorAdvisor - {data.name}", partner_html))

    return lead

@router.get("/leads")
async def get_leads(partner_slug: Optional[str] = None):
    query = {}
    if partner_slug:
        query["partner_slug"] = partner_slug
    leads = await db.partner_leads.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return leads

@router.get("/leads/stats")
async def get_lead_stats():
    pipeline = [
        {"$group": {"_id": "$partner_slug", "total": {"$sum": 1}}},
    ]
    stats = await db.partner_leads.aggregate(pipeline).to_list(100)
    return {s["_id"]: s["total"] for s in stats}
