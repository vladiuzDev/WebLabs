from datetime import date

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.api.items import router as items_router
from src.api.auth import router as auth_router
from src.core.database import Base, engine
from src.models.item import Item  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.token import Token  # noqa: F401
from src.models.password_reset import PasswordReset  # noqa: F401

app = FastAPI(title="WebLab API", version="3.0.0")
app.include_router(items_router)
app.include_router(auth_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def generic_exception_handler(_, __: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


def days_before_new_year(today: date | None = None) -> int:
    current = today or date.today()
    next_new_year = date(current.year + 1, 1, 1)
    return (next_new_year - current).days


@app.get("/info")
def get_info() -> dict[str, int]:
    return {"days_before_new_year": days_before_new_year()}