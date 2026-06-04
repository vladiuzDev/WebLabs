import os

from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


MONGO_URI = get_env("MONGO_URI")
DB_NAME = get_env("DB_NAME", "wp_labs")

JWT_ACCESS_SECRET = get_env("JWT_ACCESS_SECRET")
JWT_REFRESH_SECRET = get_env("JWT_REFRESH_SECRET")
CLIENT_ID = get_env("CLIENT_ID")
CLIENT_SECRET = get_env("CLIENT_SECRET")
CALLBACK_URL = get_env("CALLBACK_URL")

APP_ENV = get_env("APP_ENV", "development")

REDIS_HOST = get_env("REDIS_HOST", "localhost")
REDIS_PORT = int(get_env("REDIS_PORT", "6379"))
REDIS_PASSWORD = get_env("REDIS_PASSWORD", "")
CACHE_TTL_DEFAULT = int(get_env("CACHE_TTL_DEFAULT", "300"))
ACCESS_TOKEN_EXPIRE_SECONDS = 15 * 60
