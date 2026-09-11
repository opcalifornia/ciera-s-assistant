from fastapi import APIRouter
from pydantic import BaseModel, EmailStr, Field

from app.core.security import CurrentUser
from app.models.user import Role
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    workspace_name: str = Field(min_length=1)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: Role
    workspace_id: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest) -> TokenResponse:
    _, user = await auth_service.register_founder_workspace(
        workspace_name=payload.workspace_name,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    tokens = auth_service.issue_tokens(user)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    user = await auth_service.authenticate(email=payload.email, password=payload.password)
    tokens = auth_service.issue_tokens(user)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    tokens = await auth_service.refresh_access_token(payload.refresh_token)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(user: CurrentUser) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        workspace_id=user.workspace_id,
    )
