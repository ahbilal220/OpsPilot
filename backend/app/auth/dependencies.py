from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Role, User
from app.auth.security import COOKIE, session_key
from app.db.session import get_session

Session = Annotated[AsyncSession, Depends(get_session)]


async def current_user(request: Request, session: Session) -> User:
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        raise HTTPException(401, "Authentication required")
    user_id = await request.app.state.redis.get(session_key(token))
    if not user_id:
        raise HTTPException(401, "Authentication required")
    try:
        user = await session.get(User, UUID(user_id))
    except ValueError:
        user = None
    if user is None:
        raise HTTPException(401, "Authentication required")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role) -> Callable[[User], Awaitable[User]]:
    async def authorize(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return user

    return authorize


async def trusted_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.trusted_origins:
        raise HTTPException(403, "Trusted Origin header required")
