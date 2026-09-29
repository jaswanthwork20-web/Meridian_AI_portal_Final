"""
Authentication Router
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, User
from app.auth import verify_password, create_access_token, get_current_user, require_employee
from app.schemas import LoginRequest, TokenResponse, UserProfileOut

router = APIRouter(tags=["Authentication"])

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    email_query = req.email.strip().lower()
    if email_query in ("maya", "maya.sharma", "maya_sharma", "maya@meridian.com"):
        email_query = "maya.sharma@meridian.com"
    elif email_query in ("alex", "alex.turner", "alex@meridian.com", "alex.turner@smartfix.com"):
        email_query = "alex@meridian.com"
    elif email_query in ("customer", "cust"):
        email_query = "customer@meridian.com"

    user = db.query(User).filter(User.email.ilike(email_query)).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return TokenResponse(
        access_token=create_access_token(user.id, user.email),
        role=user.role or "customer"
    )

@router.get("/me", response_model=UserProfileOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user
