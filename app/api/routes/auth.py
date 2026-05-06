"""Authentication routes."""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.security import verify_password, hash_password, create_access_token, decode_token

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


def get_current_admin(token: str = Depends(oauth2_scheme)) -> str:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    username = payload.get("sub")
    if username != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=403, detail="Forbidden")
    return username


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username != settings.ADMIN_USERNAME:
        raise HTTPException(status_code=401, detail="Incorrect credentials")
    if not verify_password(form_data.password, hash_password(settings.ADMIN_PASSWORD)):
        # Compare directly since we hash dynamically for simplicity
        if form_data.password != settings.ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Incorrect credentials")

    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_me(current_user: str = Depends(get_current_admin)):
    return {"username": current_user, "role": "admin"}
