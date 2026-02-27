"""
In-memory conversation memory.
Keyed by session_id.  Replace with Redis for multi-instance deployments.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.core.config import settings
from app.models.schemas import ChatMessage, SessionInfo


class MemoryService:
    def __init__(
        self,
        max_messages: int = settings.MEMORY_MAX_MESSAGES,
        session_ttl_minutes: int = settings.MEMORY_SESSION_TTL_MINUTES,
    ) -> None:
        # session_id → list of {"role": ..., "content": ...}
        self._sessions: Dict[str, List[dict]] = {}
        self._last_access: Dict[str, datetime] = {}
        # session_id → user display name
        self._names: Dict[str, str] = {}
        self.max_messages = max_messages
        self.session_ttl = timedelta(minutes=session_ttl_minutes)

    # ── Public API ────────────────────────────────────────────────────────────

    def create_session(self, session_id: str, name: str) -> None:
        """Explicitly register a named session (called from POST /sessions)."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._names[session_id] = name
        self._last_access[session_id] = datetime.now(timezone.utc)

    def get_name(self, session_id: str) -> Optional[str]:
        """Return the display name stored for this session, or None."""
        return self._names.get(session_id)

    def get_message_count(self, session_id: str) -> int:
        """Return the number of messages in the session (0 if not in memory)."""
        return len(self._sessions.get(session_id, []))

    def get_history(self, session_id: str) -> List[dict]:
        """Return the message history for a session (creates it if absent)."""
        self._cleanup_expired()
        history = self._sessions.get(session_id, [])
        if session_id in self._sessions:
            self._last_access[session_id] = datetime.now(timezone.utc)
        return history

    def add_exchange(
        self,
        session_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        """Append a user→assistant exchange and trim to max_messages."""
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        self._sessions[session_id].extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": assistant_text},
        ])

        # Keep the most recent N pairs
        cap = self.max_messages * 2
        if len(self._sessions[session_id]) > cap:
            self._sessions[session_id] = self._sessions[session_id][-cap:]

        self._last_access[session_id] = datetime.now(timezone.utc)

    def clear_session(self, session_id: str) -> bool:
        """Delete a session and return True if it existed."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._last_access.pop(session_id, None)
            self._names.pop(session_id, None)
            return True
        return False

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        if session_id not in self._sessions:
            return None
        last = self._last_access.get(session_id)
        return SessionInfo(
            session_id=session_id,
            name=self._names.get(session_id),
            message_count=len(self._sessions[session_id]),
            last_access=last.isoformat() if last else None,
        )

    def list_sessions(self) -> List[SessionInfo]:
        self._cleanup_expired()
        return [self.get_session_info(sid) for sid in self._sessions if self.get_session_info(sid)]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, last in self._last_access.items()
            if now - last > self.session_ttl
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._last_access.pop(sid, None)
            self._names.pop(sid, None)


# Singleton — shared across the entire app process
memory_service = MemoryService()
