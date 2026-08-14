from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_admin, verify_password
from app.config import Settings, get_settings
from app.database import get_db
from app.models import AdminUser
from app.schemas import AdminLoginIn, AdminLoginOut, AdminUserOut

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/login", response_model=AdminLoginOut)
def login(body: AdminLoginIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user = db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    ).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid username or password")

    token, expires_at = create_access_token(user, settings)
    return AdminLoginOut(token=token, expires_at=expires_at, username=user.username, role=user.role)


@router.get("/me", response_model=AdminUserOut)
def me(current: AdminUser = Depends(get_current_admin)):
    return current
