from fastapi import APIRouter, Depends

from deps import get_current_user, CurrentUser
import services

router = APIRouter(prefix="/menu", tags=["menu"])


@router.get("")
def get_menu(current_user: CurrentUser = Depends(get_current_user)):
    # Any authenticated user (staff or manager) can view the menu — the till
    # needs it to render category/item tiles. It carries no manager-only data.
    return services.get_menu_tree()
