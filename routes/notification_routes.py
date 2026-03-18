from fastapi import APIRouter, Request
import uuid
from datetime import datetime, timezone

from database import db
from auth import get_current_user

router = APIRouter()


async def create_notification(user_id: str, title: str, message: str, notification_type: str):
    """Create a notification for a user"""
    notification_id = f"notif_{uuid.uuid4().hex[:12]}"
    notification = {
        "notification_id": notification_id,
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notification_type,
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.notifications.insert_one(notification)
    return notification


@router.get("/notifications")
async def get_notifications(request: Request):
    """Get user's notifications"""
    user = await get_current_user(request, db)
    notifications = await db.notifications.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifications


@router.get("/notifications/unread-count")
async def get_unread_count(request: Request):
    """Get count of unread notifications"""
    user = await get_current_user(request, db)
    count = await db.notifications.count_documents({
        "user_id": user["user_id"],
        "read": False
    })
    return {"count": count}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    """Mark notification as read"""
    user = await get_current_user(request, db)
    await db.notifications.update_one(
        {"notification_id": notification_id, "user_id": user["user_id"]},
        {"$set": {"read": True}}
    )
    return {"message": "Marcada como leída"}


@router.post("/notifications/read-all")
async def mark_all_notifications_read(request: Request):
    """Mark all notifications as read"""
    user = await get_current_user(request, db)
    await db.notifications.update_many(
        {"user_id": user["user_id"], "read": False},
        {"$set": {"read": True}}
    )
    return {"message": "Todas marcadas como leídas"}
