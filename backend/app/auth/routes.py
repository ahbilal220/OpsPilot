import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.auth.dependencies import CurrentUser, Session, trusted_origin
from app.auth.models import Role, User
from app.auth.schemas import Login, Message, Register, UserPublic
from app.auth.security import COOKIE, DUMMY_HASH, password_hasher, session_key

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("opspilot.auth")


async def limit_auth(request: Request) -> None:
    # Atomic fixed window, shared across API workers. Fail closed if Redis is unavailable.
    peer = request.client.host if request.client else "unknown"
    key = "auth-limit:" + hashlib.sha256(peer.encode()).hexdigest()
    count = await request.app.state.redis.eval(
        "local n=redis.call('INCR',KEYS[1]); "
        "if n==1 then redis.call('EXPIRE',KEYS[1],60) end; return n",
        1,
        key,
    )
    if count > 20:
        raise HTTPException(429, "Too many authentication attempts")


mutations = [Depends(trusted_origin), Depends(limit_auth)]


@router.post("/register", response_model=UserPublic, status_code=201, dependencies=mutations)
async def register(body: Register, request: Request, session: Session) -> User:
    if not request.app.state.settings.registration_enabled:
        raise HTTPException(403, "Registration disabled")
    user = User(
        email=str(body.email),
        name=body.name.strip(),
        password_hash=await run_in_threadpool(
            password_hasher.hash, body.password.get_secret_value()
        ),
        role=Role(request.app.state.settings.registration_default_role),
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Registration could not be completed") from None
    await session.refresh(user)
    logger.info("auth.registered", extra={"actor_id": str(user.id), "audit": True})
    return user


@router.post("/login", response_model=UserPublic, dependencies=mutations)
async def login(body: Login, request: Request, response: Response, session: Session) -> User:
    user = await session.scalar(select(User).where(User.email == str(body.email)))
    valid = await run_in_threadpool(
        password_hasher.verify,
        body.password.get_secret_value(),
        user.password_hash if user else DUMMY_HASH,
    )
    if not valid or user is None:
        logger.info("auth.login_denied", extra={"audit": True})
        raise HTTPException(401, "Invalid credentials")
    old = request.cookies.get(COOKIE)
    if old:
        await request.app.state.redis.delete(session_key(old))
    token = secrets.token_urlsafe(32)
    settings = request.app.state.settings
    await request.app.state.redis.set(
        session_key(token), str(user.id), ex=settings.session_ttl_seconds
    )
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.session_ttl_seconds,
        path="/api/v1",
    )
    logger.info("auth.logged_in", extra={"actor_id": str(user.id), "audit": True})
    return user


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> User:
    return user


@router.post("/logout", response_model=Message, dependencies=[Depends(trusted_origin)])
async def logout(request: Request, response: Response, user: CurrentUser) -> Message:
    await request.app.state.redis.delete(session_key(request.cookies[COOKIE]))
    response.delete_cookie(
        COOKIE,
        path="/api/v1",
        secure=request.app.state.settings.cookie_secure,
        httponly=True,
        samesite="strict",
    )
    logger.info("auth.logged_out", extra={"actor_id": str(user.id), "audit": True})
    return Message(message="Logged out")
