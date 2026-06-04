from uuid import UUID

from fastapi import APIRouter, Query, Response, Security, status

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

router = APIRouter(prefix="/items", tags=["Items"])

_401 = {
    "description": "Unauthorized — missing or invalid access token",
    "content": {"application/json": {"example": {"detail": "Not authenticated"}}},
}
_404 = {
    "description": "Item not found or has been deleted",
    "content": {"application/json": {"example": {"detail": "Item not found"}}},
}
_400 = {
    "description": "Bad Request — validation error",
    "content": {
        "application/json": {
            "example": {"detail": [{"msg": "Value error, ...", "type": "value_error"}]}
        }
    },
}
_409 = {
    "description": "Conflict — item with this name already exists",
    "content": {"application/json": {"example": {"detail": "Item with this name already exists"}}},
}


@router.get(
    "",
    response_model=ItemListResponse,
    status_code=status.HTTP_200_OK,
    summary="List items with pagination",
    description=(
        "Returns a paginated list of active (non-deleted) items. "
        "Use `page` and `limit` query parameters to navigate through pages. "
        "Maximum 100 items per page."
    ),
    responses={
        200: {
            "description": "Paginated list of items",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440001",
                                "name": "My First Item",
                                "description": "Description of the first item",
                                "status": "active",
                                "created_at": "2026-05-27T10:30:00Z",
                                "updated_at": "2026-05-27T10:30:00Z",
                            }
                        ],
                        "meta": {"total": 1, "page": 1, "limit": 10, "totalPages": 1},
                    }
                }
            },
        },
        400: _400,
        401: _401,
    },
)
async def list_items(
    page: int = Query(default=1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(default=10, ge=1, le=100, description="Number of items per page (1–100)"),
    current_user: User = Security(get_current_user),
) -> ItemListResponse:
    params = PaginationQuery(page=page, limit=limit)
    service = ItemService()
    data, meta = await service.list(page=params.page, limit=params.limit)
    return ItemListResponse(data=data, meta=meta)


@router.get(
    "/{item_id}",
    response_model=ItemRead,
    status_code=status.HTTP_200_OK,
    summary="Get item by ID",
    description="Returns a single active item by its UUID. Returns 404 if the item does not exist or has been soft-deleted.",
    responses={
        200: {
            "description": "Item found",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "name": "My First Item",
                        "description": "Description of the first item",
                        "status": "active",
                        "created_at": "2026-05-27T10:30:00Z",
                        "updated_at": "2026-05-27T10:30:00Z",
                    }
                }
            },
        },
        401: _401,
        404: _404,
    },
)
async def get_item(
    item_id: UUID,
    current_user: User = Security(get_current_user),
) -> ItemRead:
    service = ItemService()
    return await service.get_by_id_cached(item_id)


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
    description="Creates a new item. Item names must be unique across all active items.",
    responses={
        201: {
            "description": "Item created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "name": "My First Item",
                        "description": "This is a detailed description of my first item",
                        "status": "active",
                        "created_at": "2026-05-27T10:30:00Z",
                        "updated_at": "2026-05-27T10:30:00Z",
                    }
                }
            },
        },
        400: _400,
        401: _401,
        409: _409,
    },
)
async def create_item(
    payload: ItemCreate,
    current_user: User = Security(get_current_user),
) -> ItemRead:
    service = ItemService()
    return await service.create(payload)


@router.put(
    "/{item_id}",
    response_model=ItemRead,
    status_code=status.HTTP_200_OK,
    summary="Replace item (full update)",
    description=(
        "Fully replaces an existing item. All fields are required. "
        "Returns 404 if the item does not exist or has been soft-deleted."
    ),
    responses={
        200: {
            "description": "Item replaced successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "name": "Updated Item Name",
                        "description": "Updated description for the item",
                        "status": "inactive",
                        "created_at": "2026-05-27T10:30:00Z",
                        "updated_at": "2026-05-27T13:00:00Z",
                    }
                }
            },
        },
        400: _400,
        401: _401,
        404: _404,
        409: _409,
    },
)
async def put_item(
    item_id: UUID,
    payload: ItemPut,
    current_user: User = Security(get_current_user),
) -> ItemRead:
    service = ItemService()
    return await service.put(item_id=item_id, payload=payload)


@router.patch(
    "/{item_id}",
    response_model=ItemRead,
    status_code=status.HTTP_200_OK,
    summary="Partially update item",
    description=(
        "Updates only the provided fields of an existing item. "
        "Omitted fields remain unchanged. "
        "Returns 404 if the item does not exist or has been soft-deleted."
    ),
    responses={
        200: {
            "description": "Item updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440001",
                        "name": "My First Item",
                        "description": "This is a detailed description of my first item",
                        "status": "archived",
                        "created_at": "2026-05-27T10:30:00Z",
                        "updated_at": "2026-05-27T14:00:00Z",
                    }
                }
            },
        },
        400: _400,
        401: _401,
        404: _404,
        409: _409,
    },
)
async def patch_item(
    item_id: UUID,
    payload: ItemPatch,
    current_user: User = Security(get_current_user),
) -> ItemRead:
    service = ItemService()
    return await service.patch(item_id=item_id, payload=payload)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete item",
    description=(
        "Marks the item as deleted (soft delete — sets `deleted_at` timestamp). "
        "The item is no longer returned in list or get-by-ID responses. "
        "Returns 204 No Content on success."
    ),
    responses={
        204: {"description": "Item deleted successfully — no content returned"},
        401: _401,
        404: _404,
    },
)
async def delete_item(
    item_id: UUID,
    current_user: User = Security(get_current_user),
) -> Response:
    service = ItemService()
    await service.soft_delete(item_id=item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
