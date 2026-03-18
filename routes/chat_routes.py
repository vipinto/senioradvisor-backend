from fastapi import APIRouter, Request, HTTPException
from datetime import datetime, timezone
import asyncio

from database import db
from models import ChatMessageCreate
from auth import get_current_user
from email_service import send_email, new_message_email
from routes.notification_routes import create_notification
from routes.contact_request_routes import check_connection

router = APIRouter(prefix="/chat")


@router.post("/messages")
async def send_message(message_data: ChatMessageCreate, request: Request):
    """Send chat message. Only between connected users."""
    user = await get_current_user(request, db)

    # Check connection exists between users
    connected = await check_connection(user["user_id"], message_data.receiver_id)
    if not connected:
        raise HTTPException(
            status_code=403,
            detail="No tienes conexion con este usuario. El chat se desbloquea cuando ambas partes aceptan."
        )

    import uuid
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    conversation_id = f"{min(user['user_id'], message_data.receiver_id)}_{max(user['user_id'], message_data.receiver_id)}"

    message = {
        "message_id": message_id,
        "conversation_id": conversation_id,
        "sender_id": user["user_id"],
        "receiver_id": message_data.receiver_id,
        "message": message_data.message,
        "read": False,
        "created_at": datetime.now(timezone.utc)
    }
    await db.chat_messages.insert_one(message)
    message.pop("_id", None)

    # Send email notification to receiver (only for first message or after 30 min)
    messages_in_window = await db.chat_messages.count_documents({
        "conversation_id": conversation_id,
        "sender_id": user["user_id"],
        "created_at": {"$gte": datetime.now(timezone.utc) - __import__('datetime').timedelta(minutes=30)}
    })

    if messages_in_window <= 1:
        receiver = await db.users.find_one({"user_id": message_data.receiver_id})
        if receiver and receiver.get("email"):
            subject, html = new_message_email(
                recipient_name=receiver.get("name", "Usuario"),
                sender_name=user.get("name", "Usuario"),
                message_preview=message_data.message
            )
            asyncio.create_task(send_email(receiver["email"], subject, html))

        await create_notification(
            user_id=message_data.receiver_id,
            title=f"Nuevo mensaje de {user.get('name', 'Usuario')}",
            message=message_data.message[:100],
            notification_type="new_message"
        )

    return message


@router.get("/conversations")
async def get_conversations(request: Request):
    """Get user's conversations (only with connected users)"""
    user = await get_current_user(request, db)

    # Get all active connections for this user
    connections = await db.connections.find(
        {
            "status": "active",
            "$or": [
                {"client_user_id": user["user_id"]},
                {"provider_user_id": user["user_id"]}
            ]
        },
        {"_id": 0}
    ).to_list(100)

    connected_user_ids = set()
    for conn in connections:
        other_id = conn["provider_user_id"] if conn["client_user_id"] == user["user_id"] else conn["client_user_id"]
        connected_user_ids.add(other_id)

    if not connected_user_ids:
        return []

    messages = await db.chat_messages.find(
        {"$or": [
            {"sender_id": user["user_id"], "receiver_id": {"$in": list(connected_user_ids)}},
            {"receiver_id": user["user_id"], "sender_id": {"$in": list(connected_user_ids)}}
        ]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(1000)

    conversations = {}
    for msg in messages:
        conv_id = msg["conversation_id"]
        if conv_id not in conversations:
            other_user_id = msg["receiver_id"] if msg["sender_id"] == user["user_id"] else msg["sender_id"]
            other_user = await db.users.find_one(
                {"user_id": other_user_id},
                {"_id": 0, "user_id": 1, "name": 1, "picture": 1}
            )
            conversations[conv_id] = {
                "conversation_id": conv_id,
                "other_user": other_user,
                "last_message": msg,
                "unread_count": 0
            }

        if msg["receiver_id"] == user["user_id"] and not msg["read"]:
            conversations[conv_id]["unread_count"] += 1

    # Also show connections without messages yet (so users can start chatting)
    for conn in connections:
        other_id = conn["provider_user_id"] if conn["client_user_id"] == user["user_id"] else conn["client_user_id"]
        conv_id = f"{min(user['user_id'], other_id)}_{max(user['user_id'], other_id)}"
        if conv_id not in conversations:
            other_user = await db.users.find_one(
                {"user_id": other_id},
                {"_id": 0, "user_id": 1, "name": 1, "picture": 1}
            )
            conversations[conv_id] = {
                "conversation_id": conv_id,
                "other_user": other_user,
                "last_message": None,
                "unread_count": 0,
                "connection_type": conn.get("type", "")
            }

    return list(conversations.values())


@router.get("/messages/{conversation_id}")
async def get_conversation_messages(conversation_id: str, request: Request):
    """Get messages for a conversation"""
    user = await get_current_user(request, db)

    messages = await db.chat_messages.find(
        {"conversation_id": conversation_id},
        {"_id": 0}
    ).sort("created_at", 1).to_list(500)

    await db.chat_messages.update_many(
        {
            "conversation_id": conversation_id,
            "receiver_id": user["user_id"],
            "read": False
        },
        {"$set": {"read": True}}
    )

    return messages
