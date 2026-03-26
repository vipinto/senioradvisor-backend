from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import uuid
from database import db

router = APIRouter(prefix="/partners", tags=["partners"])

# --- Convenios CRUD ---

class PlanModel(BaseModel):
    name: str
    category: str
    price: str
    uf: str

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

class ConvenioUpdate(BaseModel):
    name: Optional[str] = None
    logo: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    plans: Optional[List[PlanModel]] = None
    featured: Optional[bool] = None
    active: Optional[bool] = None
    discount_code: Optional[str] = None

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
