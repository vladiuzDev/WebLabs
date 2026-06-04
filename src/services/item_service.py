from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from src.models.item import Item
from src.schemas.item import ItemCreate, ItemPatch, ItemPut, ItemRead, PaginationMeta
from src.services.cache import cache, make_key


def _list_key(page: int, limit: int) -> str:
    return make_key("items", "list", f"page:{page}", f"limit:{limit}")


def _item_key(item_id: UUID) -> str:
    return make_key("items", "item", str(item_id))


def _invalidate_lists() -> None:
    cache.delete_by_pattern(make_key("items", "list", "*"))


def _invalidate_item(item_id: UUID) -> None:
    cache.delete(_item_key(item_id))


class ItemService:
    async def create(self, payload: ItemCreate) -> Item:
        item = Item(**payload.model_dump())
        try:
            await item.insert()
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Item with this name already exists")
        _invalidate_lists()
        return item

    async def list(self, page: int, limit: int) -> tuple[list, PaginationMeta]:
        key = _list_key(page, limit)
        cached = cache.get(key)
        if cached is not None:
            data = [ItemRead.model_validate(d) for d in cached["data"]]
            meta = PaginationMeta.model_validate(cached["meta"])
            return data, meta

        skip = (page - 1) * limit
        total = await Item.find(Item.deleted_at == None).count()
        items = (
            await Item.find(Item.deleted_at == None)
            .sort(-Item.created_at)
            .skip(skip)
            .limit(limit)
            .to_list()
        )

        total_pages = (total + limit - 1) // limit if total > 0 else 0
        meta = PaginationMeta(total=total, page=page, limit=limit, totalPages=total_pages)

        cache.set(key, {
            "data": [ItemRead.model_validate(i).model_dump(mode="json") for i in items],
            "meta": meta.model_dump(),
        })
        return items, meta

    async def get_active_by_id(self, item_id: UUID) -> Item:
        item = await Item.find_one(Item.id == item_id, Item.deleted_at == None)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

    async def get_by_id_cached(self, item_id: UUID) -> ItemRead:
        key = _item_key(item_id)
        cached = cache.get(key)
        if cached is not None:
            return ItemRead.model_validate(cached)

        item = await self.get_active_by_id(item_id)
        item_read = ItemRead.model_validate(item)
        cache.set(key, item_read.model_dump(mode="json"))
        return item_read

    async def put(self, item_id: UUID, payload: ItemPut) -> Item:
        item = await self.get_active_by_id(item_id)
        item.name = payload.name
        item.description = payload.description
        item.status = payload.status
        item.updated_at = datetime.now(timezone.utc)
        try:
            await item.save()
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Item with this name already exists")
        _invalidate_lists()
        _invalidate_item(item_id)
        return item

    async def patch(self, item_id: UUID, payload: ItemPatch) -> Item:
        item = await self.get_active_by_id(item_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(item, key, value)
        item.updated_at = datetime.now(timezone.utc)
        try:
            await item.save()
        except DuplicateKeyError:
            raise HTTPException(status_code=409, detail="Item with this name already exists")
        _invalidate_lists()
        _invalidate_item(item_id)
        return item

    async def soft_delete(self, item_id: UUID) -> None:
        item = await self.get_active_by_id(item_id)
        item.deleted_at = datetime.now(timezone.utc)
        await item.save()
        _invalidate_lists()
        _invalidate_item(item_id)
