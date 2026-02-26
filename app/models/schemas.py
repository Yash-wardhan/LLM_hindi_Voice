from typing import Optional

from pydantic import BaseModel, Field


# ── Health ──────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    timestamp: str
    uptime_seconds: float


# ── Item (example resource) ──────────────────────────────────────────────────

class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["My item"])
    description: Optional[str] = Field(None, max_length=500)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class ItemResponse(ItemBase):
    id: int

    model_config = {"from_attributes": True}
