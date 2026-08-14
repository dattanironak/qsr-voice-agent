from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import ConversationSession, ConversationTurn
from app.schemas import (
    ConversationSessionCreate,
    ConversationSessionOut,
    ConversationTurnCreate,
    ConversationTurnOut,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_or_create_session(db: Session, room_name: str) -> ConversationSession:
    """Look up a conversation session by room name, creating it if this is the first turn
    the agent has reported for it. Turns can arrive before an explicit start() call reaches
    the backend (e.g. a retried request), so this stays defensive rather than 404ing."""
    session = db.execute(
        select(ConversationSession).where(ConversationSession.room_name == room_name)
    ).scalar_one_or_none()
    if session is None:
        session = ConversationSession(room_name=room_name)
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


@router.post("", response_model=ConversationSessionOut, status_code=201)
def start_conversation(body: ConversationSessionCreate, db: Session = Depends(get_db)):
    session = _get_or_create_session(db, body.room_name)
    return session


@router.post("/{room_name}/turns", response_model=ConversationTurnOut, status_code=201)
def add_turn(room_name: str, body: ConversationTurnCreate, db: Session = Depends(get_db)):
    session = _get_or_create_session(db, room_name)
    turn = ConversationTurn(session_id=session.id, role=body.role, content=body.content)
    db.add(turn)
    db.commit()
    db.refresh(turn)
    return turn


@router.post("/{room_name}/end", response_model=ConversationSessionOut)
def end_conversation(room_name: str, db: Session = Depends(get_db)):
    session = _get_or_create_session(db, room_name)
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{room_name}", response_model=ConversationSessionOut)
def get_conversation(room_name: str, db: Session = Depends(get_db)):
    stmt = (
        select(ConversationSession)
        .options(selectinload(ConversationSession.turns))
        .where(ConversationSession.room_name == room_name)
    )
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        raise HTTPException(404, "Conversation not found")
    return session


@router.get("", response_model=list[ConversationSessionOut])
def list_conversations(db: Session = Depends(get_db)):
    stmt = (
        select(ConversationSession)
        .options(selectinload(ConversationSession.turns))
        .order_by(ConversationSession.started_at.desc())
        .limit(100)
    )
    return db.execute(stmt).scalars().all()
