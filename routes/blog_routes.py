from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import uuid
from database import db

router = APIRouter(prefix="/blog", tags=["blog"])

class ArticleCreate(BaseModel):
    title: str
    excerpt: str
    content: str
    image: Optional[str] = ""
    youtube_url: Optional[str] = ""
    category: Optional[str] = ""
    slug: Optional[str] = None

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    youtube_url: Optional[str] = None
    category: Optional[str] = None
    published: Optional[bool] = None

@router.get("/articles")
async def get_articles(limit: int = 200, published_only: bool = True):
    query = {"published": True} if published_only else {}
    articles = await db.blog_articles.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return articles

@router.get("/articles/{slug}")
async def get_article(slug: str):
    article = await db.blog_articles.find_one({"slug": slug}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")
    return article

@router.post("/articles")
async def create_article(data: ArticleCreate):
    slug = data.slug or data.title.lower().replace(" ", "-").replace(":", "").replace("a\u0301", "a").replace("e\u0301", "e").replace("i\u0301", "i").replace("o\u0301", "o").replace("u\u0301", "u").replace("n\u0303", "n").replace("\u00e1", "a").replace("\u00e9", "e").replace("\u00ed", "i").replace("\u00f3", "o").replace("\u00fa", "u").replace("\u00f1", "n")
    
    existing = await db.blog_articles.find_one({"slug": slug})
    if existing:
        slug = f"{slug}-{str(uuid.uuid4())[:6]}"
    
    article = {
        "article_id": str(uuid.uuid4()),
        "slug": slug,
        "title": data.title,
        "excerpt": data.excerpt,
        "content": data.content,
        "image": data.image or "",
        "youtube_url": data.youtube_url or "",
        "category": data.category or "",
        "published": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.blog_articles.insert_one(article)
    del article["_id"]
    return article

@router.put("/articles/{article_id}")
async def update_article(article_id: str, data: ArticleUpdate):
    update = {k: v for k, v in data.dict().items() if v is not None}
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    result = await db.blog_articles.update_one(
        {"article_id": article_id},
        {"$set": update}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")
    
    article = await db.blog_articles.find_one({"article_id": article_id}, {"_id": 0})
    return article

@router.delete("/articles/{article_id}")
async def delete_article(article_id: str):
    result = await db.blog_articles.delete_one({"article_id": article_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Articulo no encontrado")
    return {"status": "deleted"}

# ============= CATEGORIES =============

@router.get("/categories")
async def get_categories():
    cats = await db.blog_categories.find({}, {"_id": 0}).sort("order", 1).to_list(50)
    if not cats:
        defaults = [
            {"category_id": str(uuid.uuid4()), "name": "Editorial", "description": "Conoce los lineamientos que guían a SeniorAdvisor, donde abordamos problemáticas actuales de las personas mayores.", "order": 0},
            {"category_id": str(uuid.uuid4()), "name": "Actualidad", "description": "Mantente informado con las últimas noticias y tendencias del mundo de la tercera edad.", "order": 1},
            {"category_id": str(uuid.uuid4()), "name": "Beneficios", "description": "Guía completa de beneficios, ayudas estatales y actualizaciones legislativas para la tercera edad en Chile.", "order": 2},
            {"category_id": str(uuid.uuid4()), "name": "Formación", "description": "Descubre una selección curada de talleres, cursos y oportunidades de capacitación para las personas mayores.", "order": 3},
        ]
        await db.blog_categories.insert_many(defaults)
        for d in defaults:
            del d["_id"]
        return defaults
    return cats

@router.post("/categories")
async def create_category(data: dict):
    name = data.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nombre requerido")
    existing = await db.blog_categories.find_one({"name": name})
    if existing:
        raise HTTPException(status_code=400, detail="Categoria ya existe")
    max_order = await db.blog_categories.find({}).sort("order", -1).to_list(1)
    order = (max_order[0]["order"] + 1) if max_order else 0
    cat = {"category_id": str(uuid.uuid4()), "name": name, "description": data.get("description", ""), "order": order}
    await db.blog_categories.insert_one(cat)
    del cat["_id"]
    return cat

@router.put("/categories/{category_id}")
async def update_category(category_id: str, data: dict):
    update = {}
    if "name" in data:
        update["name"] = data["name"].strip()
    if "description" in data:
        update["description"] = data["description"].strip()
    if not update:
        raise HTTPException(status_code=400, detail="Nada que actualizar")
    result = await db.blog_categories.update_one({"category_id": category_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    cat = await db.blog_categories.find_one({"category_id": category_id}, {"_id": 0})
    return cat

@router.delete("/categories/{category_id}")
async def delete_category(category_id: str):
    result = await db.blog_categories.delete_one({"category_id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Categoria no encontrada")
    return {"status": "deleted"}
