"""Chat HTTP routes."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.service import get_current_user
from ..database import get_db
from ..models import User
from .service import ask, history


router = APIRouter(prefix="/api/chat", tags=["chat"])


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


@router.post("/ask", response_model=MessageOut)
def ask_route(
    payload: AskIn,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> MessageOut:
    result = ask(db, user, payload.question)
    return MessageOut(
        id=result["id"], role="assistant",
        content=result["content"], created_at=result["created_at"],
    )


@router.get("/history", response_model=list[MessageOut])
def history_route(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
) -> list[MessageOut]:
    msgs = history(db, user, limit=limit)
    return [MessageOut(id=m.id, role=m.role, content=m.content,
                       created_at=m.created_at.isoformat()) for m in msgs]


@router.delete("/history", status_code=200)
def clear_history(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from sqlalchemy import delete
    from ..models import ChatMessage
    db.execute(delete(ChatMessage).where(ChatMessage.user_id == user.id))
    db.commit()
    return {"ok": True}
