from pydantic import BaseModel, Field
from typing import Optional,List,Literal,Dict,Any

class CheckoutStartRequest(BaseModel):
    session_id : str

class Address(BaseModel):
    name : str
    phone : str
    line1 : str
    line2 : Optional[str] = None
    city : str
    pincode : str
    landmark : Optional[str] = None

class CheckoutAddressRequest(BaseModel):
    session_id : str
    address : Address

PaymentMethod = Literal["COD","UPI","CARD"]

class CheckoutPaymentRequest(BaseModel):
    session_id : str
    payment_method : PaymentMethod

class CheckoutConfirmRequest(BaseModel):
    session_id : str
    confirm : bool = Field(..., description="true to place order, false to cancel checkout")


# ---- Response models (simple + flexible) ----
class ErrorResponse(BaseModel):
    status : Literal["error"] = "error"
    error_code : str
    message : str
    checkout_state : Optional[str] = None

class Bill(BaseModel):
    subtotal : float
    delivery_fee : float
    grand_total : float

class CartItemView(BaseModel):
    item_id: Optional[str] = None
    item_name : str
    price : float
    qty : int
    restaurant_id : Optional[int] = None
    city : Optional[str] = None
    veg_flag : Optional[str] = None

class CheckoutStartResponse(BaseModel):
    status : Literal["ok"] = "ok"
    checkout_state : str
    cart : List[CartItemView]
    bill : Bill
    next_action : str


class GenericOkResponse(BaseModel):
    status : Literal["ok"] = "ok"
    checkout_state : str
    message : str
    bill : Optional[Bill] = None
    payment_method : Optional[PaymentMethod] = None
    order_id : Optional[str] = None