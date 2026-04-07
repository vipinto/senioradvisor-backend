from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime, timezone
import uuid
from database import db

router = APIRouter(prefix="/podcast", tags=["podcast"])

# ============= CATEGORIES =============

@router.get("/categories")
async def get_podcast_categories():
    cats = await db.podcast_categories.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    return cats

@router.post("/categories")
async def create_podcast_category(data: dict):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    existing = await db.podcast_categories.find_one({"name": name})
    if existing:
        raise HTTPException(status_code=400, detail="Categoria ya existe")
    max_order = await db.podcast_categories.find({}).sort("order", -1).to_list(1)
    order = (max_order[0]["order"] + 1) if max_order else 0
    cat = {"category_id": str(uuid.uuid4()), "name": name, "description": data.get("description", ""), "logo": data.get("logo", ""), "order": order}
    await db.podcast_categories.insert_one(cat)
    del cat["_id"]
    return cat

@router.put("/categories/{category_id}")
async def update_podcast_category(category_id: str, data: dict):
    update = {}
    if "name" in data:
        update["name"] = data["name"].strip()
    if "description" in data:
        update["description"] = data["description"].strip()
    if "logo" in data:
        update["logo"] = data["logo"]
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    result = await db.podcast_categories.update_one({"category_id": category_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    cat = await db.podcast_categories.find_one({"category_id": category_id}, {"_id": 0})
    return cat

@router.delete("/categories/{category_id}")
async def delete_podcast_category(category_id: str):
    result = await db.podcast_categories.delete_one({"category_id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    await db.podcast_episodes.delete_many({"category": category_id})
    return {"status": "deleted"}

# ============= EPISODES =============

@router.get("/episodes")
async def get_episodes():
    episodes = await db.podcast_episodes.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return episodes

@router.post("/episodes")
async def create_episode(data: dict):
    youtube_url = data.get("youtube_url", "").strip()
    title = data.get("title", "").strip()
    if not youtube_url or not title:
        raise HTTPException(status_code=400, detail="URL y titulo requeridos")
    episode = {
        "episode_id": str(uuid.uuid4()),
        "youtube_url": youtube_url,
        "title": title,
        "description": data.get("description", ""),
        "category": data.get("category", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.podcast_episodes.insert_one(episode)
    del episode["_id"]
    return episode

@router.put("/episodes/{episode_id}")
async def update_episode(episode_id: str, data: dict):
    update = {k: v for k, v in data.items() if k in ("youtube_url", "title", "description", "category") and v is not None}
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    result = await db.podcast_episodes.update_one({"episode_id": episode_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    ep = await db.podcast_episodes.find_one({"episode_id": episode_id}, {"_id": 0})
    return ep

@router.delete("/episodes/{episode_id}")
async def delete_episode(episode_id: str):
    result = await db.podcast_episodes.delete_one({"episode_id": episode_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Episodio no encontrado")
    return {"status": "deleted"}
