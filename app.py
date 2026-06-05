import os
from datetime import date

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from src.api.auth import router as auth_router
from src.api.files import router as files_router
from src.api.items import router as items_router
from src.api.profile import router as profile_router
from src.core.database import init_db
from src.services.storage import storage

APP_ENV = os.getenv("APP_ENV", "development")
_is_dev = APP_ENV != "production"

_DESCRIPTION = """
## WebLab REST API — Лабораторные работы 2–7

REST API на базе **FastAPI**, **MongoDB** (Beanie ODM) и **MinIO** (Object Storage).

### Возможности
- **CRUD для items** — создание, чтение, обновление, мягкое удаление, пагинация
- **JWT аутентификация** — токены в HttpOnly cookies (access 15 мин / refresh 7 дней)
- **OAuth2** — авторизация через Yandex ID (Authorization Code flow)
- **Сброс пароля** — одноразовые токены с ограниченным сроком действия
- **Redis кеширование** — cache-aside для items, файлов и профиля
- **Хранение файлов** — загрузка/скачивание через MinIO (потоковая обработка)
- **Профиль пользователя** — обновление данных и установка аватара
- **OpenAPI документация** — доступна только в режиме `development`

### Аутентификация
API использует **HttpOnly cookies** для хранения токенов.
После успешного `/auth/login` браузер автоматически отправляет cookies с каждым запросом.

Для ручного тестирования защищённых эндпоинтов:
1. Вызовите **POST /auth/login** — cookies установятся автоматически.
2. Или скопируйте JWT из cookie и нажмите **🔒 Authorize** (Bearer).
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
            "All endpoints require authentication."
        ),
    },
    {
        "name": "Files",
        "description": (
            "File upload, download and deletion via MinIO object storage. "
            "Files are streamed — not buffered in memory. "
            "Users can only access their own files."
        ),
    },
    {
        "name": "Profile",
        "description": (
            "Get and update the current user profile, including avatar. "
            "To set an avatar: upload an image via **POST /files**, then pass the `id` to **POST /profile**."
        ),
    },
]

app = FastAPI(
    title="WebLab API",
    version="7.0.0",
    description=_DESCRIPTION,
    openapi_tags=tags_metadata,
    docs_url="/api/docs" if _is_dev else None,
    redoc_url="/api/redoc" if _is_dev else None,
    openapi_url="/api/openapi.json" if _is_dev else None,
)

app.include_router(auth_router)
app.include_router(items_router)
app.include_router(files_router)
app.include_router(profile_router)


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

        schemes["bearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Paste a raw JWT access token obtained from the `access_token` cookie "
                "after calling **POST /auth/login**."
            ),
        }
        schemes["cookieAuth"] = {
            "type": "apiKey",
            "in": "cookie",
            "name": "access_token",
            "description": "JWT access token stored in an HttpOnly cookie.",
        }
        schemes["oauth2Yandex"] = {
            "type": "oauth2",
            "description": "Yandex ID OAuth2 Authorization Code flow.",
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
async def startup() -> None:
    await init_db()
    storage.ensure_bucket()


def days_before_new_year(today: date | None = None) -> int:
    current = today or date.today()
    next_new_year = date(current.year + 1, 1, 1)
    return (next_new_year - current).days


@app.get("/info", tags=["Info"], summary="Server info", description="Returns the number of days until the next New Year.")
def get_info() -> dict[str, int]:
    return {"days_before_new_year": days_before_new_year()}
