from typing import Optional

from pydantic import BaseModel, Field


class RecommendationRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    activity: Optional[str] = Field(default=None, max_length=80)
    goal: Optional[str] = Field(default=None, max_length=80)
    dietary_preference: Optional[str] = Field(default=None, max_length=80)
    allergies: list[str] = Field(default_factory=list, max_length=20)
    caffeine_sensitive: bool = False


class SupplementCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    description: str = Field(min_length=10, max_length=1500)
    serving_size: str = Field(min_length=1, max_length=100)
    protein_g: float = Field(default=0, ge=0, le=500)
    caffeine_mg: float = Field(default=0, ge=0, le=2000)
    activity_tags: list[str] = Field(default_factory=list, max_length=20)
    goal_tags: list[str] = Field(default_factory=list, max_length=20)
    dietary_tags: list[str] = Field(default_factory=list, max_length=20)
    allergens: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    price: float = Field(gt=0, le=10000)
    stock: int = Field(default=0, ge=0, le=100000)


class PurchaseRequest(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(default=1, gt=0, le=20)
