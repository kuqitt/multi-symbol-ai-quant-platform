from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.auth import create_access_token, hash_password, verify_password
from app.config import EnvironmentSettings
from app.models import User


class AuthService:
    def __init__(self, env_settings: EnvironmentSettings, logger: object) -> None:
        self.env_settings = env_settings
        self.logger = logger

    def seed_admin(self, session: Session) -> None:
        existing = session.exec(select(User).where(User.username == self.env_settings.admin_username)).first()
        if existing:
            return
        admin = User(
            username=self.env_settings.admin_username,
            hashed_password=hash_password(self.env_settings.admin_password),
            role="admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()
        self.logger.info("已初始化默认管理员账号", extra={"category": "auth"})

    def authenticate(self, session: Session, username: str, password: str) -> tuple[User, str]:
        user = session.exec(select(User).where(User.username == username)).first()
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
        token = create_access_token(subject=user.username, role=user.role, env_settings=self.env_settings)
        return user, token

    def get_user_by_username(self, session: Session, username: str) -> User | None:
        return session.exec(select(User).where(User.username == username)).first()

    def create_user(self, session: Session, username: str, password: str, role: str) -> User:
        if self.get_user_by_username(session, username):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
        user = User(
            username=username,
            hashed_password=hash_password(password),
            role=role,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
