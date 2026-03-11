from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .observability import setup_observability

from .schemas import (
    CheckoutStartRequest,
    CheckoutPaymentRequest,
    CheckoutAddressRequest,
    CheckoutConfirmRequest,
    CheckoutStartResponse,
    GenericOkResponse,
    ErrorResponse
)

from .checkout_logic import start_checkout,save_address,save_payment,confirm_checkout

app = FastAPI(title='checkout-service',version='0.1')

setup_observability(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_credentials = True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi import Response

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@app.get("/health")
def health():
    return {"ok":True,"service":"checkout-service"}

@app.post("/checkout/start",response_model=CheckoutStartResponse | ErrorResponse)
def checkout_start(req:CheckoutStartRequest):
    out = start_checkout(req.session_id)
    if not out.get("ok"):
        return ErrorResponse(error_code=out["error_code"],message=out["message"])
    #If already placed, still return ok with bill/cart
    if out.get("checkout_state") == "PLACED":
        return CheckoutStartResponse(
            checkout_state=out['checkout_state'],
            cart=out.get("cart",[]),
            bill=out.get("bill"),
            next_action = f"Order already placed: {out.get('order_id')}",
        )
    return CheckoutStartResponse(
        checkout_state=out['checkout_state'],
        cart=out['cart'],
        bill=out['bill'],
        next_action=out['next_action'],
    )


@app.post("/checkout/address", response_model=GenericOkResponse | ErrorResponse)
def checkout_address(req:CheckoutAddressRequest):
    out = save_address(req.session_id,req.address.model_dump())
    if not out.get("ok"):
        return ErrorResponse(error_code=out["error_code"],message=out["message"],checkout_state=out.get("checkout_state"))
    return GenericOkResponse(
        checkout_state=out["checkout_state"],
        message = out["message"],
        order_id = out.get("order_id"),
    )


@app.post("/checkout/payment",response_model=GenericOkResponse | ErrorResponse)
def checkout_payment(req:CheckoutPaymentRequest):
    out = save_payment(req.session_id,req.payment_method)
    if not out.get("ok"):
        return ErrorResponse(error_code=out["error_code"],message=out["message"],checkout_state=out.get("checkout_state"))
    return GenericOkResponse(
        checkout_state=out["checkout_state"],
        message=out["message"],
        bill = out.get("bill"),
        payment_method=out.get("payment_method"),
        order_id=out.get("order_id"),
    )


@app.post("/checkout/confirm",response_model=GenericOkResponse | ErrorResponse)
def checkout_confirm(req:CheckoutConfirmRequest):
    out = confirm_checkout(req.session_id,req.confirm)
    if not out.get("ok"):
        return ErrorResponse(error_code=out["error_code"],message=out["message"],checkout_state=out.get("checkout_state"))
    return GenericOkResponse(
        checkout_state=out["checkout_state"],
        message=out["message"],
        order_id = out.get("order_id"),
        bill = out.get("bill"),
        payment_method=out.get("payment_method"),
    )