"""Auth router — register, login, refresh, logout, forgot/reset password."""
from __future__ import annotations

from fastapi import APIRouter, Request

from dependencies import CurrentUser, DbSession
from schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from schemas.common import MessageResponse
from schemas.user import UserOut
from services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(data: RegisterRequest, db: DbSession):
    svc = AuthService(db)
    await svc.register(data)
    return MessageResponse(message="Registration successful. Your account is pending review.")


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: DbSession):
    svc = AuthService(db)
    return await svc.login(data)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(data: RefreshRequest, db: DbSession):
    svc = AuthService(db)
    return await svc.refresh(data.refresh_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: CurrentUser):
    # Stateless JWT — client discards tokens; server-side revocation is a future enhancement
    return MessageResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(data: ForgotPasswordRequest, db: DbSession, request: Request):
    svc = AuthService(db)
    token = await svc.forgot_password(data.email)
    # Always return success to prevent email enumeration
    return MessageResponse(message="If the email exists, a password reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(data: ResetPasswordRequest, db: DbSession):
    svc = AuthService(db)
    await svc.reset_password(data.token, data.new_password)
    return MessageResponse(message="Password reset successfully")


@router.get("/me", response_model=UserOut)
async def get_me(current_user: CurrentUser):
    return current_user
