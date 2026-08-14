from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    backend_public_base_url: str = "http://localhost:8000"
    frontend_public_base_url: str = "http://localhost:5173"

    livekit_url: str | None = None
    livekit_api_key: str | None = None
    livekit_api_secret: str | None = None

    admin_jwt_secret: str
    # Staff shift length — how long an admin login stays valid before requiring a re-login.
    admin_jwt_expire_minutes: int = 12 * 60

    payu_merchant_key: str | None = None
    payu_merchant_salt: str | None = None
    # Hosted checkout POST endpoint. Defaults to PayU's test sandbox; swap to
    # https://secure.payu.in/_payment for production.
    payu_payment_url: str = "https://test.payu.in/_payment"

    # No physical receipt printer yet — stand-in is opening the printable receipt in a new
    # Chrome tab on whatever machine the backend process runs on. Only makes sense while backend
    # and counter screen are the same machine; turn off once a real printer (or a separate
    # backend host) is wired up.
    auto_open_receipt: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
