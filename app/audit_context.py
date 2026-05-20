from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.orm import Session


AUDIT_ACTOR_USER_ID_KEY = "audit_actor_user_id"


@contextmanager
def bind_audit_actor(session: Session, actor_user_id: int | None) -> Iterator[None]:
    """Временно связывает текущий SQLAlchemy Session с actor_user_id для audit-логов."""
    marker = object()
    previous_value = session.info.get(AUDIT_ACTOR_USER_ID_KEY, marker)

    if actor_user_id is None:
        session.info.pop(AUDIT_ACTOR_USER_ID_KEY, None)
    else:
        session.info[AUDIT_ACTOR_USER_ID_KEY] = actor_user_id

    try:
        yield
    finally:
        if previous_value is marker:
            session.info.pop(AUDIT_ACTOR_USER_ID_KEY, None)
        else:
            session.info[AUDIT_ACTOR_USER_ID_KEY] = previous_value


def get_audit_actor_user_id(session: Session | None) -> int | None:
    """Возвращает actor_user_id, сохраненный в Session.info."""
    if session is None:
        return None

    raw_value = session.info.get(AUDIT_ACTOR_USER_ID_KEY)
    if raw_value is None:
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None
