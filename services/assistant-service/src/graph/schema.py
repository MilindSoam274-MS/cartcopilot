from typing import Any, Dict, List, TypedDict, Optional


class AssistantState(TypedDict, total=False):
    # session
    session_id: str

    # current turn
    user_message: str
    intent: str

    # constraints
    city: Optional[str]
    veg_flag: Optional[str]
    max_price: Optional[float]

    # retrieval outputs
    items: List[Dict[str, Any]]
    confidence: str
    reply: str
    debug: Dict[str, Any]

    # memory
    last_items: List[Dict[str, Any]]
    last_results: List[Dict[str, Any]]
    last_confidence: Optional[str]

    # cart
    cart: List[Dict[str, Any]]

    # control flags
    halt: bool
