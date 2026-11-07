import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("sidewatch")


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int):
        self.code = code
        self.message = message
        self.status_code = status_code


# Stable error codes. Messages are deliberately generic.
def invalid_credentials():
    return AppError("AUTH_INVALID_CREDENTIALS", "Invalid username or password.", 401)

def account_locked():
    return AppError("AUTH_ACCOUNT_LOCKED", "Account temporarily locked. Try again later.", 423)

def not_authenticated():
    return AppError("AUTH_REQUIRED", "Authentication required.", 401)

def session_expired():
    return AppError("AUTH_SESSION_EXPIRED", "Session expired. Please sign in again.", 401)

def csrf_failed():
    return AppError("CSRF_FAILED", "Request could not be verified.", 403)

def forbidden():
    return AppError("ACCESS_DENIED", "You do not have permission to perform this action.", 403)

def not_found():
    return AppError("NOT_FOUND", "Resource not found.", 404)

def rate_limited():
    return AppError("RATE_LIMITED", "Too many requests. Please slow down.", 429)


def _body(code: str, message: str) -> dict:
    return {"code": code, "message": message, "request_id": uuid.uuid4().hex[:12]}

def user_exists():
    return AppError("USER_EXISTS", "That username is not available.", 409)

def invalid_operation():
    return AppError("INVALID_OPERATION", "This operation is not allowed.", 400)

def invalid_fixture():
    return AppError("INVALID_FIXTURE", "Unknown test fixture.", 422)

def invalid_rule_value():
    return AppError("INVALID_RULE_VALUE", "Value is outside the permitted range.", 422)

def confirmation_required():
    return AppError("CONFIRMATION_REQUIRED", "This action must be confirmed.", 400)

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        return JSONResponse(_body("VALIDATION_ERROR", "Invalid request data."), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(request: Request, exc: StarletteHTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        return JSONResponse(_body(code, "Request could not be completed."), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        body = _body("INTERNAL_ERROR", "An unexpected error occurred.")
        logger.exception("Unhandled error request_id=%s", body["request_id"])
        return JSONResponse(body, status_code=500)