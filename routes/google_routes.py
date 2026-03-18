from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode
import os
import logging

from database import db
from auth import google_auth_login

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://senioradvisor.cl")

router = APIRouter(prefix="/auth")


@router.get("/google")
async def google_callback(request: Request):

    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?google_error={error}"
        )

    if not code:
        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?google_error=missing_code"
        )

    try:

        result = await google_auth_login(
            code=code,
            redirect_uri=f"{os.environ.get('REACT_APP_BACKEND_URL', 'https://senioradvisor.cl')}/auth/google",
            db=db
        )

        token = result["token"]

        params = urlencode({
            "token": token
        })

        return RedirectResponse(
            url=f"{FRONTEND_URL}/auth/google-success?{params}"
        )

    except Exception as e:

        logger.exception(f"Google callback error: {str(e)}")

        return RedirectResponse(
            url=f"{FRONTEND_URL}/login?google_error=auth_failed"
        )
