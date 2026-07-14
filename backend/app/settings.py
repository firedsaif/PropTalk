"""Env/secret loading. One Settings object, read once, imported everywhere.

Reads the repo-root .env (gitignored) the same way app/db.py does.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    app_env: str = "local"
    log_level: str = "info"
    pilot_minutes_cap: int = 300
    feature_sms_enabled: bool = False

    database_url: str = ""

    retell_api_key: str = ""
    retell_webhook_secret: str = ""

    calcom_api_key: str = ""
    calcom_event_type_id: str = ""

    resend_api_key: str = ""
    from_email: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""


settings = Settings()
