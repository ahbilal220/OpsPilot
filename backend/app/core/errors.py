from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, str] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=ErrorEnvelope(error=ErrorDetail(code=code, message=message)).model_dump(),
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return error_response(exc.status_code, f"HTTP_{exc.status_code}", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Never echo invalid input: it may contain a password or token.
        return error_response(422, "VALIDATION_ERROR", "Request validation failed")

    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(RedisError)
    async def dependency_error(request: Request, exc: Exception) -> JSONResponse:
        return error_response(503, "DEPENDENCY_UNAVAILABLE", "Required service unavailable")
