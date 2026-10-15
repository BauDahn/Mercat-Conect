from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

STATUS = {
    "bad_request": 400, "validation_failed": 422, "unauthorized": 401, "invalid_credentials": 401,
    "forbidden": 403, "not_found": 404, "conflict": 409, "rate_limited": 429, "email_taken": 409,
    "account_not_verified": 403, "age_not_verified": 403, "person_already_registered": 409,
    "idempotency_key_required": 400, "idempotency_key_reused": 409, "offer_not_active": 409,
    "out_of_stock": 409, "no_points": 409, "exceeds_max": 403, "insufficient_reputation": 403,
    "no_locker_capacity": 409, "invalid_transition": 409, "payment_failed": 409,
    "invalid_signature": 401, "demo_only": 404,
}


class ApiError(Exception):
    def __init__(self, code: str, message_key: str | None = None, status: int | None = None, **params: Any):
        self.code = code
        self.status = status or STATUS[code]
        self.message_key = message_key or f"errors.{code}"
        self.params = params
        super().__init__(code)

    def body(self) -> dict:
        return {"error": {"code": self.code, "message_key": self.message_key, "params": self.params}}


def _resp(status: int, code: str, params: dict | None = None, key: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message_key": key or f"errors.{code}", "params": params or {}}},
    )


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        errs = [{"loc": [str(x) for x in e.get("loc", [])], "msg": str(e.get("msg", ""))} for e in exc.errors()]
        return _resp(422, "validation_failed", {"errors": errs})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
                405: "bad_request", 409: "conflict", 429: "rate_limited"}.get(exc.status_code, "bad_request")
        return _resp(exc.status_code, code)
