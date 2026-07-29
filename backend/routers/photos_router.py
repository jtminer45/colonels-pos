from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response

import services

router = APIRouter(prefix="/photos", tags=["photos"])

# Deliberately unauthenticated: a browser <img src="..."> / Streamlit
# st.image(url) request never carries the Authorization header, and a menu
# item photo isn't sensitive data — the same tradeoff bundled static menu
# photos already have (also served with no auth, straight from Netlify).
@router.get("/{item_id}")
def get_photo(item_id: int):
    result = services.get_item_photo(item_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No uploaded photo for this item.")
    photo_bytes, content_type = result
    return Response(content=photo_bytes, media_type=content_type)
