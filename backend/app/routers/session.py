import uuid

from fastapi import APIRouter, Depends, HTTPException
from livekit.api import AccessToken, VideoGrants

from app.config import Settings, get_settings
from app.schemas import SessionTokenRequest, SessionTokenResponse

router = APIRouter()


@router.post("/session/token", response_model=SessionTokenResponse)
def create_session_token(
    body: SessionTokenRequest,
    settings: Settings = Depends(get_settings),
) -> SessionTokenResponse:
    if not (settings.livekit_url and settings.livekit_api_key and settings.livekit_api_secret):
        raise HTTPException(status_code=500, detail="LiveKit is not configured on the server")

    order_session_id = uuid.uuid4().hex
    room_name = f"order-{order_session_id}"
    identity = f"customer-{order_session_id}"

    token = (
        AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(body.customer_name or "Customer")
        .with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )

    return SessionTokenResponse(
        livekit_url=settings.livekit_url,
        room_name=room_name,
        token=token,
        order_session_id=order_session_id,
    )
