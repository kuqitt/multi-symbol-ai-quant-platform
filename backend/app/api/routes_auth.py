from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from app.database import get_session
from app.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas import LoginRequest, LoginResponse, UserCreateRequest, UserRead


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_session)) -> LoginResponse:
    user, token = request.app.state.container.auth_service.authenticate(session, payload.username, payload.password)
    return LoginResponse(access_token=token, username=user.username, role=user.role)


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> UserRead:
    return UserRead(**user.model_dump())


@router.get("/users", response_model=list[UserRead])
def list_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin")),
) -> list[UserRead]:
    users = session.exec(select(User).order_by(User.created_at.desc())).all()
    return [UserRead(**user.model_dump()) for user in users]


@router.post("/users", response_model=UserRead)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    session: Session = Depends(get_session),
    _: User = Depends(require_roles("admin")),
) -> UserRead:
    user = request.app.state.container.auth_service.create_user(
        session,
        username=payload.username,
        password=payload.password,
        role=payload.role,
    )
    return UserRead(**user.model_dump())
