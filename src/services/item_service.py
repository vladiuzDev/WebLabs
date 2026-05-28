from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: ItemCreate) -> Item:
        item = Item(**payload.model_dump())
        self.db.add(item)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Item with this name already exists") from exc
        self.db.refresh(item)
        # Invalidate all list pages — a new item changes totals
        _invalidate_lists()
        return item

    def list(self, page: int, limit: int) -> tuple[list, PaginationMeta]:
        key = _list_key(page, limit)
        cached = cache.get(key)
        if cached is not None:
            data = [ItemRead.model_validate(d) for d in cached["data"]]
            meta = PaginationMeta.model_validate(cached["meta"])
            return data, meta

        # Cache miss → query DB
        offset = (page - 1) * limit
        total = self.db.execute(
            select(func.count(Item.id)).where(Item.deleted_at.is_(None))
        ).scalar_one()

        items = list(
            self.db.execute(
                select(Item)
                .where(Item.deleted_at.is_(None))
                .order_by(Item.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).scalars().all()
        )
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        meta = PaginationMeta(total=total, page=page, limit=limit, totalPages=total_pages)

        # Store serialized data in cache
        cache.set(key, {
            "data": [ItemRead.model_validate(i).model_dump(mode="json") for i in items],
            "meta": meta.model_dump(),
        })
        return items, meta

    def get_active_by_id(self, item_id: UUID) -> Item:
        stmt = select(Item).where(Item.id == item_id, Item.deleted_at.is_(None))
        item = self.db.execute(stmt).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

    def get_by_id_cached(self, item_id: UUID) -> ItemRead:
        """GET /items/{id} with Cache-Aside."""
        key = _item_key(item_id)
        cached = cache.get(key)
        if cached is not None:
            return ItemRead.model_validate(cached)

        item = self.get_active_by_id(item_id)
        item_read = ItemRead.model_validate(item)
        cache.set(key, item_read.model_dump(mode="json"))
        return item_read

    def put(self, item_id: UUID, payload: ItemPut) -> Item:
        item = self.get_active_by_id(item_id)
        item.name = payload.name
        item.description = payload.description
        item.status = payload.status
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Item with this name already exists") from exc
        self.db.refresh(item)
        _invalidate_lists()
        _invalidate_item(item_id)
        return item

    def patch(self, item_id: UUID, payload: ItemPatch) -> Item:
        item = self.get_active_by_id(item_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(item, key, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Item with this name already exists") from exc
        self.db.refresh(item)
        _invalidate_lists()
        _invalidate_item(item_id)
        return item

    def soft_delete(self, item_id: UUID) -> None:
        item = self.get_active_by_id(item_id)
        item.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
        _invalidate_lists()
        _invalidate_item(item_id)
