from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str
    db_password: str

    # Redis
    redis_url: str

    # Flight Provider
    flight_provider: str = "amadeus"
    serpapi_api_key: str = ""          
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""

    # LLM Provider
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    mistral_api_key: str = ""

    # App
    app_env: str = "development"
    cache_ttl_hours: int = 6
    max_airports_search: int = 300

    class Config:
        env_file = ".env"


# Istanza globale usata in tutto il progetto
settings = Settings()
