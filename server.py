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
from routes.cloudinary_routes import router as cloudinary_router

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
api_router.include_router(cloudinary_router)


@api_router.get("/")
async def root():
    return {"message": "SeniorAdvisor API", "version": "1.0.0"}


@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "SeniorAdvisor"}


@api_router.get("/diagnostics")
async def diagnostics():
    """Diagnostic endpoint to check backend dependencies and config"""
    results = {}
    
    # Check bcrypt
    try:
        import bcrypt as bcrypt_check
        test_hash = bcrypt_check.hashpw(b"test123", bcrypt_check.gensalt()).decode('utf-8')
        verified = bcrypt_check.checkpw(b"test123", test_hash.encode('utf-8'))
        results["bcrypt"] = {"status": "ok", "verify_works": verified, "version": getattr(bcrypt_check, '__version__', 'unknown')}
    except Exception as e:
        results["bcrypt"] = {"status": "error", "error": str(e)}
    
    # Check JWT
    try:
        import jwt
        token = jwt.encode({"test": True}, "secret", algorithm="HS256")
        results["pyjwt"] = {"status": "ok"}
    except Exception as e:
        results["pyjwt"] = {"status": "error", "error": str(e)}
    
    # Check DB connection
    try:
        user_count = await db.users.count_documents({})
        results["database"] = {"status": "ok", "users_count": user_count}
    except Exception as e:
        results["database"] = {"status": "error", "error": str(e)}
    
    # Check env vars
    results["env"] = {
        "JWT_SECRET": "set" if os.environ.get("JWT_SECRET") else "MISSING",
        "MONGO_URL": "set" if os.environ.get("MONGO_URL") else "MISSING",
        "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", "not set"),
    }
    
    return results


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
