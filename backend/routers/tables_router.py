from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from schemas import AddTableItemRequest, TableCheckoutRequest, VoidRequest
from deps import get_current_user, CurrentUser
import services

router = APIRouter(prefix="/tables", tags=["tables"])


@router.get("")
def list_tables(current_user: CurrentUser = Depends(get_current_user)):
    return services.list_tables()


@router.get("/{table_id}/order")
def get_table_order(table_id: int, current_user: CurrentUser = Depends(get_current_user)):
    order_id = services.get_open_table_order_id(table_id)
    if order_id is None:
        return {"table_order_id": None, "table_id": table_id, "status": "empty",
                "items": [], "subtotal": 0, "vat_amount": 0, "total": 0}
    try:
        return services.get_table_order_detail(order_id)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/{table_id}/items")
def add_table_item(table_id: int, payload: AddTableItemRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        item_id = services.add_item_to_table_order(
            table_id, payload.item_variant_id, payload.quantity, current_user.id
        )
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"table_order_item_id": item_id}


@router.post("/order-items/{table_order_item_id}/void")
def void_table_item(table_order_item_id: int, payload: VoidRequest, current_user: CurrentUser = Depends(get_current_user)):
    try:
        services.void_table_order_item(table_order_item_id, current_user.id, payload.reason)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return {"ok": True}


@router.post("/{table_id}/request-bill")
def request_bill(table_id: int, current_user: CurrentUser = Depends(get_current_user)):
    order_id = services.get_open_table_order_id(table_id)
    if order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This table has no open order.")
    services.request_table_bill(order_id, current_user.id)
    return {"ok": True}


@router.post("/{table_id}/checkout")
def checkout_table(table_id: int, payload: TableCheckoutRequest, current_user: CurrentUser = Depends(get_current_user)):
    order_id = services.get_open_table_order_id(table_id)
    if order_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This table has no open order.")
    try:
        receipt = services.checkout_table_order(order_id, payload.payment_method, current_user.id)
    except services.ServiceError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return asdict(receipt)
