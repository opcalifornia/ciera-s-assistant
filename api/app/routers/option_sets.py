from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import CurrentUser
from app.models.option_set import OptionSet
from app.models.thread import Thread
from app.models.user import Role
from app.services.approval_service import ApprovalError, ChoiceInput, adjust_draft, choose_and_send

router = APIRouter(tags=["option-sets"])


class OptionSetResponse(BaseModel):
    id: str
    thread_id: str
    playbook_id: str | None
    options: list[dict]
    quick_replies: list[dict]
    status: str
    chosen_option_index: int | None


def _to_response(os: OptionSet) -> OptionSetResponse:
    return OptionSetResponse(
        id=str(os.id),
        thread_id=os.thread_id,
        playbook_id=os.playbook_id,
        options=[o.model_dump() for o in os.options],
        quick_replies=[q.model_dump() for q in os.quick_replies],
        status=os.status.value,
        chosen_option_index=os.chosen_option_index,
    )


@router.get("/threads/{thread_id}/option-sets", response_model=list[OptionSetResponse])
async def list_option_sets_for_thread(thread_id: str, user: CurrentUser) -> list[OptionSetResponse]:
    thread = await Thread.get(thread_id)
    if thread is None or thread.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    option_sets = (
        await OptionSet.find(OptionSet.thread_id == thread_id).sort("-created_at").to_list()
    )
    return [_to_response(os) for os in option_sets]


class ChooseRequest(BaseModel):
    kind: str  # "option" | "quick_reply" | "custom"
    index: int | None = None
    custom_text: str | None = None
    adjusted_text: str | None = None
    send: bool = True


class ChooseResponse(BaseModel):
    option_set: OptionSetResponse
    sent_message_id: str | None


@router.post("/option-sets/{option_set_id}/choose", response_model=ChooseResponse)
async def choose_option(
    option_set_id: str, payload: ChooseRequest, user: CurrentUser
) -> ChooseResponse:
    if user.role == Role.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot send replies"
        )

    try:
        option_set, message = await choose_and_send(
            option_set_id=option_set_id,
            user_id=str(user.id),
            workspace_id=user.workspace_id,
            choice=ChoiceInput(
                kind=payload.kind,
                index=payload.index,
                custom_text=payload.custom_text,
                adjusted_text=payload.adjusted_text,
            ),
            send=payload.send,
        )
    except ApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return ChooseResponse(
        option_set=_to_response(option_set), sent_message_id=str(message.id) if message else None
    )


class AdjustRequest(BaseModel):
    index: int
    instruction: str


class AdjustResponse(BaseModel):
    draft: str


@router.post("/option-sets/{option_set_id}/adjust", response_model=AdjustResponse)
async def adjust_option(
    option_set_id: str, payload: AdjustRequest, user: CurrentUser
) -> AdjustResponse:
    option_set = await OptionSet.get(option_set_id)
    if option_set is None or option_set.workspace_id != user.workspace_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Option set not found")
    if not (0 <= payload.index < len(option_set.options)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid option index")

    original = option_set.options[payload.index].draft
    new_draft = await adjust_draft(
        original_draft=original, instruction=payload.instruction, workspace_id=user.workspace_id
    )
    return AdjustResponse(draft=new_draft)
