import os
from datetime import date

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from src.api.items import router as items_router
from src.api.auth import router as auth_router
from src.core.database import Base, engine
from src.models.item import Item  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.token import Token  # noqa: F401
from src.models.password_reset import PasswordReset  # noqa: F401

APP_ENV = os.getenv("APP_ENV", "development")
_is_dev = APP_ENV != "production"

_DESCRIPTION = """
## WebLab REST API — Labs 2–4

A fully-featured REST API built with **FastAPI** and **PostgreSQL**.

### Features
- **Items CRUD** — create, read, update (full & partial), soft-delete, paginate
- **JWT authentication** — cookie-based HttpOnly tokens (access 15 min / refresh 7 days)
- **OAuth2** — Yandex ID Authorization Code flow
- **Password reset** — single-use time-limited tokens
- **OpenAPI documentation** — auto-generated (available in `development` only)

### Authentication
The API uses **HttpOnly cookies** for authentication.
After a successful `/auth/login` the browser automatically sends cookies with every request,
including requests made from this Swagger UI (same origin).

To test protected endpoints manually:
1. Call **POST /auth/login** — cookies are set automatically in the browser.
2. Or copy the raw JWT value from the cookie and click the **🔒 Authorize** button above to use Bearer auth.
"""

tags_metadata = [
    {
        "name": "Auth",
        "description": (
            "Registration, login, token refresh, logout, OAuth2 (Yandex) and password reset. "
            "Login sets **HttpOnly cookies** (`access_token`, `refresh_token`)."
        ),
    },
    {
        "name": "Items",
        "description": (
            "Full CRUD for items with soft-delete and pagination. "
            "All endpoints require authentication (cookie or Bearer token)."
        ),
    },
]

app = FastAPI(
    title="WebLab API",
    version="4.0.0",
    description=_DESCRIPTION,
    openapi_tags=tags_metadata,
    docs_url="/api/docs" if _is_dev else None,
    redoc_url="/api/redoc" if _is_dev else None,
    openapi_url="/api/openapi.json" if _is_dev else None,
)

app.include_router(auth_router)
app.include_router(items_router)


if _is_dev:
    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            tags=app.openapi_tags,
            routes=app.routes,
        )

        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})

        # bearerAuth is auto-added by FastAPI via HTTPBearer Security() dep,
        # but we enrich its description here.
        schemes["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Paste a raw JWT access token obtained from the `access_token` cookie "
                "after calling **POST /auth/login**. "
                "Click **Authorize**, enter the token value (without 'Bearer ' prefix), "
                "and all protected endpoints will include the header automatically."
            ),
        }

        # Cookie-based auth — informational; browsers send cookies automatically.
        schemes["cookieAuth"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": (
                "JWT access token stored in an **HttpOnly cookie**. "
                "The browser sends it automatically after `/auth/login`. "
                "This scheme is informational — use Bearer auth for manual Swagger UI testing."
            ),
        }

        # OAuth2 Yandex — documents the Authorization Code flow.
        schemes["oauth2Yandex"] = {
            "type": "oauth2",
            "description": "Yandex ID OAuth2 Authorization Code flow (initiated via GET /auth/oauth/yandex).",
            "flows": {
                "authorizationCode": {
                    "authorizationUrl": "https://oauth.yandex.ru/authorize",
                    "tokenUrl": "https://oauth.yandex.ru/token",
                    "scopes": {},
                }
            },
        }

        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


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


@app.get("/info", tags=["Info"], summary="Server info", description="Returns the number of days until the next New Year.")
def get_info() -> dict[str, int]:
    return {"days_before_new_year": days_before_new_year()}
