from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import DB_NAME, MONGO_URI


async def init_db() -> None:
    from src.models.item import Item
    from src.models.password_reset import PasswordReset
    from src.models.token import Token
    from src.models.user import User

    client = AsyncIOMotorClient(MONGO_URI)
    await init_beanie(
        database=client[DB_NAME],
        document_models=[User, Item, Token, PasswordReset],
    )
