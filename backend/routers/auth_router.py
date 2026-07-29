from fastapi import APIRouter, Depends, HTTPException, status

from schemas import LoginRequest, LoginResponse, ChangePasswordRequest
from deps import get_current_user, CurrentUser
from security import create_token

import auth as auth_module

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    try:
        user = auth_module.login(payload.username, payload.password)
    except auth_module.AuthError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(e))

    token = create_token(user.session_id)
    return LoginResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/logout")
def logout(current_user: CurrentUser = Depends(get_current_user)):
    auth_module.logout(current_user.session_id)
    return {"ok": True}


@router.post("/change-password")
def change_password(payload: ChangePasswordRequest, current_user: CurrentUser = Depends(get_current_user)):
    auth_module.set_password(current_user.id, payload.new_password, force_change_next_login=False)
    return {"ok": True}
