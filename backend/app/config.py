from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str
    db_password: str

    # Redis
    redis_url: str

    # Tequila API
    tequila_api_key: str
    tequila_base_url: str = "https://api.tequila.kiwi.com/v2"

    # AI model 
    ai_api_key: str = ""
    ai_model: str = "da_definire"

    # App
    app_env: str = "development"
    cache_ttl_hours: int = 6
    max_airports_search: int = 300

    class Config:
        env_file = ".env"


# Globbal instance for the entire project
settings = Settings()
