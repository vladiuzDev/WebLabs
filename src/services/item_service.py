from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.item import Item
from src.schemas.item import ItemCreate, ItemPatch, ItemPut, PaginationMeta


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
        return item

    def list(self, page: int, limit: int) -> tuple[list[Item], PaginationMeta]:
        offset = (page - 1) * limit
        total_stmt = select(func.count(Item.id)).where(Item.deleted_at.is_(None))
        total = self.db.execute(total_stmt).scalar_one()

        data_stmt = (
            select(Item)
            .where(Item.deleted_at.is_(None))
            .order_by(Item.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(data_stmt).scalars().all())
        total_pages = (total + limit - 1) // limit if total > 0 else 0
        return items, PaginationMeta(total=total, page=page, limit=limit, totalPages=total_pages)

    def get_active_by_id(self, item_id: UUID) -> Item:
        stmt = select(Item).where(Item.id == item_id, Item.deleted_at.is_(None))
        item = self.db.execute(stmt).scalar_one_or_none()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return item

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
        return item

    def soft_delete(self, item_id: UUID) -> None:
        item = self.get_active_by_id(item_id)
        item.deleted_at = datetime.now(timezone.utc)
        self.db.commit()
