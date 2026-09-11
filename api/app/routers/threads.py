from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import CurrentUser
from app.models.brand import Brand
from app.models.thread import Channel, Message, Thread, TriageSnapshot
from app.services.pipeline_service import ingest_inbound_message

router = APIRouter(tags=["threads"])


class ThreadResponse(BaseModel):
    id: str
    brand_id: str
    channel: Channel
    subject: str
    participants: list[str]
    last_message_at: str
    triage: TriageSnapshot | None
    needs_a_look: bool
    archived: bool


class MessageResponse(BaseModel):
    id: str
    direction: str
    channel: Channel
    sender: str
    recipients: list[str]
    subject: str
    body_text: str
    sent_or_received_at: str
    injection_flag: bool


class ThreadDetailResponse(ThreadResponse):
    messages: list[MessageResponse]


class IngestMessageRequest(BaseModel):
    brand_id: str
    channel: Channel
    sender: str
    subject: str = ""
    body: str


def _thread_response(t: Thread) -> ThreadResponse:
    return ThreadResponse(
        id=str(t.id),
        brand_id=t.brand_id,
        channel=t.channel,
        subject=t.subject,
        participants=t.participants,
        last_message_at=t.last_message_at.isoformat(),
        triage=t.triage,
        needs_a_look=t.needs_a_look,
        archived=t.archived,
    )


def _message_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=str(m.id),
        direction=m.direction.value,
        channel=m.channel,
        sender=m.sender,
        recipients=m.recipients,
        subject=m.subject,
        body_text=m.body_text,
        sent_or_received_at=m.sent_or_received_at.isoformat(),
        injection_flag=m.injection_flag,
    )


@router.post("/threads/ingest", response_model=ThreadResponse, status_code=status.HTTP_201_CREATED)
async def ingest_message(payload: IngestMessageRequest, user: CurrentUser) -> ThreadResponse:
    """Dev/stub inbound endpoint: simulates a message arriving over any
    channel and runs it through the full Triage -> Brand Voice pipeline.
    Stands in for the real Gmail push / Twilio webhook, which need live
    credentials this workspace doesn't have configured yet (PLAN.md open
    questions 1, 7)."""
    brand = await Brand.get(payload.brand_id)
    if brand is None or brand.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")

    thread, _message, _option_set = await ingest_inbound_message(
        workspace_id=user.workspace_id,
        brand=brand,
        channel=payload.channel,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
    )
    return _thread_response(thread)


@router.get("/threads", response_model=list[ThreadResponse])
async def list_threads(
    user: CurrentUser, channel: Channel | None = None, needs_a_look: bool | None = None
) -> list[ThreadResponse]:
    query = [Thread.workspace_id == user.workspace_id]
    if channel is not None:
        query.append(Thread.channel == channel)
    if needs_a_look is not None:
        query.append(Thread.needs_a_look == needs_a_look)
    threads = await Thread.find(*query).sort("-last_message_at").to_list()
    return [_thread_response(t) for t in threads]


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(thread_id: str, user: CurrentUser) -> ThreadDetailResponse:
    thread = await Thread.get(thread_id)
    if thread is None or thread.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    messages = (
        await Message.find(Message.thread_id == str(thread.id))
        .sort("+sent_or_received_at")
        .to_list()
    )
    base = _thread_response(thread)
    return ThreadDetailResponse(
        **base.model_dump(), messages=[_message_response(m) for m in messages]
    )
