"""Naive lexical retrieval over Brand Brain documents (Section 4.1).

Free by default (`StubEmbeddingProvider`); becomes real semantic
retrieval the moment `VOYAGE_API_KEY` is set — the interface doesn't
change, only the quality of the ranking.
"""

from app.models.brand_document import BrandDocument
from app.providers.embeddings import EmbeddingProvider, cosine_similarity


async def ingest_document(
    *,
    workspace_id: str,
    brand_id: str,
    doc_type: str,
    title: str,
    text: str,
    embedder: EmbeddingProvider,
) -> BrandDocument:
    embedding = await embedder.embed(text)
    doc = BrandDocument(
        workspace_id=workspace_id,
        brand_id=brand_id,
        doc_type=doc_type,  # type: ignore[arg-type]
        title=title,
        text=text,
        embedding=embedding,
    )
    await doc.insert()
    return doc


async def most_similar(
    *, workspace_id: str, brand_id: str, query: str, embedder: EmbeddingProvider, limit: int = 3
) -> list[BrandDocument]:
    """Returns up to `limit` documents ranked by similarity to `query`.
    Used by the Brand Voice agent to pull past-email examples so drafts
    sound like the talent (Section 4.3.4)."""
    query_vector = await embedder.embed(query)
    candidates = await BrandDocument.find(
        BrandDocument.workspace_id == workspace_id, BrandDocument.brand_id == brand_id
    ).to_list()
    scored = [(cosine_similarity(query_vector, doc.embedding), doc) for doc in candidates]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [doc for _, doc in scored[:limit]]
