import httpx
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from jose import jwt
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/login")
def login_github():
    """Initiate GitHub OAuth login"""
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=repo"
    )
    logger.info("Redirecting to GitHub OAuth")
    return RedirectResponse(github_auth_url, status_code=302)

@router.get("/callback")
async def github_callback(code: str, request: Request):
    """Handle GitHub OAuth callback"""
    try:
        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            logger.info("Exchanging code for GitHub access token")
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                json={
                    "client_id": settings.GITHUB_CLIENT_ID,
                    "client_secret": settings.GITHUB_CLIENT_SECRET,
                    "code": code,
                },
                headers={"Accept": "application/json"},
                timeout=10.0
            )
            
            if token_resp.status_code != 200:
                logger.error(f"GitHub token exchange failed: {token_resp.status_code}")
                return RedirectResponse("/?error=auth_failed")
            
            token_data = token_resp.json()
            access_token = token_data.get("access_token")

            if not access_token:
                logger.error("No access token in GitHub response")
                return RedirectResponse("/?error=auth_failed")

            # Create JWT for client storage
            jwt_payload = {
                "sub": "github_user",
                "access_token": access_token,
                "exp": datetime.utcnow() + timedelta(days=7)
            }
            jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm="HS256")
            
            logger.info("GitHub authentication successful")
            
            # Redirect to frontend with token
            base_url = str(request.base_url).rstrip('/')
            return RedirectResponse(f"{base_url}?token={jwt_token}")
            
    except httpx.TimeoutException:
        logger.error("GitHub authentication timeout")
        return RedirectResponse("/?error=timeout")
    except Exception as e:
        logger.error(f"GitHub authentication error: {e}", exc_info=True)
        return RedirectResponse("/?error=server_error")
