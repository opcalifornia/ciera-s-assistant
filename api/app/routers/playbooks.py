from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import CurrentUser
from app.models.brand import Brand
from app.models.playbook import CompiledCriteria, FixedOption, ScenarioPlaybook
from app.models.user import Role
from app.services.default_playbooks import install_default_playbooks

router = APIRouter(prefix="/brands/{brand_id}/playbooks", tags=["playbooks"])


class PlaybookCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    natural_language_trigger: str
    compiled_criteria: CompiledCriteria = Field(default_factory=CompiledCriteria)
    fixed_options: list[FixedOption] = Field(default_factory=list)
    allow_ai_extra_options: bool = True
    notification_priority: str = "normal"


class PlaybookUpdateRequest(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    compiled_criteria: CompiledCriteria | None = None
    fixed_options: list[FixedOption] | None = None
    allow_ai_extra_options: bool | None = None


class PlaybookResponse(BaseModel):
    id: str
    name: str
    natural_language_trigger: str
    compiled_criteria: CompiledCriteria
    fixed_options: list[FixedOption]
    allow_ai_extra_options: bool
    notification_priority: str
    enabled: bool
    is_default: bool


def _to_response(pb: ScenarioPlaybook) -> PlaybookResponse:
    return PlaybookResponse(
        id=str(pb.id),
        name=pb.name,
        natural_language_trigger=pb.natural_language_trigger,
        compiled_criteria=pb.compiled_criteria,
        fixed_options=pb.fixed_options,
        allow_ai_extra_options=pb.allow_ai_extra_options,
        notification_priority=pb.notification_priority,
        enabled=pb.enabled,
        is_default=pb.is_default,
    )


async def _get_brand(brand_id: str, workspace_id: str) -> Brand:
    brand = await Brand.get(brand_id)
    if brand is None or brand.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return brand


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(brand_id: str, user: CurrentUser) -> list[PlaybookResponse]:
    await _get_brand(brand_id, user.workspace_id)
    playbooks = await ScenarioPlaybook.find(
        ScenarioPlaybook.workspace_id == user.workspace_id, ScenarioPlaybook.brand_id == brand_id
    ).to_list()
    return [_to_response(pb) for pb in playbooks]


@router.post("", response_model=PlaybookResponse, status_code=status.HTTP_201_CREATED)
async def create_playbook(
    brand_id: str, payload: PlaybookCreateRequest, user: CurrentUser
) -> PlaybookResponse:
    if user.role == Role.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    await _get_brand(brand_id, user.workspace_id)
    playbook = ScenarioPlaybook(
        workspace_id=user.workspace_id, brand_id=brand_id, **payload.model_dump()
    )
    await playbook.insert()
    return _to_response(playbook)


@router.post("/install-defaults", response_model=list[PlaybookResponse])
async def install_defaults(brand_id: str, user: CurrentUser) -> list[PlaybookResponse]:
    if user.role == Role.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    await _get_brand(brand_id, user.workspace_id)
    created = await install_default_playbooks(workspace_id=user.workspace_id, brand_id=brand_id)
    return [_to_response(pb) for pb in created]


@router.patch("/{playbook_id}", response_model=PlaybookResponse)
async def update_playbook(
    brand_id: str, playbook_id: str, payload: PlaybookUpdateRequest, user: CurrentUser
) -> PlaybookResponse:
    if user.role == Role.VIEWER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    await _get_brand(brand_id, user.workspace_id)
    playbook = await ScenarioPlaybook.get(playbook_id)
    if (
        playbook is None
        or playbook.workspace_id != user.workspace_id
        or playbook.brand_id != brand_id
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(playbook, field, value)
    await playbook.save()
    return _to_response(playbook)
