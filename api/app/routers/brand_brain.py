"""Brand Brain sub-resources: offerings catalog + long-form documents
(Section 4.1). Kept in one router since both hang off `/brands/{brand_id}`
and neither is big enough yet to warrant its own file.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.security import CurrentUser
from app.models.brand import Brand
from app.models.brand_document import BrandDocument, BrandDocumentType
from app.models.offering import Offering
from app.models.user import Role
from app.providers.embeddings import get_embedding_provider
from app.services.retrieval_service import ingest_document, most_similar

router = APIRouter(prefix="/brands/{brand_id}", tags=["brand-brain"])


async def _get_brand(brand_id: str, workspace_id: str) -> Brand:
    brand = await Brand.get(brand_id)
    if brand is None or brand.workspace_id != workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return brand


# --- Offerings ---------------------------------------------------------


class OfferingRequest(BaseModel):
    opportunity_type: str
    name: str = Field(min_length=1)
    description: str = ""
    inclusions: list[str] = Field(default_factory=list)
    anchor: float | None = None
    target: float | None = None
    floor: float | None = None
    currency: str = "USD"


class OfferingResponse(OfferingRequest):
    id: str
    is_active: bool


def _offering_response(o: Offering) -> OfferingResponse:
    return OfferingResponse(
        id=str(o.id),
        opportunity_type=o.opportunity_type,
        name=o.name,
        description=o.description,
        inclusions=o.inclusions,
        anchor=o.anchor,
        target=o.target,
        floor=o.floor,
        currency=o.currency,
        is_active=o.is_active,
    )


@router.get("/offerings", response_model=list[OfferingResponse])
async def list_offerings(brand_id: str, user: CurrentUser) -> list[OfferingResponse]:
    await _get_brand(brand_id, user.workspace_id)
    offerings = await Offering.find(
        Offering.workspace_id == user.workspace_id, Offering.brand_id == brand_id
    ).to_list()
    return [_offering_response(o) for o in offerings]


@router.post("/offerings", response_model=OfferingResponse, status_code=status.HTTP_201_CREATED)
async def create_offering(
    brand_id: str, payload: OfferingRequest, user: CurrentUser
) -> OfferingResponse:
    if user.role not in (Role.OWNER, Role.MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    await _get_brand(brand_id, user.workspace_id)
    offering = Offering(workspace_id=user.workspace_id, brand_id=brand_id, **payload.model_dump())
    await offering.insert()
    return _offering_response(offering)


# --- Documents (voice samples, bios, book excerpts, etc.) --------------


class DocumentIngestRequest(BaseModel):
    doc_type: BrandDocumentType
    title: str = ""
    text: str = Field(min_length=1)


class DocumentResponse(BaseModel):
    id: str
    doc_type: BrandDocumentType
    title: str
    text: str


def _document_response(d: BrandDocument) -> DocumentResponse:
    return DocumentResponse(id=str(d.id), doc_type=d.doc_type, title=d.title, text=d.text)


@router.get("/documents", response_model=list[DocumentResponse])
async def list_documents(brand_id: str, user: CurrentUser) -> list[DocumentResponse]:
    await _get_brand(brand_id, user.workspace_id)
    docs = await BrandDocument.find(
        BrandDocument.workspace_id == user.workspace_id, BrandDocument.brand_id == brand_id
    ).to_list()
    return [_document_response(d) for d in docs]


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    brand_id: str, payload: DocumentIngestRequest, user: CurrentUser
) -> DocumentResponse:
    if user.role not in (Role.OWNER, Role.MANAGER):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")
    await _get_brand(brand_id, user.workspace_id)
    doc = await ingest_document(
        workspace_id=user.workspace_id,
        brand_id=brand_id,
        doc_type=payload.doc_type.value,
        title=payload.title,
        text=payload.text,
        embedder=get_embedding_provider(),
    )
    return _document_response(doc)


class SimilarDocumentsResponse(BaseModel):
    documents: list[DocumentResponse]


@router.get("/documents/similar", response_model=SimilarDocumentsResponse)
async def similar_documents(
    brand_id: str, query: str, user: CurrentUser
) -> SimilarDocumentsResponse:
    await _get_brand(brand_id, user.workspace_id)
    docs = await most_similar(
        workspace_id=user.workspace_id,
        brand_id=brand_id,
        query=query,
        embedder=get_embedding_provider(),
    )
    return SimilarDocumentsResponse(documents=[_document_response(d) for d in docs])
