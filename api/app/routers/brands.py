from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import CurrentUser
from app.models.brand import AvailabilityRules, Bios, Brand, BusinessTerms
from app.models.user import Role

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandCreateRequest(BaseModel):
    persona_name: str = Field(min_length=1)
    assistant_name: str = "Assistant"
    signature: str = ""
    bios: Bios = Field(default_factory=Bios)
    media_kit_url: str = ""
    values: list[str] = Field(default_factory=list)
    no_go_categories: list[str] = Field(default_factory=list)
    availability: AvailabilityRules = Field(default_factory=AvailabilityRules)
    business_terms: BusinessTerms = Field(default_factory=BusinessTerms)


class BrandResponse(BrandCreateRequest):
    id: str
    is_active: bool


def _to_response(brand: Brand) -> BrandResponse:
    return BrandResponse(
        id=str(brand.id),
        persona_name=brand.persona_name,
        assistant_name=brand.assistant_name,
        signature=brand.signature,
        bios=brand.bios,
        media_kit_url=brand.media_kit_url,
        values=brand.values,
        no_go_categories=brand.no_go_categories,
        availability=brand.availability,
        business_terms=brand.business_terms,
        is_active=brand.is_active,
    )


@router.get("", response_model=list[BrandResponse])
async def list_brands(user: CurrentUser) -> list[BrandResponse]:
    brands = await Brand.find(Brand.workspace_id == user.workspace_id).to_list()
    return [_to_response(b) for b in brands]


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(payload: BrandCreateRequest, user: CurrentUser) -> BrandResponse:
    if user.role not in (Role.OWNER, Role.MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    brand = Brand(workspace_id=user.workspace_id, **payload.model_dump())
    await brand.insert()
    return _to_response(brand)


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: str, user: CurrentUser) -> BrandResponse:
    brand = await Brand.get(brand_id)
    if brand is None or brand.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return _to_response(brand)
