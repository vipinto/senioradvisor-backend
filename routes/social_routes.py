from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from datetime import datetime, timezone, timedelta
import uuid

from database import db, UPLOADS_DIR
from models import ReviewCreate, ClientReviewCreate
from auth import get_current_user, require_subscription

router = APIRouter()


# ============= REVIEW PUBLISHING CRON =============

@router.post("/reviews/publish-expired")
async def publish_expired_reviews():
    """Publish all reviews that have passed their blind period.
    This endpoint should be called by a cron job."""
    now = datetime.now(timezone.utc)

    # Publish expired provider reviews
    provider_result = await db.reviews.update_many(
        {"published": False, "publish_after": {"$lte": now}},
        {"$set": {"published": True}}
    )

    # Publish expired client reviews
    client_result = await db.client_reviews.update_many(
        {"published": False, "publish_after": {"$lte": now}},
        {"$set": {"published": True}}
    )

    # Recalculate ratings for newly published reviews
    newly_published_provider = await db.reviews.find(
        {"published": True, "rating_recalculated": {"$ne": True}},
        {"_id": 0, "provider_id": 1, "review_id": 1}
    ).to_list(500)

    for review in newly_published_provider:
        await recalculate_provider_rating(review["provider_id"])
        await db.reviews.update_one(
            {"review_id": review["review_id"]},
            {"$set": {"rating_recalculated": True}}
        )

    newly_published_client = await db.client_reviews.find(
        {"published": True, "rating_recalculated": {"$ne": True}},
        {"_id": 0, "client_user_id": 1, "review_id": 1}
    ).to_list(500)

    for review in newly_published_client:
        await recalculate_client_rating(review["client_user_id"])
        await db.client_reviews.update_one(
            {"review_id": review["review_id"]},
            {"$set": {"rating_recalculated": True}}
        )

    return {
        "message": "Reseñas publicadas",
        "provider_reviews_published": provider_result.modified_count,
        "client_reviews_published": client_result.modified_count
    }


# ============= FAVORITES =============

@router.post("/favorites/{provider_id}")
async def add_favorite(provider_id: str, request: Request):
    """Add provider to favorites"""
    user = await get_current_user(request, db)

    existing = await db.favorites.find_one({
        "user_id": user["user_id"],
        "provider_id": provider_id
    })
    if existing:
        return {"message": "Ya está en favoritos"}

    favorite_id = f"fav_{uuid.uuid4().hex[:12]}"
    favorite = {
        "favorite_id": favorite_id,
        "user_id": user["user_id"],
        "provider_id": provider_id,
        "created_at": datetime.now(timezone.utc)
    }
    await db.favorites.insert_one(favorite)
    return {"message": "Añadido a favoritos"}


@router.delete("/favorites/{provider_id}")
async def remove_favorite(provider_id: str, request: Request):
    """Remove provider from favorites"""
    user = await get_current_user(request, db)

    result = await db.favorites.delete_one({
        "user_id": user["user_id"],
        "provider_id": provider_id
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorito no encontrado")
    return {"message": "Eliminado de favoritos"}


@router.get("/favorites")
async def get_my_favorites(request: Request):
    """Get user's favorite providers"""
    user = await get_current_user(request, db)

    favorites = await db.favorites.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).to_list(100)

    provider_ids = [f["provider_id"] for f in favorites]
    providers = await db.providers.find(
        {"provider_id": {"$in": provider_ids}},
        {"_id": 0}
    ).to_list(100)
    return providers


@router.get("/favorites/check/{provider_id}")
async def check_favorite(provider_id: str, request: Request):
    """Check if provider is in user's favorites"""
    user = await get_current_user(request, db)

    favorite = await db.favorites.find_one({
        "user_id": user["user_id"],
        "provider_id": provider_id
    })
    return {"is_favorite": favorite is not None}


# ============= REVIEWS =============

@router.post("/reviews/upload-photo")
async def upload_review_photo(file: UploadFile = File(...), request: Request = None):
    """Upload a photo for a review"""
    user = await get_current_user(request, db)
    # Sin restricción de suscripción para clientes

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten imagenes")

    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex[:16]}.{ext}"
    filepath = UPLOADS_DIR / "reviews" / filename
    (UPLOADS_DIR / "reviews").mkdir(exist_ok=True)

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="La imagen no puede superar los 5MB")

    with open(filepath, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/reviews/{filename}"
    return {"url": photo_url}


@router.post("/reviews")
async def create_review(review_data: ReviewCreate, request: Request):
    """Client reviews a provider"""
    user = await get_current_user(request, db)
    # Removido require_subscription - cualquier usuario logueado puede dejar reseña

    existing = await db.reviews.find_one({
        "user_id": user["user_id"],
        "provider_id": review_data.provider_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya has reseñado este servicio")

    # Get provider's user_id for the blind pair
    provider = await db.providers.find_one({"provider_id": review_data.provider_id})
    provider_user_id = provider["user_id"] if provider else None

    review_id = f"rev_{uuid.uuid4().hex[:12]}"
    review = {
        "review_id": review_id,
        "user_id": user["user_id"],
        **review_data.model_dump(),
        "moderated": False,
        "approved": True,
        "published": False,
        "publish_after": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.reviews.insert_one(review)

    # Check if carer already reviewed this client → publish both
    if provider_user_id:
        counter_review = await db.client_reviews.find_one({
            "provider_user_id": provider_user_id,
            "client_user_id": user["user_id"],
            "published": False
        })
        if counter_review:
            await db.reviews.update_one({"review_id": review_id}, {"$set": {"published": True}})
            await db.client_reviews.update_one({"review_id": counter_review["review_id"]}, {"$set": {"published": True}})
            await _update_provider_rating(review_data.provider_id)
            await _update_client_rating(user["user_id"])

    review.pop("_id", None)
    return {**review, "message": "Calificacion guardada. Se publicara cuando ambos califiquen o en 7 dias."}


async def _update_provider_rating(provider_id: str):
    """Recalculate provider rating from published reviews"""
    all_reviews = await db.reviews.find(
        {"provider_id": provider_id, "approved": True, "published": True},
        {"_id": 0, "rating": 1}
    ).to_list(1000)
    if all_reviews:
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        await db.providers.update_one(
            {"provider_id": provider_id},
            {"$set": {"rating": round(avg, 1), "total_reviews": len(all_reviews)}}
        )


async def _update_client_rating(client_user_id: str):
    """Recalculate client rating from published reviews"""
    all_reviews = await db.client_reviews.find(
        {"client_user_id": client_user_id, "published": True},
        {"_id": 0, "rating": 1}
    ).to_list(1000)
    if all_reviews:
        avg = sum(r["rating"] for r in all_reviews) / len(all_reviews)
        await db.users.update_one(
            {"user_id": client_user_id},
            {"$set": {"client_rating": round(avg, 1), "total_client_reviews": len(all_reviews)}}
        )


# ============= CLIENT REVIEWS (by carers) =============

@router.post("/reviews/client")
async def create_client_review(data: ClientReviewCreate, request: Request):
    """Carer reviews a client"""
    user = await get_current_user(request, db)

    # Verify the reviewer is a provider
    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=403, detail="Solo proveedores pueden calificar clientes")

    # Check client exists
    client = await db.users.find_one({"user_id": data.client_user_id})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    # Check not already reviewed
    existing = await db.client_reviews.find_one({
        "provider_user_id": user["user_id"],
        "client_user_id": data.client_user_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="Ya has calificado a este cliente")

    review_id = f"crev_{uuid.uuid4().hex[:12]}"
    review = {
        "review_id": review_id,
        "provider_user_id": user["user_id"],
        "provider_id": provider["provider_id"],
        "provider_name": provider.get("business_name", "Cuidador"),
        "client_user_id": data.client_user_id,
        "rating": data.rating,
        "punctuality": data.punctuality,
        "pet_behavior": data.pet_behavior,
        "communication": data.communication,
        "comment": data.comment,
        "published": False,
        "publish_after": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc)
    }
    await db.client_reviews.insert_one(review)

    # Check if client already reviewed this provider → publish both
    counter_review = await db.reviews.find_one({
        "user_id": data.client_user_id,
        "provider_id": provider["provider_id"],
        "published": False
    })
    if counter_review:
        await db.client_reviews.update_one({"review_id": review_id}, {"$set": {"published": True}})
        await db.reviews.update_one({"review_id": counter_review["review_id"]}, {"$set": {"published": True}})
        await _update_provider_rating(provider["provider_id"])
        await _update_client_rating(data.client_user_id)

    review.pop("_id", None)
    return {**review, "message": "Calificacion guardada. Se publicara cuando ambos califiquen o en 7 dias."}


@router.get("/reviews/client/me")
async def get_my_client_reviews(request: Request):
    """Get published reviews about the current user as a client"""
    user = await get_current_user(request, db)

    reviews = await db.client_reviews.find(
        {"client_user_id": user["user_id"], "$or": [{"published": True}, {"published": {"$exists": False}}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    return reviews


@router.get("/reviews/client/{user_id}")
async def get_client_reviews(user_id: str, request: Request):
    """Get published reviews for a client"""
    await get_current_user(request, db)

    reviews = await db.client_reviews.find(
        {"client_user_id": user_id, "$or": [{"published": True}, {"published": {"$exists": False}}]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)

    client = await db.users.find_one({"user_id": user_id}, {"_id": 0, "name": 1, "picture": 1, "client_rating": 1, "total_client_reviews": 1})

    return {
        "client": client,
        "reviews": reviews
    }


@router.get("/reviews/provider/given")
async def get_reviews_given_by_provider(request: Request):
    """Get all client reviews given by the current provider"""
    user = await get_current_user(request, db)

    provider = await db.providers.find_one({"user_id": user["user_id"]})
    if not provider:
        raise HTTPException(status_code=403, detail="No tienes perfil de proveedor")

    reviews = await db.client_reviews.find(
        {"provider_user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    # Enrich with client info
    for review in reviews:
        client = await db.users.find_one(
            {"user_id": review["client_user_id"]},
            {"_id": 0, "name": 1, "picture": 1}
        )
        if client:
            review["client_name"] = client.get("name", "Cliente")
            review["client_picture"] = client.get("picture")

    return reviews
