import os

from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


DB_HOST = get_env("DB_HOST", "localhost")
DB_PORT = int(get_env("DB_PORT", "5432"))
DB_USER = get_env("DB_USER", "student")
DB_PASSWORD = get_env("DB_PASSWORD", "student_secure_password")
DB_NAME = get_env("DB_NAME", "wp_labs")

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
JWT_ACCESS_SECRET = get_env("JWT_ACCESS_SECRET")
JWT_REFRESH_SECRET = get_env("JWT_REFRESH_SECRET")
CLIENT_ID = get_env("CLIENT_ID")
CLIENT_SECRET = get_env("CLIENT_SECRET")
CALLBACK_URL = get_env("CALLBACK_URL")