from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: int
    username: str
    role: str
    must_change_password: bool


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class CartLineIn(BaseModel):
    item_variant_id: int
    quantity: int = Field(gt=0)


class SaleRequest(BaseModel):
    cart: list[CartLineIn]
    payment_method: str  # 'cash' | 'card'


class VoidRequest(BaseModel):
    reason: str = Field(min_length=1)


class AddTableItemRequest(BaseModel):
    item_variant_id: int
    quantity: int = Field(gt=0)


class TableCheckoutRequest(BaseModel):
    payment_method: str  # 'cash' | 'card'
