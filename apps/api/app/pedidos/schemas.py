import uuid

from pydantic import BaseModel, Field


class ItemIn(BaseModel):
    offer_id: uuid.UUID
    qty: int = Field(ge=1)


class CreateOrderRequest(BaseModel):
    items: list[ItemIn] = Field(min_length=1)
