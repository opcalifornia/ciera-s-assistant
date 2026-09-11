"""Registration/login business logic, kept out of the router for testability."""

from fastapi import HTTPException, status

from app.core.security import TokenType as _TokenType
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import Role, User
from app.models.workspace import Workspace


class TokenPair:
    def __init__(self, access_token: str, refresh_token: str) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = "bearer"


async def register_founder_workspace(
    *, workspace_name: str, email: str, password: str, full_name: str = ""
) -> tuple[Workspace, User]:
    """First user in a new workspace is always the owner (Section 1: founder is customer zero)."""
    existing = await User.find_one(User.email == email)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    workspace = Workspace(name=workspace_name)
    await workspace.insert()

    user = User(
        workspace_id=str(workspace.id),
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=Role.OWNER,
    )
    await user.insert()
    return workspace, user


async def authenticate(*, email: str, password: str) -> User:
    user = await User.find_one(User.email == email)
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    return user


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user),
    )


async def refresh_access_token(refresh_token: str) -> TokenPair:
    payload = decode_token(refresh_token)
    if payload.type != _TokenType.REFRESH:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Wrong token type")
    user = await User.get(payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return issue_tokens(user)
