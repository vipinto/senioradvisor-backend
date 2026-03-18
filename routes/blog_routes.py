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
    image: str
    slug: Optional[str] = None

class ArticleUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    image: Optional[str] = None
    published: Optional[bool] = None

@router.get("/articles")
async def get_articles(limit: int = 50, published_only: bool = True):
    query = {"published": True} if published_only else {}
    articles = await db.blog_articles.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return articles

@router.get("/articles/{slug}")
async def get_article(slug: str):
    article = await db.blog_articles.find_one({"slug": slug}, {"_id": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return article

@router.post("/articles")
async def create_article(data: ArticleCreate):
    slug = data.slug or data.title.lower().replace(" ", "-").replace(":", "").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    
    existing = await db.blog_articles.find_one({"slug": slug})
    if existing:
        slug = f"{slug}-{str(uuid.uuid4())[:6]}"
    
    article = {
        "article_id": str(uuid.uuid4()),
        "slug": slug,
        "title": data.title,
        "excerpt": data.excerpt,
        "content": data.content,
        "image": data.image,
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
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    
    article = await db.blog_articles.find_one({"article_id": article_id}, {"_id": 0})
    return article

@router.delete("/articles/{article_id}")
async def delete_article(article_id: str):
    result = await db.blog_articles.delete_one({"article_id": article_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Artículo no encontrado")
    return {"status": "deleted"}
