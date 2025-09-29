import httpx
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from jose import jwt
from datetime import datetime, timedelta

from app.core.config import settings

router = APIRouter()

@router.get("/login")
def login_github():
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope=repo",
        status_code=302
    )

@router.get("/callback")
async def github_callback(code: str, request: Request):
    async with httpx.AsyncClient() as client:
        # Tukarkan kode dengan access token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            return RedirectResponse("/?error=auth_failed")

        # Buat JWT untuk disimpan di client
        jwt_payload = {
            "sub": "github_user",
            "access_token": access_token,
            "exp": datetime.utcnow() + timedelta(days=7)
        }
        jwt_token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm="HS256")
        
        # Redirect kembali ke frontend dengan token
        base_url = str(request.base_url)
        return RedirectResponse(f"{base_url}?token={jwt_token}")
