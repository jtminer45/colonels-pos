from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from schemas import SaleRequest, VoidRequest
from deps import get_current_user, CurrentUser
import services

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("")
def create_sale(payload: SaleRequest, current_user: CurrentUser = Depends(get_current_user)):
    cart = [services.CartLine(item_variant_id=l.item_variant_id, quantity=l.quantity) for l in payload.cart]
    try:
        receipt = services.record_sale(cart, current_user.id, payload.payment_method)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return asdict(receipt)


@router.post("/void/{sale_item_id}")
def void_item(sale_item_id: int, payload: VoidRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        services.void_sale_item(sale_item_id, current_user.id, payload.reason)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"ok": True}


@router.get("/shift-summary")
def shift_summary(current_user: CurrentUser = Depends(get_current_user)):
    try:
        return services.get_shift_summary(current_user.id, current_user.session_id)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
