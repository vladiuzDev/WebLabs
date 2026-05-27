from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, Query, Response, status
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.middleware import get_current_user
from src.models.user import User
from src.schemas.item import (
    ItemCreate,
    ItemListResponse,
    ItemPatch,
    ItemPut,
    ItemRead,
    PaginationQuery,
)
from src.services.item_service import ItemService

router = APIRouter(prefix="/items", tags=["items"])


def get_user(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    return get_current_user(access_token=access_token, db=db)


@router.get("", response_model=ItemListResponse, status_code=status.HTTP_200_OK)
def list_items(
    page: int = Query(default=1),
    limit: int = Query(default=10),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_user),
) -> ItemListResponse:
    params = PaginationQuery(page=page, limit=limit)
    service = ItemService(db)
    data, meta = service.list(page=params.page, limit=params.limit)
    return ItemListResponse(data=data, meta=meta)


@router.get("/{item_id}", response_model=ItemRead, status_code=status.HTTP_200_OK)
def get_item(item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_user)) -> ItemRead:
    service = ItemService(db)
    return service.get_active_by_id(item_id)


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_user)) -> ItemRead:
    service = ItemService(db)
    return service.create(payload)


@router.put("/{item_id}", response_model=ItemRead, status_code=status.HTTP_200_OK)
def put_item(item_id: UUID, payload: ItemPut, db: Session = Depends(get_db), current_user: User = Depends(get_user)) -> ItemRead:
    service = ItemService(db)
    return service.put(item_id=item_id, payload=payload)


@router.patch("/{item_id}", response_model=ItemRead, status_code=status.HTTP_200_OK)
def patch_item(item_id: UUID, payload: ItemPatch, db: Session = Depends(get_db), current_user: User = Depends(get_user)) -> ItemRead:
    service = ItemService(db)
    return service.patch(item_id=item_id, payload=payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_user)) -> Response:
    service = ItemService(db)
    service.soft_delete(item_id=item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)