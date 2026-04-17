from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AI API Keys
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    google_maps_api_key: str = ""

    # Image Generation (Replicate – FLUX Schnell)
    replicate_api_token: str = ""

    # Database – SQLite (seed architecture)
    database_url: str = "sqlite:///./click2go.db"

    # Xiaohongshu MCP Server
    mcp_server_url: str = "http://localhost:18060/mcp"

    # App
    app_env: str = "development"
    secret_key: str = "changethis"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
