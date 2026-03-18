from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path

from database import db, client, UPLOADS_DIR
from socket_handler import get_socket_app
from routes.auth_routes import router as auth_router
from routes.google_routes import router as google_router
from routes.provider_routes import router as provider_router
from routes.subscription_routes import router as subscription_router
from routes.social_routes import router as social_router
from routes.chat_routes import router as chat_router
from routes.admin_routes import router as admin_router
from routes.notification_routes import router as notification_router
from routes.misc_routes import router as misc_router
from routes.booking_routes import router as booking_router
from routes.care_request_routes import router as care_request_router
from routes.contact_request_routes import router as contact_request_router
from routes.blog_routes import router as blog_router
from routes.partner_routes import router as partner_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create the main app
app = FastAPI(title="SeniorAdvisor API", version="1.0.0", redirect_slashes=False)
@app.get("/")
async def app_root():
    return {"message": "SeniorAdvisor backend running"}

# Serve uploaded files under /api/uploads prefix
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Mount Socket.IO app
socket_app = get_socket_app()
app.mount("/socket.io", socket_app)

app.include_router(google_router)

# Main API router
api_router = APIRouter(prefix="/api")

# Include all sub-routers
api_router.include_router(auth_router)
api_router.include_router(provider_router)
api_router.include_router(subscription_router)
api_router.include_router(social_router)
api_router.include_router(chat_router)
api_router.include_router(admin_router)
api_router.include_router(notification_router)
api_router.include_router(misc_router)
api_router.include_router(booking_router)
api_router.include_router(care_request_router)
api_router.include_router(contact_request_router)
api_router.include_router(blog_router)
api_router.include_router(partner_router)


@api_router.get("/")
async def root():
    return {"message": "SeniorAdvisor API", "version": "1.0.0"}


@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "SeniorAdvisor"}


# Health check endpoints for K8s probes
@api_router.post("/gql")
@api_router.get("/gql")
async def gql_health():
    return {"status": "healthy"}


@api_router.post("/graphql")
@api_router.get("/graphql")
async def graphql_health():
    return {"status": "healthy"}


@api_router.post("/")
async def root_post():
    return {"message": "SeniorAdvisor API", "version": "1.0.0"}


# Include the router in the main app
app.include_router(api_router)


# Direct health check for /api without trailing slash (K8s probes)
@app.post("/api")
@app.get("/api")
async def api_root_no_slash():
    return {"message": "SeniorAdvisor API", "version": "1.0.0"}

# CORS Middleware
cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "https://senioradvisor.cl,https://www.senioradvisor.cl,http://localhost:3000"
)

cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
