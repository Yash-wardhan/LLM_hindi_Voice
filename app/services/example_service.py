from typing import Optional

from app.models.schemas import ItemCreate, ItemResponse, ItemUpdate


class ExampleService:
    """
    In-memory CRUD service — replace storage with your DB layer (SQLAlchemy, etc.).
    """

    def __init__(self) -> None:
        self._store: dict[int, ItemResponse] = {}
        self._counter: int = 0

    def get_all(self) -> list[ItemResponse]:
        return list(self._store.values())

    def get_by_id(self, item_id: int) -> Optional[ItemResponse]:
        return self._store.get(item_id)

    def create(self, payload: ItemCreate) -> ItemResponse:
        self._counter += 1
        item = ItemResponse(id=self._counter, **payload.model_dump())
        self._store[self._counter] = item
        return item

    def update(self, item_id: int, payload: ItemUpdate) -> Optional[ItemResponse]:
        existing = self._store.get(item_id)
        if not existing:
            return None
        updated_data = existing.model_dump()
        updated_data.update({k: v for k, v in payload.model_dump().items() if v is not None})
        updated = ItemResponse(**updated_data)
        self._store[item_id] = updated
        return updated

    def delete(self, item_id: int) -> bool:
        if item_id not in self._store:
            return False
        del self._store[item_id]
        return True
