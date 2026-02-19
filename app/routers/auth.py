from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timezone

from app.core.deps import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.schemas.auth import LoginIn, TokenOut
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Invalid credentials")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.email)
    return TokenOut(access_token=token)

@router.post("/register", response_model=TokenOut)
def register(payload: LoginIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.email == payload.email))
    if exists:
        raise HTTPException(status_code=400, detail="Email in use")
    user = User(email=payload.email, password_hash=hash_password(payload.password), is_active=True)
    db.add(user); db.commit()
    token = create_access_token(user.email)
    return TokenOut(access_token=token)
