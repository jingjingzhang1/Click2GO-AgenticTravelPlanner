from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # AI API Keys
    anthropic_api_key: str = ""
    google_maps_api_key: str = ""
    baidu_maps_api_key: str = ""

    # Database
    database_url: str = "sqlite:///./click2go.db"

    # Xiaohongshu MCP Server
    mcp_server_url: str = "http://localhost:18060/mcp"

    # LongCat Image Generation
    longcat_api_key: str = ""
    longcat_api_url: str = "https://api.wavespeed.ai/api/v3/wavespeed-ai/longcat-image/text-to-image"

    # App
    app_env: str = "development"
    secret_key: str = "changethis"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
