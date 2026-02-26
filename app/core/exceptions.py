from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


class NotFoundException(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(status_code=404, detail=f"{resource} not found")


class BadRequestException(AppException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=400, detail=detail)


class UnauthorizedException(AppException):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=401, detail=detail)


# --- Exception Handlers ---

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
