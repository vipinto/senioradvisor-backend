import socketio
from typing import Dict
import logging

logger = logging.getLogger(__name__)

# Socket.IO server instance
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True
)

# Store active connections: {user_id: sid}
active_connections: Dict[str, str] = {}

@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected: {sid}")
    return True

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")
    # Remove from active connections
    for user_id, session_id in list(active_connections.items()):
        if session_id == sid:
            del active_connections[user_id]
            break

@sio.event
async def authenticate(sid, data):
    """Authenticate user and register connection"""
    try:
        user_id = data.get('user_id')
        if user_id:
            active_connections[user_id] = sid
            logger.info(f"User authenticated: {user_id} -> {sid}")
            await sio.emit('authenticated', {'success': True}, room=sid)
        else:
            await sio.emit('error', {'message': 'user_id required'}, room=sid)
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def send_message(sid, data):
    """Handle sending messages"""
    try:
        sender_id = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        message = data.get('message')
        message_id = data.get('message_id')
        conversation_id = data.get('conversation_id')
        
        logger.info(f"Message from {sender_id} to {receiver_id}: {message[:50]}")
        
        # Send to receiver if online
        receiver_sid = active_connections.get(receiver_id)
        if receiver_sid:
            await sio.emit('new_message', {
                'message_id': message_id,
                'conversation_id': conversation_id,
                'sender_id': sender_id,
                'receiver_id': receiver_id,
                'message': message,
                'created_at': data.get('created_at')
            }, room=receiver_sid)
            logger.info(f"Message delivered to {receiver_id}")
        else:
            logger.info(f"Receiver {receiver_id} is offline")
        
        # Confirm to sender
        await sio.emit('message_sent', {
            'message_id': message_id,
            'success': True
        }, room=sid)
        
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def typing(sid, data):
    """Handle typing indicators"""
    try:
        sender_id = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        is_typing = data.get('is_typing', True)
        
        receiver_sid = active_connections.get(receiver_id)
        if receiver_sid:
            await sio.emit('user_typing', {
                'user_id': sender_id,
                'is_typing': is_typing
            }, room=receiver_sid)
    except Exception as e:
        logger.error(f"Error handling typing: {e}")

def get_socket_app():
    """Get the Socket.IO ASGI application"""
    return socketio.ASGIApp(sio)
