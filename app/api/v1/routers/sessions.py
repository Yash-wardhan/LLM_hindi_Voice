"""
Session Management Router
──────────────────────────
All endpoints require a valid Bearer JWT (login/signup first).

POST   /api/v1/sessions               — create a session for the logged-in user
GET    /api/v1/sessions               — list this user’s sessions
GET    /api/v1/sessions/{session_id}  — get session details
DELETE /api/v1/sessions/{session_id}  — delete session (DB + memory)
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import CurrentUser
from app.core.uuid7 import uuid7
from app.models.db_models import Session as DBSession
from app.models.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionInfo,
    SessionListResponse,
)
from app.services.memory_service import memory_service

router = APIRouter()


def _db_to_schema(db_sess: DBSession, message_count: int) -> SessionInfo:
    return SessionInfo(
        session_id=db_sess.id,
        user_id=db_sess.user_id,
        name=db_sess.name,
        message_count=message_count,
        last_access=db_sess.last_access.isoformat(),
        created_at=db_sess.created_at.isoformat(),
    )


@router.post(
    "",
    response_model=CreateSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
    description=(
        "Creates a new conversation session linked to the authenticated user. "
        "Pass the returned `session_id` in voice/chat requests."
    ),
)
async def create_session(
    body: CreateSessionRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> CreateSessionResponse:
    session_id = uuid7()
    label = (body.label or current_user.name).strip()

    # Persist to database
    db_sess = DBSession(
        id=session_id,
        user_id=current_user.id,
        name=label,
    )
    db.add(db_sess)
    await db.commit()
    await db.refresh(db_sess)

    # Also register in in-memory service for fast chat history lookups
    memory_service.create_session(session_id, label)

    return CreateSessionResponse(
        session_id=session_id,
        user_id=current_user.id,
        name=label,
    )


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List my sessions",
)
async def list_sessions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    result = await db.execute(
        select(DBSession)
        .where(DBSession.user_id == current_user.id, DBSession.is_active == True)  # noqa: E712
        .order_by(DBSession.last_access.desc())
    )
    db_sessions = result.scalars().all()

    sessions = [
        _db_to_schema(s, memory_service.get_message_count(s.id))
        for s in db_sessions
    ]
    return SessionListResponse(sessions=sessions, total=len(sessions))


@router.get(
    "/{session_id}",
    response_model=SessionInfo,
    summary="Get session details",
)
async def get_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SessionInfo:
    result = await db.execute(
        select(DBSession).where(
            DBSession.id == session_id,
            DBSession.user_id == current_user.id,
            DBSession.is_active == True,  # noqa: E712
        )
    )
    db_sess = result.scalar_one_or_none()
    if not db_sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    return _db_to_schema(db_sess, memory_service.get_message_count(session_id))


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete session",
    description="Removes the session from the database and clears its conversation memory.",
)
async def delete_session(
    session_id: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(DBSession).where(
            DBSession.id == session_id,
            DBSession.user_id == current_user.id,
        )
    )
    db_sess = result.scalar_one_or_none()
    if not db_sess:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found.",
        )
    # Soft-delete in DB
    db_sess.is_active = False
    db_sess.last_access = datetime.now(timezone.utc)
    await db.commit()

    # Clear from in-memory store
    memory_service.clear_session(session_id)
