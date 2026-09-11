from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import CurrentUser
from app.models.user import Role
from app.models.workspace import AutonomyConfig, Workspace, WorkspaceSettings

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    plan: str
    settings: WorkspaceSettings
    autonomy: AutonomyConfig
    kill_switch: bool


class KillSwitchRequest(BaseModel):
    enabled: bool


def _to_response(ws: Workspace) -> WorkspaceResponse:
    return WorkspaceResponse(
        id=str(ws.id),
        name=ws.name,
        plan=ws.plan,
        settings=ws.settings,
        autonomy=ws.autonomy,
        kill_switch=ws.kill_switch,
    )


@router.get("/me", response_model=WorkspaceResponse)
async def get_my_workspace(user: CurrentUser) -> WorkspaceResponse:
    ws = await Workspace.get(user.workspace_id)
    if ws is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return _to_response(ws)


@router.post("/me/kill-switch", response_model=WorkspaceResponse)
async def set_kill_switch(payload: KillSwitchRequest, user: CurrentUser) -> WorkspaceResponse:
    """One tap stops all automated sending workspace-wide (Section 11)."""
    if user.role not in (Role.OWNER, Role.MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    ws = await Workspace.get(user.workspace_id)
    if ws is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    ws.kill_switch = payload.enabled
    await ws.save()
    return _to_response(ws)
