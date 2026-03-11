#API request/response schemas (Pydantic)

from pydantic import BaseModel, Field
from typing import Optional, List, Literal

class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=1)

    # Filters (optional)
    city: Optional[Literal["Bangalore", "Delhi", "Mumbai"]] = None
    veg_flag: Optional[str] = None  # "Veg" / "Non-veg" (dataset dependent)
    max_price: Optional[float] = None
    category: Optional[str] = None  # menu/category

class RetrievedItem(BaseModel):
    item_id: str
    item_name: str
    category: Optional[str] = None
    price: Optional[float] = None
    veg_flag: Optional[str] = None
    city: str
    restaurant_id: int
    score: float

class RetrieveResponse(BaseModel):
    index_version: str
    top1_score: float
    confidence: Literal["high", "medium", "low"]
    results: List[RetrievedItem]
    debug: dict