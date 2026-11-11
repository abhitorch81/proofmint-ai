from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = 'sqlite:///./proofmint.db'
    frontend_url: str = 'http://localhost:3000'
    cors_origins: str = 'http://localhost:3000'
    paypal_client_id: str = ''
    paypal_client_secret: str = ''
    paypal_base_url: str = 'https://api-m.sandbox.paypal.com'
    receipt_signing_secret: str = 'development-only-change-me'
    app_env: str = 'development'
    whisper_model: str = 'tiny.en'
    max_video_mb: int = 100
    max_video_seconds: int = 3600
    demo_upload_token: str = ''
    upload_dir: str = './uploads'
    momentweave_export_dir: str = './momentweave_exports'
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

@lru_cache
def get_settings():
    return Settings()
