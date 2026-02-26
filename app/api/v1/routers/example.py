from fastapi import APIRouter, HTTPException, status

from app.models.schemas import ItemCreate, ItemResponse, ItemUpdate
from app.services.example_service import ExampleService

router = APIRouter()
service = ExampleService()


@router.get("/items", response_model=list[ItemResponse], summary="List all items")
async def list_items() -> list[ItemResponse]:
    return service.get_all()


@router.get("/items/{item_id}", response_model=ItemResponse, summary="Get item by ID")
async def get_item(item_id: int) -> ItemResponse:
    item = service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.post(
    "/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new item",
)
async def create_item(payload: ItemCreate) -> ItemResponse:
    return service.create(payload)


@router.patch("/items/{item_id}", response_model=ItemResponse, summary="Update an item")
async def update_item(item_id: int, payload: ItemUpdate) -> ItemResponse:
    item = service.update(item_id, payload)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an item",
)
async def delete_item(item_id: int) -> None:
    if not service.delete(item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
